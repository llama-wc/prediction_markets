import json
import os
import requests
from datetime import datetime

API_URL = "https://gamma-api.polymarket.com/events?limit=15&active=true&closed=false"
DATA_FILE = "market-data.json"

def fetch_and_process():
    old_data = {}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                raw_old = json.load(f)
                old_data = {str(item['id']): item for item in raw_old}
        except Exception:
            pass 

    headers = {"Accept": "application/json"}
    response = requests.get(API_URL, headers=headers)
    live_events = response.json()

    processed_data = []

    for index, event in enumerate(live_events):
        market_id = str(event.get('id', index))
        title = event.get('title', 'Unknown')
        volume = float(event.get('volume', 0)) / 1000000
        
        slug = event.get('slug', '')
        url = f"https://polymarket.com/event/{slug}" if slug else "https://polymarket.com"

        prob = 50
        try:
            markets = event.get('markets', [])
            if markets:
                prices_raw = markets[0].get('outcomePrices')
                if prices_raw:
                    if isinstance(prices_raw, str):
                        try:
                            prices_raw = json.loads(prices_raw.replace("'", '"'))
                        except:
                            prices_raw = prices_raw.strip('][').split(', ')
                    
                    if isinstance(prices_raw, list) and len(prices_raw) > 0:
                        prob = int(float(prices_raw[0]) * 100)
        except Exception:
            pass 

        past_record = old_data.get(market_id, {})
        history = past_record.get('history', [])
        
        # --- THE PURE DATA ENGINE ---
        # If the market is brand new, pad it with the current probability
        if not history:
            history = [prob] * 7
            epoch_velocity = 0
        else:
            # If history exists, calculate the real shift and cycle the array
            last_prob = history[-1]
            epoch_velocity = prob - last_prob
            history.pop(0)
            history.append(prob)

        shift = past_record.get('shift', 0) + epoch_velocity

        processed_data.append({
            "id": market_id,
            "category": "MACRO", 
            "market": title,
            "prob": prob,
            "vol": round(volume, 2),
            "shift": shift,
            "epoch_velocity": epoch_velocity,
            "history": history,
            "url": url,
            "last_updated": datetime.utcnow().isoformat()
        })

    processed_data = sorted(processed_data, key=lambda x: x['vol'], reverse=True)

    with open(DATA_FILE, 'w') as f:
        json.dump(processed_data, f, indent=2)

if __name__ == "__main__":
    fetch_and_process()
