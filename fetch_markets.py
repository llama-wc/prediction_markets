import json
import os
import requests
from datetime import datetime

API_URL = "https://gamma-api.polymarket.com/events?limit=15&active=true&closed=false"
DATA_FILE = "market-data.json"

def fetch_and_process():
    # 1. Load the previous epoch's data to calculate velocity
    old_data = {}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                raw_old = json.load(f)
                # Map old data by ID for quick comparison
                old_data = {item['id']: item for item in raw_old}
        except Exception:
            pass # If the file is corrupted or empty, start fresh

    # 2. Fetch fresh live data
    headers = {"Accept": "application/json"}
    response = requests.get(API_URL, headers=headers)
    live_events = response.json()

    processed_data = []

    # 3. Process and calculate metrics
    for index, event in enumerate(live_events):
        market_id = event.get('id', str(index))
        title = event.get('title', 'Unknown')
        volume = float(event.get('volume', 0)) / 1000000

        # Extract probability
        prob = 50
        if event.get('markets') and len(event['markets']) > 0:
            prices = event['markets'][0].get('outcomePrices', ['0.5', '0.5'])
            prob = int(float(prices[0]) * 100)

        # 4. Cross-reference with old data for Epoch Math
        past_record = old_data.get(market_id, {})
        history = past_record.get('history', [prob] * 7) # Default flat history
        
        # Calculate the 10-minute epoch velocity
        last_prob = history[-1]
        epoch_velocity = prob - last_prob

        # Update the 24H shift (Simulated here, but can be derived from deeper history later)
        shift = past_record.get('shift', 0) + epoch_velocity

        # Cycle the history array (Drop the oldest, append the newest)
        history.pop(0)
        history.append(prob)

        processed_data.append({
            "id": int(market_id) if str(market_id).isdigit() else market_id,
            "category": "MACRO", 
            "market": title,
            "prob": prob,
            "vol": round(volume, 2),
            "shift": shift,
            "epoch_velocity": epoch_velocity,
            "history": history,
            "last_updated": datetime.utcnow().isoformat()
        })

    # Sort by heavy liquidity
    processed_data = sorted(processed_data, key=lambda x: x['vol'], reverse=True)

    # 5. Overwrite the JSON file
    with open(DATA_FILE, 'w') as f:
        json.dump(processed_data, f, indent=2)
    
    print(f"SUCCESS: Processed {len(processed_data)} markets. JSON updated.")

if __name__ == "__main__":
    fetch_and_process()
