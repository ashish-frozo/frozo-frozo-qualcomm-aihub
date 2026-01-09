import qai_hub as hub
import os
from dotenv import load_dotenv

load_dotenv()

token = os.environ.get("QAIHUB_API_TOKEN")
if not token:
    print("QAIHUB_API_TOKEN not found")
    exit(1)

print(f"hub.hub._Client: {hub.hub._Client}")
try:
    client = hub.hub._Client(api_token=token)
    print("Successfully instantiated hub.hub._Client")
    print(f"Client attributes: {dir(client)}")
    
    # Try to use the client to list devices
    devices = client.get_devices()
    print(f"Successfully listed {len(devices)} devices using direct client")
except Exception as e:
    print(f"Failed to instantiate or use hub.hub._Client: {e}")

# Check if hub.submit_compile_job can take a client
import inspect
print(f"hub.submit_compile_job signature: {inspect.signature(hub.submit_compile_job)}")
