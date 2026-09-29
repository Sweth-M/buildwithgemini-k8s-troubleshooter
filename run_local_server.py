from dotenv import load_dotenv
load_dotenv()

import uvicorn
from app.fast_api_app import app

if __name__ == "__main__":
    print("Starting k8s-troubleshooter local server on port 8081...", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=8081)
