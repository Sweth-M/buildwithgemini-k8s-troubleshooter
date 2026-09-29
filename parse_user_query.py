import asyncio
from dotenv import load_dotenv
load_dotenv()

from app.agent import root_agent
from google.adk.runners import InMemoryRunner
from google.genai import types

async def main():
    prompt = """Here's my kubectl get pods output. What's wrong?

NAME                          READY   STATUS             RESTARTS       AGE
api-7d9f8b6c5d-x2k4p          0/1     CrashLoopBackOff   7 (2m ago)     18m
api-7d9f8b6c5d-q8n1z          1/1     Running            0              18m
worker-5c6b7d8f9-lm3tq        0/1     CrashLoopBackOff   4 (45s ago)    12m
frontend-6f8d9c7b4-zp2wr      0/1     ImagePullBackOff   0              5m
redis-0                       1/1     Running            0              2d"""

    runner = InMemoryRunner(agent=root_agent, app_name="k8s_troubleshooter")
    session = await runner.session_service.create_session(
        app_name="k8s_troubleshooter",
        user_id="user-triage",
    )
    
    user_msg = types.Content(
        role="user",
        parts=[types.Part.from_text(text=prompt)]
    )
    
    response_text = ""
    async for event in runner.run_async(
        session_id=session.id,
        user_id="user-triage",
        new_message=user_msg,
    ):
        if hasattr(event, "content") and event.content:
            for part in event.content.parts:
                if getattr(part, "text", None):
                    response_text += part.text

    print(response_text)

if __name__ == "__main__":
    asyncio.run(main())
