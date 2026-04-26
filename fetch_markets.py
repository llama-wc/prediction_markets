import json
import os
import requests
import time
import re
from datetime import datetime

# --- THE FIX: Pointing to exact binary Markets instead of broad Events ---
GAMMA_API = "https://gamma-api.polymarket.com/markets?limit=30&active=true&closed=false"
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
    live_markets = response.json()

    processed_data = []

    for market in live_markets:
        market_id = str(market.get('id', ''))
        if not market_id: continue
        
        # Grab the specific binary question, not the umbrella event
        title = market.get('question', 'Unknown Market')
        volume = float(market.get('volume', 0)) / 1000000
        
        slug = market.get('slug', '')
        url = f"https://polymarket.com/event/{slug}" if slug else "https://polymarket.com"

        tags = market.get('tags', [])
        category = "MACRO"
        if tags and len(tags) > 0:
            category = str(tags[0]).upper().replace(" ", "_")[:10]

        prob = 50
        prices_raw = str(market.get('outcomePrices', '[]'))
        found_prices = re.findall(r'\b(?:0\.\d+|1\.0+|0|1)\b', prices_raw)
        if found_prices:
            valid_prices = [float(p) for p in found_prices]
            if valid_prices:
                # Track the "YES" price specifically for accurate sentiment
                prob = int(valid_prices[0] * 100)

        clob_token = None
        tokens_raw = str(market.get('clobTokenIds', ''))
        token_match = re.search(r'(0x[a-fA-F0-9]+)', tokens_raw)
        if token_match:
            clob_token = token_match.group(1)

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

    # Sort by volume and keep the top 15 most active specific markets
    processed_data = sorted(processed_data, key=lambda x: x['vol'], reverse=True)[:15]

    with open(DATA_FILE, 'w') as f:
        json.dump(processed_data, f, indent=2)

if __name__ == "__main__":
    fetch_and_process()
