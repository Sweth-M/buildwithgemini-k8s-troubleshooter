import datetime
from google.cloud import firestore

# Explicitly hardcode project ID to avoid Agent Platform project number issue
PROJECT_ID = "qwiklabs-gcp-04-e954671c3d10"

RUNBOOKS = [
    {
        "id": "crashloopbackoff",
        "title": "CrashLoopBackOff",
        "category": "workload",
        "severity": "critical",
        "symptoms": [
            "Pod restarts repeatedly with back-off delay",
            "STATUS shows CrashLoopBackOff",
            "RESTARTS count keeps incrementing"
        ],
        "likely_causes": [
            "Unhandled application exception or fatal error on startup",
            "Missing environment variable, configuration file, or secret",
            "Misconfigured command or args in container spec",
            "Failing startup or liveness probe timing out before container is ready"
        ],
        "diagnostic_commands": [
            "kubectl logs <pod-name> -n <namespace> --previous",
            "kubectl describe pod <pod-name> -n <namespace>",
            "kubectl get events -n <namespace> --field-selector involvedObject.name=<pod-name> --sort-by='.lastTimestamp'"
        ],
        "fix_steps": [
            "1. Inspect previous logs: `kubectl logs <pod-name> --previous` to identify the unhandled runtime stack trace.",
            "2. Verify all ConfigMaps and Secrets referenced in `env` or `envFrom` exist in the namespace.",
            "3. If startup takes longer than expected, increase `initialDelaySeconds` and `failureThreshold` in `startupProbe`.",
            "4. Verify the container command and entrypoint arguments."
        ]
    },
    {
        "id": "oomkilled",
        "title": "OOMKilled (Exit Code 137)",
        "category": "resources",
        "severity": "critical",
        "symptoms": [
            "Pod terminated with Exit Code 137",
            "Last State shows Reason: OOMKilled",
            "Sudden restart during memory-intensive processing"
        ],
        "likely_causes": [
            "Container memory footprint exceeded spec.containers[*].resources.limits.memory",
            "JVM or runtime not cgroup-aware allocating more heap than the container limit",
            "Memory leak in application code retaining object references",
            "Node-level memory pressure triggering kernel OOM killer"
        ],
        "diagnostic_commands": [
            "kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.status.containerStatuses[*].lastState.terminated.reason}'",
            "kubectl describe pod <pod-name> -n <namespace>",
            "kubectl top pod <pod-name> -n <namespace> --containers"
        ],
        "fix_steps": [
            "1. Increase container memory limit: `kubectl set resources deployment/<deploy> -c=<container> --limits=memory=1Gi`.",
            "2. If Java/JVM: configure `-XX:MaxRAMPercentage=75.0` or `-XX:+UseContainerSupport` to avoid over-allocating heap.",
            "3. If Node.js: configure `--max-old-space-size=<megabytes>` proportional to container memory.",
            "4. Profile application memory usage to locate and fix memory leaks."
        ]
    },
    {
        "id": "imagepullbackoff",
        "title": "ImagePullBackOff / ErrImagePull",
        "category": "registry",
        "severity": "high",
        "symptoms": [
            "STATUS shows ImagePullBackOff or ErrImagePull",
            "Pod cannot start any containers",
            "Event logs show 'Failed to pull image'"
        ],
        "likely_causes": [
            "Typo in image name, repository path, or tag (tags are case-sensitive)",
            "Private registry authentication failed / missing imagePullSecrets",
            "Docker Hub anonymous pull rate limit exceeded (HTTP 429)",
            "Network firewall or node egress blocking registry endpoint"
        ],
        "diagnostic_commands": [
            "kubectl describe pod <pod-name> -n <namespace> | grep -A 10 Events:",
            "kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.imagePullSecrets}'",
            "kubectl get secrets -n <namespace>"
        ],
        "fix_steps": [
            "1. Verify image name and tag spelling: test with `docker pull <image>` locally.",
            "2. Create docker-registry secret: `kubectl create secret docker-registry regcred --docker-server=... --docker-username=... --docker-password=...`.",
            "3. Add `imagePullSecrets: [{name: regcred}]` to the Pod spec or attach to default service account.",
            "4. For Google Artifact Registry, ensure the cluster service account has `roles/artifactregistry.reader`."
        ]
    },
    {
        "id": "pending-unschedulable",
        "title": "Pending (Insufficient CPU/Memory, Unschedulable)",
        "category": "scheduler",
        "severity": "high",
        "symptoms": [
            "Pod remains in Pending status indefinitely",
            "No node assigned to pod",
            "Events show '0/N nodes are available: Insufficient cpu/memory'"
        ],
        "likely_causes": [
            "Cluster capacity exhausted: sum of requests exceeds node allocatable resources",
            "Pod resources.requests set higher than any single worker node capacity",
            "PersistentVolumeClaim (PVC) unbound or in Pending state",
            "NodeSelector or nodeAffinity does not match any active node labels",
            "Node taints lack corresponding pod tolerations"
        ],
        "diagnostic_commands": [
            "kubectl describe pod <pod-name> -n <namespace> | grep -A 10 Events:",
            "kubectl get nodes",
            "kubectl describe nodes | grep -A 6 'Allocated resources:'",
            "kubectl get pvc -n <namespace>"
        ],
        "fix_steps": [
            "1. Check if resource requests are over-provisioned; lower `resources.requests.cpu` and `memory`.",
            "2. Scale out cluster worker nodes or verify Cluster Autoscaler is enabled.",
            "3. If PVC is pending, inspect storage class and provisioner: `kubectl describe pvc <claim-name>`.",
            "4. Check node labels: `kubectl get nodes --show-labels` and verify against `nodeSelector`."
        ]
    },
    {
        "id": "createcontainerconfigerror",
        "title": "CreateContainerConfigError (Missing ConfigMap/Secret)",
        "category": "configuration",
        "severity": "high",
        "symptoms": [
            "STATUS shows CreateContainerConfigError or CreateContainerError",
            "Container cannot be created",
            "Events show 'configmap \"xyz\" not found' or 'secret \"xyz\" not found'"
        ],
        "likely_causes": [
            "ConfigMap or Secret referenced in `env[].valueFrom` or `envFrom` does not exist",
            "ConfigMap or Secret exists in a different namespace than the Pod",
            "Key specified in `configMapKeyRef` or `secretKeyRef` is missing from data map"
        ],
        "diagnostic_commands": [
            "kubectl describe pod <pod-name> -n <namespace> | grep -A 8 Events:",
            "kubectl get configmap -n <namespace>",
            "kubectl get secrets -n <namespace>"
        ],
        "fix_steps": [
            "1. Inspect the exact missing resource name from Events: `kubectl describe pod <pod-name>`.",
            "2. Create the missing ConfigMap: `kubectl create configmap <name> --from-literal=KEY=VALUE -n <namespace>`.",
            "3. Create the missing Secret: `kubectl create secret generic <name> --from-literal=KEY=VALUE -n <namespace>`.",
            "4. Verify keys within the ConfigMap/Secret match the manifest `key:` field."
        ]
    },
    {
        "id": "evicted-pod",
        "title": "Evicted (Node Disk/Memory Pressure)",
        "category": "node-pressure",
        "severity": "high",
        "symptoms": [
            "STATUS shows Evicted",
            "Multiple pods across node terminated unexpectedly",
            "Node Conditions show DiskPressure, MemoryPressure, or PIDPressure"
        ],
        "likely_causes": [
            "Node root filesystem or imagefs disk usage exceeded eviction threshold (default 85%)",
            "Node memory allocatable capacity exhausted",
            "Application container writing unrotated large log files to container filesystem instead of stdout"
        ],
        "diagnostic_commands": [
            "kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.status.reason}'",
            "kubectl describe node <node-name> | grep -A 8 Conditions:",
            "kubectl get pods -n <namespace> --field-selector status.phase=Failed"
        ],
        "fix_steps": [
            "1. Clean up unused evicted pods: `kubectl delete pod --field-selector status.phase=Failed -n <namespace>`.",
            "2. SSH or inspect node disk usage: prune dangling docker/containerd images and stale logs.",
            "3. Ensure container logging uses stdout/stderr with daemon log rotation (max-size).",
            "4. Expand worker node disk size or add more nodes to distribute workload."
        ]
    },
    {
        "id": "probe-failure",
        "title": "Readiness / Liveness Probe Failures",
        "category": "healthcheck",
        "severity": "medium",
        "symptoms": [
            "READY column shows 0/1 although pod is Running",
            "Pod is repeatedly killed (liveness) or receives no traffic (readiness)",
            "Events show 'Unhealthy: Liveness probe failed' or 'Readiness probe failed'"
        ],
        "likely_causes": [
            "Application health endpoint `/healthz` returning 5xx or timing out under load",
            "`initialDelaySeconds` is too small; probe starts before server finishes booting",
            "Probe checking wrong port, protocol (HTTP vs HTTPS), or path",
            "Heavy garbage collection pause or deadlocked worker thread"
        ],
        "diagnostic_commands": [
            "kubectl describe pod <pod-name> -n <namespace> | grep -A 10 Events:",
            "kubectl describe pod <pod-name> -n <namespace> | grep -A 6 'Liveness:'",
            "kubectl logs <pod-name> -n <namespace> --tail=50"
        ],
        "fix_steps": [
            "1. Increase `initialDelaySeconds` to give the app adequate boot time (e.g., 20-30s).",
            "2. Increase `timeoutSeconds` (e.g., 5s) and `failureThreshold` (e.g., 3-5).",
            "3. Test healthcheck endpoint locally inside container: `kubectl exec -it <pod-name> -- curl -I http://localhost:<port>/healthz`.",
            "4. Differentiate liveness (should only detect deadlocks) from readiness (can shed traffic when overloaded)."
        ]
    },
    {
        "id": "service-no-endpoints",
        "title": "Service Has No Endpoints (Selector Mismatch)",
        "category": "networking",
        "severity": "medium",
        "symptoms": [
            "Clients receive Connection Refused or HTTP 503 when calling Service",
            "`kubectl get endpoints <svc>` shows `<none>`",
            "Pods are running fine but receiving zero traffic"
        ],
        "likely_causes": [
            "Labels defined in `spec.selector` on Service do not match labels in Pod `spec.template.metadata.labels`",
            "Target pod readiness probe is failing, so endpoints controller removes it",
            "Service port `targetPort` does not match the port the application is listening on"
        ],
        "diagnostic_commands": [
            "kubectl get endpoints <service-name> -n <namespace>",
            "kubectl describe service <service-name> -n <namespace>",
            "kubectl get pods -n <namespace> --show-labels"
        ],
        "fix_steps": [
            "1. Compare `spec.selector` on Service with `metadata.labels` on Pods.",
            "2. Align labels: ensure every key-value pair under service selector exists on target pods.",
            "3. Verify pod readiness: `kubectl get pods -l <selector-labels>` - pods must be `1/1 Running`.",
            "4. Verify `targetPort` in Service matches container `containerPort`."
        ]
    },
    {
        "id": "coredns-failure",
        "title": "CoreDNS / In-Cluster DNS Failure",
        "category": "networking",
        "severity": "critical",
        "symptoms": [
            "Pods cannot resolve internal service names (e.g. `service.namespace.svc.cluster.local`)",
            "External domain names fail with 'nslookup: can't resolve'",
            "Application fails with connection errors to database hostname"
        ],
        "likely_causes": [
            "CoreDNS pods are in CrashLoopBackOff, Pending, or OOMKilled in `kube-system`",
            "NetworkPolicy blocking port 53 UDP/TCP traffic between application pods and CoreDNS",
            "Node upstream DNS resolver unreachable or forwarding loop detected in Corefile"
        ],
        "diagnostic_commands": [
            "kubectl get pods -n kube-system -l k8s-app=kube-dns",
            "kubectl logs -n kube-system -l k8s-app=kube-dns",
            "kubectl exec -i -t <pod-name> -n <namespace> -- nslookup kubernetes.default"
        ],
        "fix_steps": [
            "1. Check CoreDNS status: `kubectl get pods -n kube-system -l k8s-app=kube-dns`.",
            "2. Check CoreDNS logs for upstream forward loops: `kubectl logs -n kube-system -l k8s-app=kube-dns`.",
            "3. If CoreDNS is OOMKilled, increase memory limit in `coredns` deployment manifest.",
            "4. Check for restrictive NetworkPolicies blocking egress to `kube-system` port 53."
        ]
    },
    {
        "id": "node-notready",
        "title": "Node NotReady",
        "category": "infrastructure",
        "severity": "critical",
        "symptoms": [
            "STATUS shows NotReady in `kubectl get nodes`",
            "Pods on the node enter Unknown or Terminating state",
            "New pods cannot be scheduled onto the node"
        ],
        "likely_causes": [
            "kubelet daemon crashed, stopped, or failed healthcheck",
            "Container runtime (containerd / CRI-O) unresponsive or stopped",
            "Node out of disk space (`DiskPressure`) or memory (`MemoryPressure`)",
            "Network partition between worker node and Kubernetes control plane API server"
        ],
        "diagnostic_commands": [
            "kubectl describe node <node-name>",
            "kubectl get nodes -o wide",
            "systemctl status kubelet (on worker node host)",
            "journalctl -u kubelet -n 100 --no-pager (on worker node host)"
        ],
        "fix_steps": [
            "1. Inspect conditions under `kubectl describe node <node-name>` (Ready, DiskPressure, MemoryPressure).",
            "2. SSH to node and verify kubelet status: `systemctl status kubelet` and `systemctl restart kubelet`.",
            "3. Verify container runtime: `systemctl status containerd`.",
            "4. Check disk usage with `df -h` to verify `/var/lib/kubelet` and `/var/lib/containerd` have available space.",
            "5. Verify security groups / firewall rules allow bidirectional communication between node and master on port 6443/10250."
        ]
    }
]


def seed():
    print(f"Connecting to Firestore for project: {PROJECT_ID}...")
    db = firestore.Client(project=PROJECT_ID)
    collection = db.collection("k8s_runbooks")
    
    print(f"Seeding {len(RUNBOOKS)} runbooks into 'k8s_runbooks'...")
    now = datetime.datetime.now(datetime.timezone.utc)
    
    for rb in RUNBOOKS:
        doc_id = rb["id"]
        data = {
            "title": rb["title"],
            "category": rb["category"],
            "severity": rb["severity"],
            "symptoms": rb["symptoms"],
            "likely_causes": rb["likely_causes"],
            "diagnostic_commands": rb["diagnostic_commands"],
            "fix_steps": rb["fix_steps"],
            "updated_at": now,
        }
        collection.document(doc_id).set(data)
        print(f"  ✓ Seeded runbook: {rb['title']} (ID: {doc_id})")
        
    print("✅ Successfully seeded all 10 Kubernetes runbooks into Firestore!")

if __name__ == "__main__":
    seed()
