# My agent: K8s Troubleshooter
One-liner: A conversational agent that helps developers and cluster admins diagnose Kubernetes problems across any distribution (RKE2, GKE, minikube, kind) with a catalog of verified runbooks and incident tracking.

## Behaviour
Diagnoses like an SRE:
- Asks the user for the observed symptom.
- Directs the user to run specific read-only `kubectl` commands (`get pods`, `describe pod`, `get events`, `logs --previous`, `top pods`, `get nodes`).
- Analyzes pasted terminal output, identifies the root cause, and provides exact remediation commands or YAML manifest changes.
- Automatically logs and updates incidents in Firestore.
- Safety guardrails: Never executes commands directly against real clusters; always suggests read-only diagnostic commands first; explicitly warns with clear cautions before any destructive or disruptive command (`delete`, `drain`, `cordon`, `scale to zero`).

## Tool coverage:
- **Memory**: Remembers the user's Kubernetes distribution (e.g., RKE2, GKE, minikube, kind), Kubernetes version, cluster names, default namespace, container runtime (containerd/CRI-O), and recurring workload issues.
- **Tools**:
  - `search_runbooks`: Queries Firestore collection `k8s_runbooks` for matching troubleshooting guides by symptom or category.
  - `create_incident`: Creates and logs an incident in Firestore collection `k8s_incidents`.
  - `update_incident`: Updates diagnosis, recommended fix, and status in `k8s_incidents`.
  - `list_open_incidents`: Retrieves unresolved incidents from `k8s_incidents`.
  - `explain_exit_code`: Deterministic lookup for container exit codes (`0`, `1`, `126`, `127`, `137`, `139`, `143`).
  - `check_k8s_release`: Queries GitHub releases API (`https://api.github.com/repos/kubernetes/kubernetes/releases/latest`) for current Kubernetes release info.
  - `check_eol_support`: Queries `endoflife.date` API (`https://endoflife.date/api/kubernetes.json` and base images like python, nginx, postgresql, redis) to check version support lifecycle.
- **Catalog/UI**:
  - Firestore Collections:
    - `k8s_runbooks`: Schema includes `title`, `category`, `symptoms` (list), `likely_causes` (list), `diagnostic_commands` (list), `fix_steps` (list), `severity`. Seeded with 10 core runbooks:
      1. CrashLoopBackOff
      2. OOMKilled (exit code 137)
      3. ImagePullBackOff / ErrImagePull
      4. Pending (Insufficient CPU/memory, unschedulable)
      5. CreateContainerConfigError (missing ConfigMap/Secret)
      6. Evicted (node disk/memory pressure)
      7. Readiness / liveness probe failures
      8. Service has no endpoints (selector mismatch)
      9. CoreDNS / in-cluster DNS failure
      10. Node NotReady
    - `k8s_incidents`: Schema includes `incident_id`, `cluster_name`, `namespace`, `resource`, `symptom`, `category`, `diagnosis`, `commands_suggested` (list), `status` (open/resolved), `created_at`, `resolved_at`.
  - A2UI Surfaces:
    - **Diagnosis Card**: Displays target resource, current status, identified root cause, confidence score, copyable fix commands, and generated cluster topology diagram.
    - **Pod Health Table**: Displays name, ready count, status, restart counts, and age.
    - **Open Incidents Table**: Overview of active cluster triage tickets.
- **Image gen**: Generates an illustrated cluster architecture diagram (`Ingress -> Service -> Deployment -> Pods -> Containers, on Nodes`) highlighting the failing component in red. Clean technical-illustration style; excludes the official Kubernetes logo.
- **Sandbox**:
  - Parses pasted `kubectl` output (`get pods`, `describe`, `events`, `top`).
  - Counts pods not ready and restart spikes.
  - Converts between memory units (`Mi`, `Gi`, `bytes`) and CPU millicores.
  - Compares observed consumption against requests/limits and flags pods nearing memory exhaustion.
  - Decodes exit codes and signals.
  - Lints pasted YAML manifests with `pyyaml` to detect missing resource limits, missing probes, or mismatched pod labels and service selectors.
  - Charts restart trends per pod.

## Recommended for every project:
Memory (Vertex AI Memory Bank), storage (Firestore `k8s_runbooks` & `k8s_incidents`), tools, image generation (`gemini-3.1-flash-lite-image`), A2UI (v0.8 Basic Catalog).

## Agent-specific / stretch (pick what fits):
- Code sandbox for parsing kubectl outputs and YAML manifest linting with `pyyaml`.
- Free external APIs: `endoflife.date` and GitHub releases API.
- Eval set of real `kubectl` outputs with expected diagnoses.
- Helm chart version and deprecation checks.
- Omni video explaining cluster remediation workflows.
