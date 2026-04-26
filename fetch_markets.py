import json
import os
import requests
import time
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
        
        slug = event.get('slug', '')
        url = f"https://polymarket.com/event/{slug}" if slug else "https://polymarket.com"

        tags = event.get('tags', [])
        category = "MISC"
        if tags:
            category = str(tags[0]).upper().replace(" ", "_")[:10]

        prob = 50
        clob_token = None
        markets = event.get('markets', [])
        
        if markets:
            market_data = markets[0]
            
            prices_raw = market_data.get('outcomePrices')
            if isinstance(prices_raw, str):
                try: prices_raw = json.loads(prices_raw.replace("'", '"'))
                except: prices_raw = prices_raw.strip('][').split(', ')
            
            if isinstance(prices_raw, list) and len(prices_raw) > 0:
                # FIX: Extract the leading probability (The "Favorite")
                valid_prices = [float(p) for p in prices_raw if str(p).replace('.','',1).isdigit()]
                if valid_prices:
                    prob = int(max(valid_prices) * 100)
            
            tokens_raw = market_data.get('clobTokenIds')
            if isinstance(tokens_raw, str):
                try: tokens_raw = json.loads(tokens_raw.replace("'", '"'))
                except: tokens_raw = tokens_raw.strip('][').split(', ')
            if isinstance(tokens_raw, list) and len(tokens_raw) > 0:
                clob_token = tokens_raw[0]

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

    processed_data = sorted(processed_data, key=lambda x: x['vol'], reverse=True)

    with open(DATA_FILE, 'w') as f:
        json.dump(processed_data, f, indent=2)

if __name__ == "__main__":
    fetch_and_process()
