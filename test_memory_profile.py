import asyncio
from dotenv import load_dotenv
load_dotenv()

from app.agent import root_agent
from google.adk.runners import InMemoryRunner
from google.genai import types

async def main():
    print("Testing k8s cluster profile tracking in agent instructions...")
    prompt = """Hi SRE, for future reference our primary cluster is 'prod-gke-east', running GKE v1.29 with containerd as the container runtime. Our default workload namespace is 'payments', and we have a recurring issue where payment-worker pods hit sudden OOMKills during end-of-month reconciliation. Please confirm what you will remember."""

    runner = InMemoryRunner(agent=root_agent, app_name="k8s_troubleshooter")
    session = await runner.session_service.create_session(
        app_name="k8s_troubleshooter",
        user_id="test-cluster-admin",
    )
    
    user_msg = types.Content(
        role="user",
        parts=[types.Part.from_text(text=prompt)]
    )
    
    response_text = ""
    async for event in runner.run_async(
        session_id=session.id,
        user_id="test-cluster-admin",
        new_message=user_msg,
    ):
        if hasattr(event, "content") and event.content:
            for part in event.content.parts:
                if getattr(part, "text", None):
                    response_text += part.text

    print("\n--- Agent Response ---")
    print(response_text)

if __name__ == "__main__":
    asyncio.run(main())
