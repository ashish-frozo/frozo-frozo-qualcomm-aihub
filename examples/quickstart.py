"""
EdgeGate QuickStart - End-to-End Consumer Flow Example.

This script demonstrates how a consumer would use the EdgeGate API:
1. Register and Login
2. Create a Workspace
3. Connect AI Hub (Mock)
4. Run Capability Discovery (Probe)
5. Create a PromptPack
6. Create a Pipeline
7. Upload a Model and Trigger a Run
"""

import httpx
import time
import uuid
import json
import os
from datetime import datetime

BASE_URL = "http://localhost:8000"
EMAIL = f"consumer_{uuid.uuid4().hex[:6]}@example.com"
PASSWORD = "secure_password_123"
QAIHUB_TOKEN = os.getenv("QAIHUB_API_TOKEN", "mock_token_for_testing")

def print_step(msg):
    print(f"\n--- {msg} ---")

def main():
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        # 1. Register
        print_step(f"1. Registering user: {EMAIL}")
        resp = client.post("/v1/auth/register", json={"email": EMAIL, "password": PASSWORD})
        resp.raise_for_status()
        user = resp.json()
        print(f"User created: {user['id']}")

        # 2. Login
        print_step("2. Logging in")
        resp = client.post("/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
        resp.raise_for_status()
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("Login successful, token acquired.")

        # 3. Create Workspace
        print_step("3. Creating Workspace")
        resp = client.post("/v1/workspaces", json={"name": "Robotics Fleet A"}, headers=headers)
        resp.raise_for_status()
        workspace = resp.json()
        ws_id = workspace["id"]
        print(f"Workspace created: {workspace['name']} ({ws_id})")

        # 4. Connect AI Hub (Mock)
        print_step("4. Connecting AI Hub Integration")
        # In this environment, we use a mock token unless QAIHUB_API_TOKEN is set
        resp = client.post(
            f"/v1/workspaces/{ws_id}/integrations/qaihub",
            json={"token": QAIHUB_TOKEN},
            headers=headers
        )
        resp.raise_for_status()
        print("AI Hub integration connected.")

        # 5. Run Capability Discovery
        print_step("5. Running Capability Discovery (Probe)")
        use_mock = "true" if QAIHUB_TOKEN == "mock_token_for_testing" else "false"
        resp = client.post(f"/v1/workspaces/{ws_id}/capabilities/probe?use_mock={use_mock}", headers=headers)
        resp.raise_for_status()
        print("Probe task submitted to Celery.")
        
        # Wait a bit for the mock probe to complete
        print("Waiting for probe results...")
        time.sleep(2)
        
        resp = client.get(f"/v1/workspaces/{ws_id}/capabilities", headers=headers)
        resp.raise_for_status()
        caps = resp.json()
        print(f"Discovered {len(caps)} capabilities.")

        # 6. Create a PromptPack
        print_step("6. Creating a PromptPack")
        promptpack_id = f"vision-qa-{uuid.uuid4().hex[:4]}"
        resp = client.post(
            f"/v1/workspaces/{ws_id}/promptpacks",
            json={
                "promptpack_id": promptpack_id,
                "version": "1.0.0",
                "content": {
                    "promptpack_id": promptpack_id,
                    "version": "1.0.0",
                    "name": "Vision QA Suite",
                    "cases": [
                        {
                            "case_id": "detect_object",
                            "name": "Detect Robot",
                            "prompt": "What is in this image?",
                            "expected": {"type": "exact", "text": "robot"}
                        }
                    ]
                }
            },
            headers=headers
        )
        resp.raise_for_status()
        print(f"PromptPack '{promptpack_id}' created.")

        # 6.5 Publish the PromptPack (Required for Pipelines)
        print_step("6.5 Publishing the PromptPack")
        resp = client.put(f"/v1/workspaces/{ws_id}/promptpacks/{promptpack_id}/1.0.0/publish", headers=headers)
        resp.raise_for_status()
        print("PromptPack published.")

        # 7. Create a Pipeline
        print_step("7. Creating a Pipeline")
        resp = client.post(
            f"/v1/workspaces/{ws_id}/pipelines",
            json={
                "name": "Production Gate - RB5",
                "promptpack_ref": {
                    "promptpack_id": promptpack_id,
                    "version": "1.0.0"
                },
                "device_matrix": [
                    {"name": "Samsung Galaxy S23", "enabled": True},
                    {"name": "RB5", "enabled": True}
                ],
                "gates": [
                    {"metric": "inference_time_ms", "operator": "lte", "threshold": 150.0},
                    {"metric": "cpu_compute_percent", "operator": "lte", "threshold": 50.0}
                ]
            },
            headers=headers
        )
        resp.raise_for_status()
        pipeline = resp.json()
        pipe_id = pipeline["id"]
        print(f"Pipeline created: {pipeline['name']} ({pipe_id})")

        # 8. Upload Model and Trigger Run
        print_step("8. Triggering a Test Run")
        # First, we need a model artifact. In a real scenario, you'd upload a file.
        # Here we'll just create a dummy artifact entry for demonstration.
        # Note: In the real API, you'd use POST /v1/workspaces/{ws_id}/artifacts
        
        # For this quickstart, we'll assume the user has a model.onnx
        # We'll mock the upload by creating a run with a random UUID for now 
        # (The service will fail if it can't find the artifact, so let's create it)
        
        with open("edgegate/probe_models/torch/model.pt", "rb") as f:
            resp = client.post(
                f"/v1/workspaces/{ws_id}/artifacts",
                data={"artifact_type": "model_torchscript"},
                files={"file": ("model.pt", f)},
                headers=headers
            )
        resp.raise_for_status()
        artifact = resp.json()
        art_id = artifact["id"]
        print(f"Model artifact uploaded: {art_id}")

        resp = client.post(
            f"/v1/workspaces/{ws_id}/runs",
            json={
                "pipeline_id": pipe_id,
                "model_artifact_id": art_id,
                "trigger": "manual"
            },
            headers=headers
        )
        resp.raise_for_status()
        run = resp.json()
        run_id = run["id"]
        print(f"Run triggered! ID: {run_id}")

        # 9. Check Status
        print_step("9. Checking Run Status")
        for _ in range(5):
            resp = client.get(f"/v1/workspaces/{ws_id}/runs/{run_id}", headers=headers)
            resp.raise_for_status()
            status_data = resp.json()
            print(f"Current Status: {status_data['status']}")
            if status_data['status'] in ['passed', 'failed', 'error']:
                break
            time.sleep(2)

        print("\nQuickStart completed successfully!")
        print(f"View your run at: {BASE_URL}/v1/workspaces/{ws_id}/runs/{run_id}")

if __name__ == "__main__":
    main()
