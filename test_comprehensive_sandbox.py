import asyncio
from dotenv import load_dotenv
load_dotenv()

from app.agent import root_agent
from google.adk.runners import InMemoryRunner
from google.genai import types

async def run_scenario(title: str, prompt: str):
    print("=" * 70)
    print(f"RUNNING: {title}")
    print("=" * 70)
    print(f"User Input:\n{prompt}\n")
    
    runner = InMemoryRunner(agent=root_agent, app_name="k8s_troubleshooter")
    session = await runner.session_service.create_session(
        app_name="k8s_troubleshooter",
        user_id="sre-evaluator",
    )
    
    user_msg = types.Content(
        role="user",
        parts=[types.Part.from_text(text=prompt)]
    )
    
    response_text = ""
    async for event in runner.run_async(
        session_id=session.id,
        user_id="sre-evaluator",
        new_message=user_msg,
    ):
        if hasattr(event, "content") and event.content:
            for part in event.content.parts:
                if getattr(part, "text", None):
                    response_text += part.text
                elif getattr(part, "executable_code", None):
                    print(f"\n[SANDBOX EXECUTED CODE]:\n{part.executable_code.code}")
                elif getattr(part, "code_execution_result", None):
                    print(f"\n[SANDBOX OUTPUT]:\n{part.code_execution_result.output}")
                elif getattr(part, "function_call", None):
                    print(f"-> Tool Call: {part.function_call.name}({part.function_call.args})")

    print("\n[AGENT SUMMARY RESPONSE]:")
    print(response_text[:800] + ("..." if len(response_text) > 800 else ""))
    print("\n")

async def main():
    # Test 1: Kubectl get pods analysis (not ready, restart spikes)
    test1_prompt = """Here is my `kubectl get pods -n production`:
NAME                             READY   STATUS             RESTARTS         AGE
auth-service-79f8c6b758-m8vxz    1/1     Running            0                4d
checkout-api-5c8c998f4-z42qp     0/1     CrashLoopBackOff   42 (3m ago)      2h
inventory-worker-674b-pl98d      0/1     Error              18 (1m ago)      45m
payment-gw-6f987f65c-v4kmn       1/1     Running            2                12d
notification-svc-78bd6c8f-287qf  0/1     OOMKilled          8 (12m ago)      1h

Can you run Python in the sandbox to parse this table, count the total pods, not-ready pods, identify the pods with restart spikes, and calculate the cluster namespace health ratio?"""
    await run_scenario("TEST 1: KUBECTL GET PODS PARSER", test1_prompt)

    # Test 2: YAML manifest linter
    test2_prompt = """Can you run Python code in the sandbox to lint this Kubernetes deployment manifest and check for missing resources, limits, or probe health checks?

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
  namespace: e-commerce
spec:
  replicas: 3
  selector:
    matchLabels:
      app: order-svc
  template:
    metadata:
      labels:
        app: order-svc
    spec:
      containers:
      - name: order-container
        image: gcr.io/my-proj/order:v1.2.0
        ports:
        - containerPort: 8080
```"""
    await run_scenario("TEST 2: YAML MANIFEST LINTER", test2_prompt)

if __name__ == "__main__":
    asyncio.run(main())
