"""
Example script to run EdgeGate ProbeSuite capability discovery.

Usage:
    export QAI_HUB_API_TOKEN="your_token"
    python aihub_probe.py --workspace-id <uuid>
"""

import asyncio
import os
import argparse
import json
from uuid import UUID

from edgegate.aihub.client import QAIHubClient
from edgegate.aihub.probesuite import ProbeSuite

async def main():
    parser = argparse.ArgumentParser(description="Run EdgeGate ProbeSuite")
    parser.add_argument("--workspace-id", required=True, help="EdgeGate Workspace UUID")
    parser.add_argument("--token", help="Qualcomm AI Hub API Token (or set QAI_HUB_API_TOKEN)")
    args = parser.parse_args()

    token = args.token or os.environ.get("QAI_HUB_API_TOKEN")
    if not token:
        print("Error: QAI_HUB_API_TOKEN environment variable or --token argument is required")
        return

    print(f"--- Starting ProbeSuite for Workspace {args.workspace_id} ---")
    
    # Initialize AI Hub Client
    client = QAIHubClient(api_token=token)
    
    # Initialize ProbeSuite
    probe_suite = ProbeSuite(client=client, workspace_id=UUID(args.workspace_id))
    
    try:
        # Run all probes
        print("Running probes (this may take a few minutes)...")
        capabilities = await probe_suite.run_all()
        
        print("\n--- Capability Discovery Complete ---")
        print(f"Supported Devices: {len(capabilities.supported_devices)}")
        print(f"Supported Runtimes: {capabilities.supported_runtimes}")
        
        # Output capabilities to file
        output_file = f"capabilities_{args.workspace_id[:8]}.json"
        with open(output_file, "w") as f:
            json.dump(capabilities.dict(), f, indent=2)
        print(f"\nCapabilities saved to {output_file}")

    except Exception as e:
        print(f"\nError running ProbeSuite: {e}")

if __name__ == "__main__":
    asyncio.run(main())
