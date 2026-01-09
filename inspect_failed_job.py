import qai_hub as hub
import os
from dotenv import load_dotenv

load_dotenv()

token = os.environ.get("QAIHUB_API_TOKEN")
if not token:
    print("QAIHUB_API_TOKEN not found")
    exit(1)

hub.set_session_token(token)

job_id = "jgo3q67kg"
try:
    job = hub.get_job(job_id)
    status = job.get_status()
    print(f"Job ID: {job_id}")
    print(f"Status Code: {status.code}")
    print(f"Status Message: {status.message}")
    print(f"Status State: {status.state}")
    print(f"Status Success: {status.success}")
    print(f"Status Failure: {status.failure}")
    print(f"Status Finished: {status.finished}")
except Exception as e:
    print(f"Error: {e}")
