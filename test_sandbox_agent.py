import asyncio
from dotenv import load_dotenv
load_dotenv()

from app.agent import root_agent
from google.adk.runners import InMemoryRunner
from google.genai import types

async def main():
    print("Testing k8s-troubleshooter agent with Sandbox Code Executor...")
    prompt = """Here is the `kubectl top pod` output from my payments namespace:
NAME                          CPU(cores)   MEMORY(bytes)
auth-service-755d49658-2xqj   125m         480Mi
payment-worker-8b4df56-z9lw   890m         1920Mi
order-api-6f987f65c-v4kmn     45m          120Mi

The payment-worker has a memory limit of 2Gi and CPU limit of 1000m.
Can you run Python code in the sandbox to parse these values, convert Mi to Gi and percentages, and calculate how close payment-worker is to its memory limit and CPU limit?"""

    print(f"User Query:\n{prompt}\n")
    
    runner = InMemoryRunner(agent=root_agent, app_name="k8s_troubleshooter")
    session = await runner.session_service.create_session(
        app_name="k8s_troubleshooter",
        user_id="sre-sandbox-tester",
    )
    
    user_msg = types.Content(
        role="user",
        parts=[types.Part.from_text(text=prompt)]
    )
    
    response_text = ""
    async for event in runner.run_async(
        session_id=session.id,
        user_id="sre-sandbox-tester",
        new_message=user_msg,
    ):
        if hasattr(event, "content") and event.content:
            for part in event.content.parts:
                if getattr(part, "text", None):
                    response_text += part.text
                elif getattr(part, "executable_code", None):
                    print(f"\n[AGENT SANDBOX CODE EXECUTION]:\n```python\n{part.executable_code.code}\n```")
                elif getattr(part, "code_execution_result", None):
                    print(f"\n[SANDBOX STDOUT]:\n{part.code_execution_result.output}")
                elif getattr(part, "function_call", None):
                    print(f"-> Tool Call: {part.function_call.name}")

    print("\n--- Final Agent Response ---")
    print(response_text)

if __name__ == "__main__":
    asyncio.run(main())
