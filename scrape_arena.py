import requests
import re
import json
import os
from datetime import datetime

# Configuration
HISTORY_FILE = "data/history.json"
os.makedirs("data", exist_ok=True)

def get_latest_data():
    # Use the specific 'code' leaderboard URL
    url = "https://arena.ai/leaderboard/code"
    
    # Modern headers to avoid being flagged as a bot
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    response = requests.get(url, headers=headers, timeout=15)
    if response.status_code != 200:
        raise Exception(f"Failed to load page: {response.status_code}")

    # FIX: Robust regex to handle both \"entries\": and "entries":
    # It looks for the start of the 'entries' array and captures everything until the closing bracket.
    match = re.search(r'\\?"entries\\?":\s*(\[.*?\])(?:\\?",|\\?"}|,|})', response.text)
    if not match:
        # Debugging: Write HTML to a file if it fails so you can inspect it in GitHub Actions
        with open("debug_page.html", "w", encoding="utf-8") as f:
            f.write(response.text)
        raise Exception("Could not find rankings data in HTML. Check debug_page.html.")

    json_str = match.group(1)
    
    # CLEANUP: If the JSON is escaped (contains \"), unescape it for the JSON parser
    if '\\"' in json_str:
        json_str = json_str.replace('\\"', '"')

    try:
        raw_data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse JSON: {e}")
    
    # Standardize data format based on current site structure
    standardized = []
    for m in raw_data:
        # Use modelDisplayName as the primary name
        name = m.get("modelDisplayName") or m.get("model")
        score = m.get("rating")
        org = m.get("modelOrganization")
        
        if name and score:
            standardized.append({
                "name": name,
                "score": round(float(score), 1),
                "org": org
            })
            
    return standardized[:25] # Keep Top 25

def update_history():
    try:
        new_snapshot = get_latest_data()
        today = datetime.now().strftime("%Y-%m-%d")

        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                history = json.load(f)
        else:
            history = []

        # Prevent duplicate entries for the same day
        if not any(entry['date'] == today for entry in history):
            history.append({
                "date": today,
                "models": new_snapshot
            })
            
            # Keep only last 100 snapshots
            history = history[-100:]

            with open(HISTORY_FILE, "w") as f:
                json.dump(history, f, indent=2)
            print(f"Successfully updated history for {today}")
        else:
            print("Snapshot for today already exists.")
            
    except Exception as e:
        print(f"Error during update: {e}")
        raise # Re-raise to ensure the GitHub Action shows as 'Failed'

if __name__ == "__main__":
    update_history()
