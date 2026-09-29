import asyncio
from dotenv import load_dotenv
load_dotenv()

from app.agent import root_agent
from google.adk.runners import InMemoryRunner
from google.genai import types

async def main():
    print("Testing k8s-troubleshooter agent with Firestore tools...")
    prompt = "I have a pod named order-processor stuck in CrashLoopBackOff with exit code 137 on cluster prod-k8s in default namespace. Can you check the runbook, explain what code 137 is, log an incident, and tell me what read-only commands to run?"
    print(f"User Query: {prompt}\n")
    
    runner = InMemoryRunner(agent=root_agent, app_name="k8s_troubleshooter")
    session = await runner.session_service.create_session(
        app_name="k8s_troubleshooter",
        user_id="lead-sre",
    )
    
    user_msg = types.Content(
        role="user",
        parts=[types.Part.from_text(text=prompt)]
    )
    
    response_text = ""
    async for event in runner.run_async(
        session_id=session.id,
        user_id="lead-sre",
        new_message=user_msg,
    ):
        if hasattr(event, "content") and event.content:
            for part in event.content.parts:
                if getattr(part, "text", None):
                    response_text += part.text
                elif getattr(part, "function_call", None):
                    print(f"-> Tool Call: {part.function_call.name}({part.function_call.args})")
                elif getattr(part, "function_response", None):
                    print(f"<- Tool Response: {part.function_response.name}")

    print("\n--- Agent Response ---")
    print(response_text)

if __name__ == "__main__":
    asyncio.run(main())
