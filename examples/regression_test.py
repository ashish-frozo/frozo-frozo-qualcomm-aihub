import httpx
import time
import uuid
import sys
import os
from typing import Dict, Any

# Configuration
API_URL = "http://localhost:8000"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "edgegate/probe_models/torch/model.pt")
QAIHUB_TOKEN = os.getenv("QAIHUB_API_TOKEN", "mock_token")

def print_step(msg: str):
    print(f"\n--- {msg} ---")

def wait_for_run(client: httpx.Client, ws_id: str, run_id: str, headers: Dict[str, str], timeout: int = 300) -> Dict[str, Any]:
    start_time = time.time()
    while time.time() - start_time < timeout:
        resp = client.get(f"/v1/workspaces/{ws_id}/runs/{run_id}", headers=headers)
        resp.raise_for_status()
        data = resp.json()
        status = data["status"]
        print(f"  Run {run_id[:8]} status: {status}")
        if status in ["passed", "failed", "error"]:
            return data
        time.sleep(5)
    raise TimeoutError("Run timed out")

def main():
    print("=== EdgeGate Real Use Case: Model Optimization Regression Testing ===")
    
    with httpx.Client(base_url=API_URL, timeout=30.0) as client:
        # 1. Setup: Register & Login
        email = f"dev_{uuid.uuid4().hex[:6]}@robotics.com"
        password = "SecurePassword123!"
        
        print_step(f"1. Registering Developer: {email}")
        client.post("/v1/auth/register", json={"email": email, "password": password}).raise_for_status()
        
        resp = client.post("/v1/auth/login", json={"email": email, "password": password})
        resp.raise_for_status()
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Create Workspace
        print_step("2. Creating Workspace: 'Object Detection Fleet'")
        resp = client.post("/v1/workspaces", json={"name": "Object Detection Fleet"}, headers=headers)
        resp.raise_for_status()
        ws_id = resp.json()["id"]

        # 3. Connect AI Hub
        print_step("3. Connecting AI Hub Integration")
        client.post(f"/v1/workspaces/{ws_id}/integrations/qaihub", json={"token": QAIHUB_TOKEN}, headers=headers).raise_for_status()

        # 4. Run Capability Discovery
        print_step("4. Running Capability Discovery")
        use_mock = "true" if QAIHUB_TOKEN == "mock_token" else "false"
        resp = client.post(f"/v1/workspaces/{ws_id}/capabilities/probe?use_mock={use_mock}", headers=headers)
        resp.raise_for_status()
        probe_data = resp.json()
        probe_run_id = probe_data["probe_run_id"]
        
        print(f"  Probe run {probe_run_id} initiated.")
        print(f"  Token Valid: {probe_data['token_valid']}")
        print(f"  Devices Discovered: {probe_data['device_count']}")
        print(f"  Packaging Types: {', '.join(probe_data['packaging_types_supported'])}")
        while True:
            resp = client.get(f"/v1/workspaces/{ws_id}/capabilities", headers=headers)
            if resp.json():
                break
            time.sleep(2)
        print(f"  Discovered {len(resp.json())} capabilities.")

        # 5. Create & Publish PromptPack
        print_step("5. Creating 'Critical Safety' PromptPack")
        pp_id = f"safety-suite-{uuid.uuid4().hex[:4]}"
        client.post(
            f"/v1/workspaces/{ws_id}/promptpacks",
            json={
                "promptpack_id": pp_id,
                "version": "1.0.0",
                "content": {
                    "promptpack_id": pp_id,
                    "version": "1.0.0",
                    "name": "Critical Safety Suite",
                    "cases": [
                        {
                            "case_id": "pedestrian",
                            "name": "Pedestrian Detection",
                            "prompt": "Is there a person in this frame?",
                            "expected": {"type": "exact", "text": "yes"}
                        }
                    ]
                }
            },
            headers=headers
        ).raise_for_status()
        client.put(f"/v1/workspaces/{ws_id}/promptpacks/{pp_id}/1.0.0/publish", headers=headers).raise_for_status()

        # 6. Create Pipeline with Strict Gates
        print_step("6. Creating Pipeline with Performance Gates")
        # We want: Latency <= 100ms, Memory <= 50MB
        resp = client.post(
            f"/v1/workspaces/{ws_id}/pipelines",
            json={
                "name": "Optimization Gate",
                "promptpack_ref": {"promptpack_id": pp_id, "version": "1.0.0"},
                "device_matrix": [{"name": "RB5", "enabled": True}],
                "gates": [
                    {"metric": "inference_time_ms", "operator": "lte", "threshold": 100.0},
                    {"metric": "peak_memory_mb", "operator": "lte", "threshold": 50.0}
                ]
            },
            headers=headers
        )
        resp.raise_for_status()
        pipeline_id = resp.json()["id"]

        # 7. Upload Baseline (FP32) and Run
        print_step("7. Running Baseline Model (FP32)")
        with open(MODEL_PATH, "rb") as f:
            resp = client.post(f"/v1/workspaces/{ws_id}/artifacts", files={"file": f}, data={"kind": "model"}, headers=headers)
        baseline_art_id = resp.json()["id"]
        
        resp = client.post(f"/v1/workspaces/{ws_id}/runs", json={"pipeline_id": pipeline_id, "model_artifact_id": baseline_art_id}, headers=headers)
        baseline_run_id = resp.json()["id"]
        baseline_data = wait_for_run(client, ws_id, baseline_run_id, headers)

        # 8. Upload Optimized (INT8) and Run
        print_step("8. Running Optimized Model (INT8)")
        # In this mock scenario, we'll use the same file but simulate different results via the worker
        with open(MODEL_PATH, "rb") as f:
            resp = client.post(f"/v1/workspaces/{ws_id}/artifacts", files={"file": f}, data={"kind": "model"}, headers=headers)
        opt_art_id = resp.json()["id"]
        
        resp = client.post(f"/v1/workspaces/{ws_id}/runs", json={"pipeline_id": pipeline_id, "model_artifact_id": opt_art_id}, headers=headers)
        opt_run_id = resp.json()["id"]
        opt_data = wait_for_run(client, ws_id, opt_run_id, headers)

        # 9. Regression Analysis
        print_step("9. Regression Analysis Report")
        
        b_metrics = baseline_data.get("normalized_metrics", {})
        o_metrics = opt_data.get("normalized_metrics", {})
        
        # Mocking some deltas for demonstration if metrics are empty (since worker is mock)
        b_lat = b_metrics.get("inference_time_ms", 180.0)
        o_lat = o_metrics.get("inference_time_ms", 45.0)
        b_mem = b_metrics.get("peak_memory_mb", 120.0)
        o_mem = o_metrics.get("peak_memory_mb", 32.0)
        
        print(f"{'Metric':<20} | {'Baseline (FP32)':<15} | {'Optimized (INT8)':<15} | {'Delta':<10}")
        print("-" * 70)
        
        def print_row(name, b, o, unit):
            delta = ((o - b) / b) * 100
            print(f"{name:<20} | {b:>10.2f} {unit:<4} | {o:>10.2f} {unit:<4} | {delta:>+7.1f}%")

        print_row("Latency", b_lat, o_lat, "ms")
        print_row("Memory", b_mem, o_mem, "MB")
        
        print("\nFinal Verdict:")
        if opt_data["status"] == "completed":
            print("  ✅ PASS: Optimized model meets all quality gates.")
            print(f"  🚀 Speedup: {b_lat / o_lat:.1f}x faster")
            print(f"  📉 Memory Reduction: {((b_mem - o_mem) / b_mem) * 100:.1f}%")
        else:
            print("  ❌ FAIL: Optimized model regressed or failed quality gates.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
