import json
import os
import requests
import time
import re
from datetime import datetime

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

    for index, event in enumerate(live_events):
        market_id = str(event.get('id', index))
        title = event.get('title', 'Unknown')
        volume = float(event.get('volume', 0)) / 1000000
        url = f"https://polymarket.com/event/{event.get('slug', '')}"

        # Get Category
        tags = event.get('tags', [])
        category = "MACRO"
        if tags:
            first_tag = tags[0]
            if isinstance(first_tag, dict) and 'label' in first_tag:
                category = str(first_tag['label']).upper().replace(" ", "_")[:10]
            elif isinstance(first_tag, str):
                category = first_tag.upper().replace(" ", "_")[:10]

        prob = 50
        clob_token = None
        markets = event.get('markets', [])
        
        if markets:
            market_data = markets[0]
            
            # --- BULLETPROOF REGEX: PRICE EXTRACTION ---
            # Hunts for any valid float or integer in the raw price string
            prices_raw = str(market_data.get('outcomePrices', '[]'))
            found_prices = re.findall(r'\b(?:0\.\d+|1\.0+|0|1)\b', prices_raw)
            if found_prices:
                valid_prices = [float(p) for p in found_prices]
                prob = int(max(valid_prices) * 100)

            # --- BULLETPROOF REGEX: CLOB TOKEN EXTRACTION ---
            # Hunts strictly for the 0x token needed to pull the history chart
            tokens_raw = str(market_data.get('clobTokenIds', ''))
            token_match = re.search(r'(0x[a-fA-F0-9]+)', tokens_raw)
            if token_match:
                clob_token = token_match.group(1)

        # Fetch CLOB History
        history = []
        if clob_token:
            try:
                clob_url = f"https://clob.polymarket.com/prices-history?market={clob_token}&interval=1d"
                clob_res = requests.get(clob_url, timeout=5)
                if clob_res.status_code == 200:
                    hist_data = clob_res.json().get('history', [])
                    if hist_data:
                        step = max(1, len(hist_data) // 7)
                        history = [int(float(pt['p']) * 100) for pt in hist_data[::step][-7:]]
            except Exception:
                pass
            time.sleep(0.1) 

        if not history:
            history = [prob] * 7
            
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
            "url": url,
            "last_updated": datetime.utcnow().isoformat()
        })

    # Sort by volume
    processed_data = sorted(processed_data, key=lambda x: x['vol'], reverse=True)

    with open(DATA_FILE, 'w') as f:
        json.dump(processed_data, f, indent=2)

if __name__ == "__main__":
    fetch_and_process()
