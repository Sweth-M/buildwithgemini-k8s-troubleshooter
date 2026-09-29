# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import json
import urllib.request
import uuid
from typing import Any, Dict, List, Optional

from google import genai
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.memory import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.adk.tools.tool_context import ToolContext
from google.cloud import firestore, storage
from google.genai import types

from .a2ui_instruction import INSTRUCTION as A2UI_SYSTEM_INSTRUCTION
from .a2ui_utils import a2ui_callback

MODEL = "gemini-3.6-flash"

# IMPORTANT: Hardcode GCP project ID, Storage Bucket, and Agent Engine references as string literals.
# On Agent Platform, google.auth.default() and GOOGLE_CLOUD_PROJECT can return
# the numeric project number, which breaks Firestore/GCS operations.
GCP_PROJECT_ID = "qwiklabs-gcp-04-e954671c3d10"
DIAGRAMS_BUCKET_NAME = "k8s-troubleshooter-diagrams-e954671c"

# Agent Engine ID reused as Memory Bank
MEMORY_BANK_ID = "2926440357279301632"
AGENT_ENGINE_ID = f"projects/698694960991/locations/us-east1/reasoningEngines/{MEMORY_BANK_ID}"
SANDBOX_ID = f"projects/698694960991/locations/us-east1/reasoningEngines/{MEMORY_BANK_ID}/sandboxEnvironments/4361252453992103936"

# Initialize AgentEngineSandboxCodeExecutor with the dedicated Sandbox Environment
sandbox_code_executor = AgentEngineSandboxCodeExecutor(
    sandbox_resource_name=SANDBOX_ID,
    agent_engine_resource_name=AGENT_ENGINE_ID,
)

_db: Optional[firestore.Client] = None
_storage_client: Optional[storage.Client] = None


def get_firestore_client() -> firestore.Client:
    """Returns a singleton Firestore client explicitly configured with the GCP project string."""
    global _db
    if _db is None:
        _db = firestore.Client(project=GCP_PROJECT_ID)
    return _db


def get_storage_client() -> storage.Client:
    """Returns a singleton Cloud Storage client explicitly configured with the GCP project string."""
    global _storage_client
    if _storage_client is None:
        _storage_client = storage.Client(project=GCP_PROJECT_ID)
    return _storage_client


# WRITE: after each turn, send the session to Memory Bank for durable extraction
async def generate_memories_callback(callback_context: CallbackContext):
    await callback_context.add_session_to_memory()
    return None


def memory_bank_service_builder():
    """Builds the VertexAiMemoryBankService pointing to the deployed Agent Engine."""
    return VertexAiMemoryBankService(
        project=GCP_PROJECT_ID,
        location="us-east1",
        agent_engine_id=MEMORY_BANK_ID,
    )


async def generate_cluster_topology_diagram(
    scenario: str,
    failing_component: str,
    tool_context: ToolContext,
) -> str:
    """Generates an illustrated Kubernetes cluster topology diagram highlighting the failing component in red.

    Uses the gemini-3.1-flash-lite-image model in the global region.
    Does two things with the generated image:
    1. Saves it via tool_context.save_artifact so it displays in the Playground Artifacts panel.
    2. Uploads the exact same image bytes directly to the public Cloud Storage bucket and returns its public HTTPS URL.
    Never writes image bytes to local disk.

    Args:
        scenario: Description of the cluster problem (e.g. 'Payment service Pod OOMKilled under high traffic', 'CoreDNS crash causing cluster-wide DNS failure').
        failing_component: The specific failing tier or component to highlight in bold red (e.g. 'Pods', 'Deployment', 'Service', 'Ingress', 'Node').
        tool_context: ADK ToolContext used to save artifacts to the active session.

    Returns:
        JSON string containing the public Cloud Storage image URL, artifact filename, and scenario summary.
    """
    try:
        genai_client = genai.Client(vertexai=True, project=GCP_PROJECT_ID, location="global")
        prompt = (
            f"A clean, technical architecture illustration of a Kubernetes cluster experiencing an issue: {scenario}. "
            "Depicting the standard workflow layers on cluster worker nodes: Ingress -> Service -> Deployment -> Pods -> Containers. "
            f"Visually highlight the failing component ({failing_component}) in bold striking red with a warning icon. "
            "Clean technical-illustration style with clear component boundaries, neat topology flow lines, and labels. "
            "Do not draw the official Kubernetes logo."
        )

        response = genai_client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt,
        )

        image_bytes = None
        mime_type = "image/jpeg"
        for candidate in response.candidates:
            if candidate.content and candidate.content.parts:
                for part in candidate.content.parts:
                    if getattr(part, "inline_data", None):
                        image_bytes = part.inline_data.data
                        mime_type = part.inline_data.mime_type or "image/jpeg"
                        break
            if image_bytes:
                break

        if not image_bytes:
            return json.dumps({"error": "No image data was generated by gemini-3.1-flash-lite-image."}, indent=2)

        artifact_filename = f"k8s_topology_{uuid.uuid4().hex[:8]}.jpg"
        artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        await tool_context.save_artifact(filename=artifact_filename, artifact=artifact_part)

        client = get_storage_client()
        bucket = client.bucket(DIAGRAMS_BUCKET_NAME)
        blob = bucket.blob(artifact_filename)
        blob.upload_from_string(image_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{DIAGRAMS_BUCKET_NAME}/{artifact_filename}"

        return json.dumps({
            "success": True,
            "artifact_filename": artifact_filename,
            "public_url": public_url,
            "failing_component": failing_component,
            "scenario": scenario,
            "message": f"Cluster topology diagram generated, saved as artifact '{artifact_filename}', and uploaded to {public_url}"
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to generate cluster topology diagram: {str(e)}"}, indent=2)


def check_version_support_eol(product: str = "kubernetes", version: Optional[str] = None) -> str:
    """Checks whether a Kubernetes or container base image version is still supported or end-of-life (EOL).

    Fetches real data from the free endoflife.date API (https://endoflife.date/api/{product}.json).
    Supports products like 'kubernetes', 'python', 'nginx', 'postgresql', 'redis', 'golang'.

    Args:
        product: Name of the product or base image (e.g. 'kubernetes', 'python', 'nginx', 'redis').
        version: Specific major.minor version string to check (e.g. '1.25', '1.30', '3.11').

    Returns:
        JSON string with real release date, EOL date, support status, and latest patch release.
    """
    clean_product = product.strip().lower()
    url = f"https://endoflife.date/api/{clean_product}.json"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "K8s-Troubleshooter-Agent/1.0", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        return json.dumps({"error": f"Failed to fetch lifecycle for {product}: {str(e)}"}, indent=2)

    today = datetime.date.today().isoformat()
    if version:
        v_clean = version.strip().lstrip("v")
        for cycle in data:
            if cycle.get("cycle") == v_clean:
                eol = cycle.get("eol")
                is_supported = (eol is False) or (isinstance(eol, str) and eol > today)
                return json.dumps({
                    "product": clean_product,
                    "cycle": cycle.get("cycle"),
                    "eol": eol,
                    "is_supported": is_supported,
                    "latest_patch": cycle.get("latest"),
                    "release_date": cycle.get("releaseDate"),
                }, indent=2)
        return json.dumps({
            "product": clean_product,
            "version_queried": version,
            "status": "version_not_found",
            "available_cycles": [c.get("cycle") for c in data[:5]]
        }, indent=2)

    return json.dumps({
        "product": clean_product,
        "recent_cycles": [
            {
                "cycle": c.get("cycle"),
                "eol": c.get("eol"),
                "is_supported": (c.get("eol") is False) or (isinstance(c.get("eol"), str) and c.get("eol") > today),
                "latest_patch": c.get("latest"),
                "release_date": c.get("releaseDate"),
            }
            for c in data[:3]
        ]
    }, indent=2)


def get_latest_k8s_release() -> str:
    """Fetches the latest official stable Kubernetes release from the GitHub Releases API.

    Queries https://api.github.com/repos/kubernetes/kubernetes/releases/latest with a timeout.

    Returns:
        JSON string containing the latest release tag (e.g. 'v1.31.1'), publish date, and release URL.
    """
    url = "https://api.github.com/repos/kubernetes/kubernetes/releases/latest"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "K8s-Troubleshooter-Agent/1.0",
            "Accept": "application/vnd.github.v3+json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        return json.dumps({
            "latest_tag": data.get("tag_name"),
            "name": data.get("name"),
            "published_at": data.get("published_at"),
            "html_url": data.get("html_url"),
            "prerelease": data.get("prerelease", False),
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to fetch latest Kubernetes release: {str(e)}"}, indent=2)


def explain_exit_code(exit_code: int) -> str:
    """Deterministic lookup for common container and Linux exit codes.

    Args:
        exit_code: Container process exit code (e.g. 0, 1, 126, 127, 137, 139, 143).

    Returns:
        Structured JSON explanation with signal breakdown, typical Kubernetes root causes, and verification steps.
    """
    table = {
        0: {
            "meaning": "Success / Graceful termination",
            "signal": "None",
            "description": "Container process exited normally (expected for Jobs). For Deployments, process may lack a foreground PID 1 daemon.",
            "recommended_check": "Ensure entrypoint keeps process in foreground."
        },
        1: {
            "meaning": "Application Error / Unhandled Exception",
            "signal": "General Error",
            "description": "Unhandled runtime exception, missing environment variable, or startup script failure.",
            "recommended_check": "Run `kubectl logs <pod> -n <namespace> --previous` to inspect the runtime stack trace."
        },
        126: {
            "meaning": "Command Invoked Cannot Execute",
            "signal": "Permission Denied",
            "description": "The command was found but lacks execute permissions (`chmod +x`) or architecture mismatch.",
            "recommended_check": "Check executable permissions or container architecture."
        },
        127: {
            "meaning": "File or Command Not Found",
            "signal": "PATH lookup failure",
            "description": "The binary or script specified in `command`/`args` does not exist in the container image.",
            "recommended_check": "Verify binary paths in image: `docker run --rm -it <image> which <cmd>`."
        },
        137: {
            "meaning": "Fatal Error: SIGKILL (128 + 9)",
            "signal": "SIGKILL (9)",
            "description": "Process terminated by Linux kernel OOM killer or Kubernetes liveness probe timeout.",
            "recommended_check": "Check `kubectl describe pod <pod>` for `Reason: OOMKilled` and increase memory limits."
        },
        139: {
            "meaning": "Fatal Error: Segmentation Fault (128 + 11)",
            "signal": "SIGSEGV (11)",
            "description": "Process attempted to access unmapped memory (native library corruption or libc/musl mismatch).",
            "recommended_check": "Check compiled C/C++ dependencies and base image architecture."
        },
        143: {
            "meaning": "Graceful Termination: SIGTERM (128 + 15)",
            "signal": "SIGTERM (15)",
            "description": "Graceful termination signal from Kubernetes (normal during rolling update, pod eviction, or node drain).",
            "recommended_check": "Inspect cluster events: `kubectl get events --sort-by='.lastTimestamp'`."
        }
    }

    if exit_code in table:
        return json.dumps({"exit_code": exit_code, "status": "known", **table[exit_code]}, indent=2)
    sig = exit_code - 128 if exit_code > 128 else None
    return json.dumps({
        "exit_code": exit_code,
        "status": "custom_or_uncommon",
        "meaning": f"Terminated by signal {sig}" if sig else "Custom application error",
        "recommended_check": "Inspect application-specific exit routines in container logs."
    }, indent=2)


def create_incident(
    cluster_name: str,
    namespace: str,
    resource: str,
    symptom: str,
    category: str,
    diagnosis: str,
    commands_suggested: List[str],
) -> str:
    """Logs a new Kubernetes incident in Firestore collection `k8s_incidents`.

    Args:
        cluster_name: Name or context of the Kubernetes cluster (e.g. 'prod-cluster', 'minikube').
        namespace: Kubernetes namespace (e.g. 'default', 'kube-system').
        resource: Target Kubernetes resource (e.g. 'deployment/auth-service', 'pod/payment-worker-xyz').
        symptom: Observed failure symptom (e.g. 'Pod restarting with ExitCode 137').
        category: Incident category (e.g. 'workload', 'resources', 'scheduler', 'registry', 'network').
        diagnosis: Technical root cause assessment.
        commands_suggested: List of read-only diagnostic commands suggested to the user.

    Returns:
        JSON string confirming the incident was created with its generated `incident_id`.
    """
    try:
        db = get_firestore_client()
        incident_id = f"inc-{uuid.uuid4().hex[:8]}"
        now = datetime.datetime.now(datetime.timezone.utc)

        incident_data = {
            "incident_id": incident_id,
            "cluster_name": cluster_name,
            "namespace": namespace,
            "resource": resource,
            "symptom": symptom,
            "category": category,
            "diagnosis": diagnosis,
            "commands_suggested": commands_suggested,
            "status": "open",
            "created_at": now.isoformat(),
            "resolved_at": None,
        }

        db.collection("k8s_incidents").document(incident_id).set(incident_data)
        return json.dumps({"status": "created", "incident_id": incident_id, "details": incident_data}, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to create incident: {str(e)}"}, indent=2)


def update_incident(
    incident_id: str,
    status: Optional[str] = None,
    diagnosis: Optional[str] = None,
    fix_applied: Optional[str] = None,
) -> str:
    """Updates an existing Kubernetes incident status or resolution notes in `k8s_incidents`.

    Args:
        incident_id: The ID of the incident (e.g. 'inc-3a9b2c1d').
        status: Updated status ('open' or 'resolved').
        diagnosis: Updated or refined diagnosis details.
        fix_applied: Description of the remediation executed.

    Returns:
        JSON string confirming the update.
    """
    try:
        db = get_firestore_client()
        doc_ref = db.collection("k8s_incidents").document(incident_id)
        doc = doc_ref.get()

        if not doc.exists:
            return json.dumps({"error": f"Incident '{incident_id}' not found."}, indent=2)

        updates: Dict[str, Any] = {}
        if status:
            updates["status"] = status
            if status.lower() == "resolved":
                updates["resolved_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if diagnosis:
            updates["diagnosis"] = diagnosis
        if fix_applied:
            updates["fix_applied"] = fix_applied

        doc_ref.update(updates)
        return json.dumps({"status": "updated", "incident_id": incident_id, "applied_updates": updates}, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to update incident: {str(e)}"}, indent=2)


def list_open_incidents(cluster_name: Optional[str] = None, namespace: Optional[str] = None) -> str:
    """Lists all active and unresolved incidents from Firestore collection `k8s_incidents`.

    Args:
        cluster_name: Optional filter for a specific cluster name.
        namespace: Optional filter for a specific namespace.

    Returns:
        JSON string listing open incidents.
    """
    try:
        db = get_firestore_client()
        query = db.collection("k8s_incidents").where(filter=firestore.FieldFilter("status", "==", "open"))
        docs = query.stream()

        incidents = []
        for doc in docs:
            item = doc.to_dict()
            if cluster_name and item.get("cluster_name", "").lower() != cluster_name.lower():
                continue
            if namespace and item.get("namespace", "").lower() != namespace.lower():
                continue
            incidents.append(item)

        return json.dumps({"count": len(incidents), "open_incidents": incidents}, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to list open incidents: {str(e)}"}, indent=2)


def search_runbooks(query: str, category: Optional[str] = None) -> str:
    """Searches the Kubernetes runbooks library in Firestore (`k8s_runbooks`).

    Args:
        query: Search term or symptom (e.g., 'CrashLoopBackOff', 'OOMKilled', '137', 'CoreDNS').
        category: Optional category filter.

    Returns:
        JSON string containing matching runbooks.
    """
    try:
        db = get_firestore_client()
        docs = db.collection("k8s_runbooks").stream()
        results = []
        q = query.lower()

        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            if "updated_at" in data and isinstance(data["updated_at"], datetime.datetime):
                data["updated_at"] = data["updated_at"].isoformat()

            if category and data.get("category", "").lower() != category.lower():
                continue

            matched = (
                q in data.get("title", "").lower()
                or q in data.get("category", "").lower()
                or any(q in s.lower() for s in data.get("symptoms", []))
                or any(q in c.lower() for c in data.get("likely_causes", []))
            )
            if matched or not query.strip():
                results.append(data)

        return json.dumps({"count": len(results), "runbooks": results}, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to search runbooks: {str(e)}"}, indent=2)


root_agent = Agent(
    name="k8s_troubleshooter",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    code_executor=sandbox_code_executor,
    instruction=A2UI_SYSTEM_INSTRUCTION,
    tools=[
        PreloadMemoryTool(),
        generate_cluster_topology_diagram,
        check_version_support_eol,
        get_latest_k8s_release,
        explain_exit_code,
        create_incident,
        update_incident,
        list_open_incidents,
        search_runbooks,
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
