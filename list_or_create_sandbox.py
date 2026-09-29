import os
import json
from google import genai

PROJECT_ID = "qwiklabs-gcp-04-e954671c3d10"
LOCATION = "us-east1"
REASONING_ENGINE_ID = "projects/698694960991/locations/us-east1/reasoningEngines/2926440357279301632"

client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

print(f"Listing sandbox environments under {REASONING_ENGINE_ID}...")
try:
    sandboxes = list(client.sandbox_environments.list(parent=REASONING_ENGINE_ID))
    print(f"Found {len(sandboxes)} existing sandbox(es):")
    for s in sandboxes:
        print(f"  - {s.name}")
    if sandboxes:
        selected_sandbox = sandboxes[0].name
    else:
        print("No sandbox found. Creating a new Sandbox Environment...")
        sb = client.sandbox_environments.create(
            parent=REASONING_ENGINE_ID,
            sandbox_environment={
                "display_name": "k8s-troubleshooter-sandbox",
                "description": "Sandbox for analyzing kubectl outputs and manifest linting",
            }
        )
        print(f"Created sandbox: {sb.name}")
        selected_sandbox = sb.name

    print(f"SELECTED_SANDBOX={selected_sandbox}")
except Exception as e:
    print(f"Error checking/creating sandbox: {e}")
