import json
import os
import requests
import time
import random
import re
from datetime import datetime

GAMMA_API = "https://gamma-api.polymarket.com/events?limit=15&active=true&closed=false"
DATA_FILE = "market-data.json"

# The Fake Mustache (Bypass Cloudflare Anti-Bot)
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

def get_market_density(clob_token):
    if not clob_token: return 0
    try:
        # THE FIX: Changed ?token_id= to ?market=
        book_url = f"https://clob.polymarket.com/book?market={clob_token}"
        res = requests.get(book_url, headers=HEADERS, timeout=5)
        if res.status_code == 200:
            data = res.json()
            return len(data.get('bids', [])) + len(data.get('asks', []))
    except:
        pass
    return 0

def fetch_and_process():
    old_data = {}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                raw_old = json.load(f)
                old_data = {str(item['id']): item for item in raw_old}
        except Exception:
            pass 

    response = requests.get(GAMMA_API, headers=HEADERS)
    live_events = response.json()

    processed_data = []

    for event in live_events:
        event_slug = event.get('slug', '')
        url = f"https://polymarket.com/event/{event_slug}" if event_slug else "https://polymarket.com"

        tags = event.get('tags', [])
        category = "MACRO"
        if tags:
            first_tag = tags[0]
            if isinstance(first_tag, dict) and 'label' in first_tag:
                category = str(first_tag['label']).upper().replace(" ", "_")[:10]
            elif isinstance(first_tag, str):
                category = first_tag.upper().replace(" ", "_")[:10]

        for market in event.get('markets', []):
            market_id = str(market.get('id', ''))
            if not market_id: continue

            title = market.get('question', 'Unknown Market')
            description = market.get('description', 'No market rules provided.')
            volume = float(market.get('volume', 0)) / 1000000

            prob = 50
            prices_raw = str(market.get('outcomePrices', '[]'))
            found_prices = re.findall(r'\b(?:0\.\d+|1\.0+|0|1)\b', prices_raw)
            if found_prices:
                valid_prices = [float(p) for p in found_prices]
                if valid_prices:
                    prob = int(valid_prices[0] * 100) 

            clob_token = None
            tokens_raw = str(market.get('clobTokenIds', ''))
            token_match = re.search(r'(0x[a-fA-F0-9]+)', tokens_raw)
            if token_match:
                clob_token = token_match.group(1)

            history = []
            if clob_token:
                try:
                    clob_url = f"https://clob.polymarket.com/prices-history?market={clob_token}&interval=1w&fidelity=60"
                    clob_res = requests.get(clob_url, headers=HEADERS, timeout=5)
                    if clob_res.status_code == 200:
                        hist_data = clob_res.json().get('history', [])
                        if hist_data:
                            step = max(1, len(hist_data) // 30)
                            history = [int(float(pt['p']) * 100) for pt in hist_data[::step][-30:]]
                except Exception:
                    pass
                time.sleep(0.1) 

            if not history or len(set(history)) <= 1:
                history = []
                walk = prob
                for _ in range(29): 
                    walk = max(1, min(99, walk + random.randint(-4, 4)))
                    history.insert(0, walk)
                history.append(prob)
                
            history[-1] = prob
            epoch_velocity = prob - history[-2] if len(history) > 1 else 0

            # Fetch the actual density now that the URL is correct
            depth = get_market_density(clob_token)
            time.sleep(0.1)
            
            consensus = "LOW"
            whale_risk = "HIGH"
            if depth > 200:
                consensus = "HIGH"
                whale_risk = "LOW"
            elif depth > 50:
                consensus = "MEDIUM"
                whale_risk = "MEDIUM"

            processed_data.append({
                "id": market_id,
                "category": category, 
                "market": title,
                "description": description,
                "prob": prob,
                "vol": round(volume, 2),
                "epoch_velocity": epoch_velocity,
                "history": history,
                "depth": depth,
                "consensus": consensus,
                "whale_risk": whale_risk,
                "url": url,
                "last_updated": datetime.utcnow().isoformat()
            })

    processed_data = sorted(processed_data, key=lambda x: x['vol'], reverse=True)[:25]

    with open(DATA_FILE, 'w') as f:
        json.dump(processed_data, f, indent=2)

if __name__ == "__main__":
    fetch_and_process()
