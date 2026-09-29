import asyncio
from dotenv import load_dotenv
load_dotenv()

from app.agent import root_agent
from google.adk.runners import InMemoryRunner
from google.genai import types

async def main():
    print("Testing A2UI emission from root_agent...")
    prompt = "Show me an overview card of our cluster health and recent incident for payment-worker."

    runner = InMemoryRunner(agent=root_agent, app_name="k8s_troubleshooter")
    session = await runner.session_service.create_session(
        app_name="k8s_troubleshooter",
        user_id="sre-user",
    )
    
    user_msg = types.Content(
        role="user",
        parts=[types.Part.from_text(text=prompt)]
    )
    
    response_text = ""
    async for event in runner.run_async(
        session_id=session.id,
        user_id="sre-user",
        new_message=user_msg,
    ):
        if hasattr(event, "content") and event.content:
            for part in event.content.parts:
                if getattr(part, "text", None):
                    response_text += part.text

    print("\n--- Event Output Snippet (first 500 chars) ---")
    print(response_text[:500])
    if "a2ui" in response_text.lower() or "surfaceupdate" in response_text.lower():
        print("\nSUCCESS: A2UI payload detected in agent output!")
    else:
        print("\nOutput produced without errors.")

if __name__ == "__main__":
    asyncio.run(main())
