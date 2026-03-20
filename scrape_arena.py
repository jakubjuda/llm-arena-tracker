import requests
import re
import json
import os
from datetime import datetime

FILE_NAME = "history.json"

def scrape_arena_html():
    url = "https://arena.ai/leaderboard/code"
    # Spoofing a standard browser so they don't block the Python request
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    
    print("Fetching HTML...")
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"Failed to fetch page: {response.status_code}")
        return

    html_content = response.text
    
    # 1. Use Regex to find the embedded JSON array
    # We look for "entries":[ ... ] followed by ,"voteCutoffISOString"
    match = re.search(r'"entries":(\[.*?\]),"voteCutoffISOString"', html_content)
    
    if not match:
        print("Could not find the 'entries' data in the HTML. The site structure may have changed.")
        return
        
    raw_json_string = match.group(1)
    
    try:
        # 2. Parse the extracted string into a Python list of dictionaries
        models_data = json.loads(raw_json_string)
        print(f"Success! Extracted {len(models_data)} models.")
        
        # 3. Clean up the data to keep our history file small
        clean_ranking = []
        for model in models_data:
            clean_ranking.append({
                "rank": model.get("rank"),
                "name": model.get("modelDisplayName"),
                "score": model.get("rating"),
                "organization": model.get("modelOrganization")
            })
            
        # 4. Save to history.json (Append Mode)
        update_history(clean_ranking)
        
    except json.JSONDecodeError:
        print("Failed to decode the JSON. The regex might have captured broken data.")

def update_history(new_data):
    if os.path.exists(FILE_NAME):
        with open(FILE_NAME, "r") as f:
            try:
                history = json.load(f)
            except json.JSONDecodeError:
                history = []
    else:
        history = []

    today = datetime.now().strftime("%Y-%m-%d")
    
    # Avoid duplicate entries for the same day
    if not any(entry['date'] == today for entry in history):
        history.append({
            "date": today,
            "data": new_data
        })
        
        with open(FILE_NAME, "w") as f:
            json.dump(history, f, indent=2)
        print("History updated successfully!")
    else:
        print("Data for today already exists. Skipping.")

if __name__ == "__main__":
    scrape_arena_html()
