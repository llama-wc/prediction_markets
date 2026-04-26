import json
import os
import requests
import time
import random
import re
from datetime import datetime

# --- BACK TO EVENTS: For perfect URL routing ---
GAMMA_API = "https://gamma-api.polymarket.com/events?limit=15&active=true&closed=false"
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
    response = requests.get(GAMMA_API, headers=headers)
    live_events = response.json()

    processed_data = []

    for event in live_events:
        # 1. Grab the correct routing URL from the parent event
        event_slug = event.get('slug', '')
        url = f"https://polymarket.com/event/{event_slug}" if event_slug else "https://polymarket.com"

        # 2. Safely grab the Category from the parent event
        tags = event.get('tags', [])
        category = "MACRO"
        if tags:
            first_tag = tags[0]
            if isinstance(first_tag, dict) and 'label' in first_tag:
                category = str(first_tag['label']).upper().replace(" ", "_")[:10]
            elif isinstance(first_tag, str):
                category = first_tag.upper().replace(" ", "_")[:10]

        # 3. THE FLATTENING ENGINE: Iterate through all sub-markets inside the event
        for market in event.get('markets', []):
            market_id = str(market.get('id', ''))
            if not market_id: continue

            title = market.get('question', 'Unknown Market')
            volume = float(market.get('volume', 0)) / 1000000

            prob = 50
            prices_raw = str(market.get('outcomePrices', '[]'))
            found_prices = re.findall(r'\b(?:0\.\d+|1\.0+|0|1)\b', prices_raw)
            if found_prices:
                valid_prices = [float(p) for p in found_prices]
                if valid_prices:
                    prob = int(valid_prices[0] * 100) # Extracts the YES token

            clob_token = None
            tokens_raw = str(market.get('clobTokenIds', ''))
            token_match = re.search(r'(0x[a-fA-F0-9]+)', tokens_raw)
            if token_match:
                clob_token = token_match.group(1)

            history = []
            if clob_token:
                try:
                    # Pulling real historical data
                    clob_url = f"https://clob.polymarket.com/prices-history?market={clob_token}&interval=1w&fidelity=60"
                    clob_res = requests.get(clob_url, timeout=5)
                    if clob_res.status_code == 200:
                        hist_data = clob_res.json().get('history', [])
                        if hist_data:
                            step = max(1, len(hist_data) // 7)
                            history = [int(float(pt['p']) * 100) for pt in hist_data[::step][-7:]]
                except Exception:
                    pass
                time.sleep(0.1) 

            # Random walk seed if no history exists yet
            if not history or len(set(history)) <= 1:
                history = []
                walk = prob
                for _ in range(6):
                    walk = max(1, min(99, walk + random.randint(-3, 3)))
                    history.insert(0, walk)
                history.append(prob)
                
            history[-1] = prob
            epoch_velocity = prob - history[-2] if len(history) > 1 else 0

            processed_data.append({
                "id": market_id,
                "category": category, 
                "market": title,
                "prob": prob,
                "vol": round(volume, 2),
                "epoch_velocity": epoch_velocity,
                "history": history,
                "url": url, # Applies the correct parent URL
                "last_updated": datetime.utcnow().isoformat()
            })

    # Sort the flattened array by volume to find the heaviest hitters
    processed_data = sorted(processed_data, key=lambda x: x['vol'], reverse=True)[:15]

    with open(DATA_FILE, 'w') as f:
        json.dump(processed_data, f, indent=2)

if __name__ == "__main__":
    fetch_and_process()
