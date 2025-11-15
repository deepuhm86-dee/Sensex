import os
import requests
import time
from datetime import datetime, timedelta
import pandas as pd

# === CONFIG ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DHAN_API_KEY = os.getenv("DHAN_API_KEY")
SYMBOL = "SENSEX"   # DhanHQ symbol for Sensex index
DEBUG_MODE = False

# === TELEGRAM ALERT ===
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        r = requests.post(url, json=payload, timeout=10)
        print("Telegram:", r.status_code, r.text)
    except Exception as e:
        print("Telegram error:", e)

# === FETCH SENSEX 5m CANDLES ===
def get_sensex_candles():
    url = f"https://api.dhan.co/v2/market/candles"
    params = {"symbol": SYMBOL, "interval": "5m", "limit": 50}
    headers = {"Authorization": f"Bearer {DHAN_API_KEY}"}
    r = requests.get(url, params=params, headers=headers)
    return r.json().get("data", [])

# === EMA CALCULATION ===
def get_ema(candles, period=5):
    closes = [float(c["close"]) for c in candles]
    df = pd.DataFrame(closes)
    return df.ewm(span=period, adjust=False).mean().iloc[-1][0]

# === SIGNAL CHECK ===
def check_signal(candle, ema):
    low = float(candle["low"])
    if low > ema and low != ema:  # strictly above, not touching
        message = (
            f"🚀 SENSEX SELL Signal\n\n"
            f"Candle Time: {candle['time']}\n"
            f"Low: {low}\nEMA5: {ema:.2f}"
        )
        print("✅ Signal detected")
        if not DEBUG_MODE:
            send_telegram_message(message)
    else:
        print("❌ No signal")

# === MAIN LOOP ===
if __name__ == "__main__":
    print("🚀 Bot started — monitoring SENSEX 5m candles...")

    MARKET_START = datetime.now().replace(hour=9, minute=15, second=0, microsecond=0)
    MARKET_END   = datetime.now().replace(hour=15, minute=15, second=0, microsecond=0)

    while True:
        now = datetime.now()
        if MARKET_START <= now <= MARKET_END:
            candles = get_sensex_candles()
            if candles:
                ema5 = get_ema(candles)
                latest = candles[-1]
                check_signal(latest, ema5)
        else:
            print("⏱ Outside market hours")
        time.sleep(300)  # wait 5 minutes
