import httpx
import datetime
from fastapi import FastAPI, Request, BackgroundTasks
from typing import Dict

app = FastAPI(title="HoneyToken Intelligence Server")

# --- Database Simulation ---
# In a real startup, you'd move this to PostgreSQL or MongoDB
honey_tokens: Dict[str, dict] = {
    "token_123": {
        "owner": "your_email@gmail.com", 
        "filename": "Financial_Report_2026.xlsx",
        "label": "Accounting Dept Laptop"
    },
    "token_456": {
        "owner": "your_email@gmail.com", 
        "filename": "Admin_Passwords.docx",
        "label": "Server Room Backup"
    }
}

async def get_geo_info(ip: str):
    """Fetches City, Region, and Country from an IP address."""
    try:
        async with httpx.AsyncClient() as client:
            # We use ip-api (free for development) to get location data
            response = await client.get(f"http://ip-api.com/json/{ip}")
            data = response.json()
            if data.get("status") == "success":
                return f"{data.get('city')}, {data.get('regionName')}, {data.get('country')}"
    except Exception:
        return "Unknown Location"
    return "Private/Local IP"

async def process_alert(token_id: str, ip: str, user_agent: str):
    """The brain of the operation: Logs and Prepares Alerts."""
    token_data = honey_tokens.get(token_id)
    location = await get_geo_info(ip)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("\n" + "="*40)
    print(f"🚨 ALERT: HONEY TOKEN ACTIVATED 🚨")
    print(f"FILE: {token_data['filename']} ({token_data['label']})")
    print(f"TIME: {timestamp}")
    print(f"LOCATION: {location}")
    print(f"IP ADDRESS: {ip}")
    print(f"DEVICE: {user_agent}")
    print("="*40 + "\n")
    
    # NEXT STEP: This is where you'd call the Phase 3 Email/SMS function
    # send_email_alert(token_data, ip, location, user_agent)

@app.get("/track/{token_id}")
async def track_access(token_id: str, request: Request, background_tasks: BackgroundTasks):
    # 1. Identify the token
    if token_id not in honey_tokens:
        return {"status": "error", "message": "Invalid Token"}

    # 2. Extract Intruder Data
    # Note: If running behind a proxy (like Nginx), use request.headers.get("X-Forwarded-For")
    client_ip = request.client.host
    user_agent = request.headers.get("user-agent", "Unknown Device")

    # 3. Process the Intelligence in the background (so the file opens fast for the hacker)
    background_tasks.add_task(process_alert, token_id, client_ip, user_agent)

    # 4. Return a success response (or a 1x1 transparent pixel)
    return {"status": "ok", "timestamp": datetime.datetime.now()}

if __name__ == "__main__":
    import uvicorn
    # Run on 0.0.0.0 to allow external connections
    uvicorn.run(app, host="0.0.0.0", port=8000)