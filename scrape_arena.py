import requests
import re
import json
import os
from datetime import datetime

# Configuration
HISTORY_FILE = "data/history.json"
os.makedirs("data", exist_ok=True)

def get_latest_data():
    url = "https://arena.ai/leaderboard/code"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Failed to load page: {response.status_code}")

    # Next.js embeds the data in a script tag. We search for the "entries" array.
    # Note: Regex patterns may need slight adjustments if the site updates.
    match = re.search(r'\"entries\":(\[.*?\])', response.text)
    if not match:
        raise Exception("Could not find rankings data in HTML")

    raw_data = json.loads(match.group(1))
    
    # Standardize data format
    return [
        {
            "name": m.get("modelDisplayName") or m.get("model"),
            "score": m.get("rating"),
            "org": m.get("modelOrganization")
        }
        for m in raw_data
    ][:20]  # Keep only top 20 to keep files small

def update_history():
    # 1. Fetch new data
    new_snapshot = get_latest_data()
    today = datetime.now().strftime("%Y-%m-%d")

    # 2. Load existing history
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            history = json.load(f)
    else:
        history = []

    # 3. Append today's data if not already present
    if not any(entry['date'] == today for entry in history):
        history.append({
            "date": today,
            "models": new_snapshot
        })
        
        # Keep only the last 100 days to ensure fast loading
        history = history[-100:]

        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)
        print(f"Updated history for {today}")
    else:
        print("Today's data already exists.")

if __name__ == "__main__":
    update_history()
