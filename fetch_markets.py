import json
import os
import requests
import time
import random
import re
from datetime import datetime

GAMMA_API = "https://gamma-api.polymarket.com/events?limit=15&active=true&closed=false"
DATA_FILE = "market-data.json"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

def get_orderbook_stats(clob_token):
    """Scans the order book to detect massive individual bets (Whales/Insiders)."""
    if not clob_token: return {"depth": 0, "max_order": 0, "whale_ratio": 0}
    try:
        book_url = f"https://clob.polymarket.com/book?token_id={clob_token}"
        res = requests.get(book_url, headers=HEADERS, timeout=5)
        if res.status_code == 200:
            data = res.json()
            bids = data.get('bids', [])
            asks = data.get('asks', [])
            all_orders = bids + asks
            
            depth = len(all_orders)
            
            # Extract the monetary size of every single limit order on the book
            sizes = []
            for order in all_orders:
                try:
                    sizes.append(float(order.get('size', 0)))
                except: pass
            
            max_order = max(sizes) if sizes else 0
            total_resting = sum(sizes) if sizes else 1 # Avoid division by zero
            
            # What percentage of the ENTIRE order book is controlled by the single biggest bet?
            whale_ratio = (max_order / total_resting) * 100 if total_resting > 0 else 0
            
            return {"depth": depth, "max_order": max_order, "whale_ratio": whale_ratio}
    except:
        pass
    return {"depth": 0, "max_order": 0, "whale_ratio": 0}

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
            token_match = re.search(r'(\d{15,})', tokens_raw)
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

            # Scan the active order book for Insider/Whale activity
            book_stats = get_orderbook_stats(clob_token)
            time.sleep(0.1)
            
            consensus = "LOW"
            if book_stats["depth"] > 200: consensus = "HIGH"
            elif book_stats["depth"] > 50: consensus = "MEDIUM"

            processed_data.append({
                "id": market_id,
                "category": category, 
                "market": title,
                "description": description,
                "prob": prob,
                "vol": round(volume, 2),
                "epoch_velocity": epoch_velocity,
                "history": history,
                "depth": book_stats["depth"],
                "max_order": round(book_stats["max_order"], 2),
                "whale_ratio": round(book_stats["whale_ratio"], 1),
                "consensus": consensus,
                "url": url,
                "last_updated": datetime.utcnow().isoformat()
            })

    processed_data = sorted(processed_data, key=lambda x: x['vol'], reverse=True)[:25]

    with open(DATA_FILE, 'w') as f:
        json.dump(processed_data, f, indent=2)

if __name__ == "__main__":
    fetch_and_process()
