import qai_hub as hub
import os
from dotenv import load_dotenv

load_dotenv()

token = os.environ.get("QAIHUB_API_TOKEN")
if not token:
    print("QAIHUB_API_TOKEN not found")
    exit(1)

print(f"Attributes of hub: {dir(hub)}")
if hasattr(hub, 'hub'):
    print(f"Attributes of hub.hub: {dir(hub.hub)}")

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
    print(f"Error type: {type(e)}")

# Check if there is any way to get the token
if hasattr(hub, 'get_session_token'):
    print(f"get_session_token(): {hub.get_session_token()}")
