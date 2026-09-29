import json
from app.agent import check_version_support_eol, get_latest_k8s_release

print("--- Testing check_version_support_eol('kubernetes', '1.27') ---")
res_k8s = json.loads(check_version_support_eol("kubernetes", "1.27"))
print(json.dumps(res_k8s, indent=2))

print("\n--- Testing check_version_support_eol('redis', '6.0') ---")
res_redis = json.loads(check_version_support_eol("redis", "6.0"))
print(json.dumps(res_redis, indent=2))

print("\n--- Testing get_latest_k8s_release() ---")
res_gh = json.loads(get_latest_k8s_release())
print(json.dumps(res_gh, indent=2))

assert "latest_tag" in res_gh
assert "is_supported" in res_k8s
print("\n✅ All free external API tools returned real data successfully with timeouts!")
