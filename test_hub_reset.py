import qai_hub as hub
import os
from dotenv import load_dotenv

load_dotenv()

token = os.environ.get("QAIHUB_API_TOKEN")
if not token:
    print("QAIHUB_API_TOKEN not found")
    exit(1)

try:
    hub.set_session_token(token)
    print("First set_session_token succeeded")
except Exception as e:
    print(f"First set_session_token failed: {e}")

try:
    hub.set_session_token(token)
    print("Second set_session_token succeeded")
except Exception as e:
    print(f"Second set_session_token failed: {e}")

print("Attempting to reset _global_client...")
if hasattr(hub, 'hub'):
    hub.hub._global_client = None
    # We also need to reset the internal config if possible
    # The error message said "ClientConfig has already been set"
    # Let's see where ClientConfig is.
    try:
        from qai_hub.client import ClientConfig
        # ClientConfig might be a singleton
        print(f"ClientConfig: {ClientConfig}")
    except ImportError:
        print("Could not import ClientConfig")

try:
    hub.set_session_token(token)
    print("Third set_session_token (after reset) succeeded")
except Exception as e:
    print(f"Third set_session_token (after reset) failed: {e}")
