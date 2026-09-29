import json
from app.agent import (
    search_runbooks,
    create_incident,
    update_incident,
    list_open_incidents,
    explain_exit_code,
)

print("--- Testing search_runbooks('CrashLoopBackOff') ---")
res = search_runbooks("CrashLoopBackOff")
parsed = json.loads(res)
print(f"Found {parsed.get('count', 0)} runbook(s). First title: {parsed.get('runbooks', [{}])[0].get('title')}")

print("\n--- Testing explain_exit_code(137) ---")
res_code = explain_exit_code(137)
print(res_code)

print("\n--- Testing create_incident ---")
inc_res = create_incident(
    cluster_name="staging-cluster-1",
    namespace="default",
    resource="deployment/auth-service",
    symptom="CrashLoopBackOff with ExitCode 137",
    category="resources",
    diagnosis="Container memory limit exceeded cgroup threshold during batch token processing",
    commands_suggested=[
        "kubectl describe pod auth-service",
        "kubectl logs auth-service --previous",
        "kubectl top pod auth-service"
    ]
)
inc_parsed = json.loads(inc_res)
inc_id = inc_parsed["incident_id"]
print(f"Created incident: {inc_id}")

print("\n--- Testing list_open_incidents ---")
open_list = list_open_incidents(cluster_name="staging-cluster-1")
print(f"Open incidents retrieved: {json.loads(open_list).get('count')}")

print("\n--- Testing update_incident (resolving) ---")
upd_res = update_incident(
    incident_id=inc_id,
    status="resolved",
    fix_applied="Bumped memory limit from 256Mi to 1Gi"
)
print(upd_res)
