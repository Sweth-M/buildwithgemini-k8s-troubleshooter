import asyncio
import json
import urllib.request
from dotenv import load_dotenv
load_dotenv()

from app.agent import generate_cluster_topology_diagram
from unittest.mock import AsyncMock

class DummyToolContext:
    def __init__(self):
        self.saved_artifacts = {}

    async def save_artifact(self, filename, artifact):
        print(f"  ✓ ToolContext.save_artifact called: filename='{filename}', mime_type='{artifact.inline_data.mime_type}', bytes={len(artifact.inline_data.data)}")
        self.saved_artifacts[filename] = artifact

async def main():
    print("Testing generate_cluster_topology_diagram...")
    ctx = DummyToolContext()
    res_str = await generate_cluster_topology_diagram(
        scenario="Payment service Pod crashing with OOMKilled under spike traffic",
        failing_component="Pods",
        tool_context=ctx
    )
    
    print("\nTool output:")
    print(res_str)
    
    data = json.loads(res_str)
    assert data.get("success") is True, f"Failed: {data}"
    assert len(ctx.saved_artifacts) == 1, "Artifact was not saved to tool_context!"
    
    public_url = data.get("public_url")
    print(f"\nVerifying public URL over HTTP: {public_url}")
    req = urllib.request.Request(public_url, headers={"User-Agent": "TestCheck/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        print(f"  ✓ HTTP Status: {resp.status}")
        print(f"  ✓ Content-Type: {resp.headers.get('Content-Type')}")
        print(f"  ✓ Content-Length: {resp.headers.get('Content-Length')} bytes")
        assert resp.status == 200

    print("\n✅ Verification PASSED: Image generated, saved to tool_context artifact, uploaded to GCS, and publicly accessible!")

if __name__ == "__main__":
    asyncio.run(main())
