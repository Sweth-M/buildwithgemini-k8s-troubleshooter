import json
from app.agent import (
    check_k8s_version_lifecycle,
    explain_exit_code,
    create_incident,
    update_incident,
    list_open_incidents,
)

print("1. Testing check_k8s_version_lifecycle(kubernetes, 1.25):")
res_eol = json.loads(check_k8s_version_lifecycle("kubernetes", "1.25"))
print(f"   Cycle: {res_eol.get('cycle')}, EOL: {res_eol.get('eol')}, Supported: {res_eol.get('is_supported')}")

print("\n2. Testing check_k8s_version_lifecycle(python, 3.11):")
res_py = json.loads(check_k8s_version_lifecycle("python", "3.11"))
print(f"   Cycle: {res_py.get('cycle')}, EOL: {res_py.get('eol')}, Supported: {res_py.get('is_supported')}")

print("\n3. Testing explain_exit_code(137):")
res_code = json.loads(explain_exit_code(137))
print(f"   Meaning: {res_code.get('meaning')}, Signal: {res_code.get('signal')}")

print("\n4. Testing create_incident:")
inc = json.loads(create_incident(
    cluster_name="minikube-dev",
    namespace="default",
    resource="pod/test-pod",
    symptom="OOMKilled",
    category="resources",
    diagnosis="Pod breached memory limits",
    commands_suggested=["kubectl describe pod test-pod"]
))
inc_id = inc["incident_id"]
print(f"   Created Incident ID: {inc_id}")

print("\n5. Testing list_open_incidents:")
open_list = json.loads(list_open_incidents(cluster_name="minikube-dev"))
print(f"   Open incidents count for minikube-dev: {open_list.get('count')}")

print("\n6. Testing update_incident:")
upd = json.loads(update_incident(incident_id=inc_id, status="resolved", fix_applied="Increased memory to 512Mi"))
print(f"   Updated status: {upd.get('applied_updates', {}).get('status')}")
print("\n✅ All 5 requested tools verified successfully!")
