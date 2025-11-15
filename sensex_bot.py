import os
import requests
import time
from datetime import datetime
import pandas as pd

# === CONFIG ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
UPSTOX_API_KEY = os.getenv("UPSTOX_API_KEY")       # from Upstox developer portal
UPSTOX_ACCESS_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN")  # OAuth token after login
SENSEX_KEY = "BSE_INDEX|SENSEX"                   # instrument key for SENSEX
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
    url = f"https://api.upstox.com/v2/market/candle/intraday"
    headers = {"Authorization": f"Bearer {UPSTOX_ACCESS_TOKEN}"}
    params = {
        "instrument_key": SENSEX_KEY,
        "interval": "5minute"
    }
    r = requests.get(url, headers=headers, params=params)
    data = r.json()
    return data.get("data", [])

# === EMA CALCULATION ===
def get_ema(candles, period=5):
    closes = [float(c[4]) for c in candles]  # Upstox candle format: [timestamp, open, high, low, close, volume]
    df = pd.DataFrame(closes)
    return df.ewm(span=period, adjust=False).mean().iloc[-1][0]

# === SIGNAL CHECK ===
def check_signal(candle, ema):
    low = float(candle[3])   # low
    close = float(candle[4]) # close
    ts = candle[0]

    if low > ema and low != ema:
        message = (
            f"🚀 SENSEX SELL Signal\n\n"
            f"Candle Time: {ts}\n"
            f"Low: {low}\nClose: {close}\nEMA5: {ema:.2f}"
        )
        print("✅ Signal detected")
        if not DEBUG_MODE:
            send_telegram_message(message)
    else:
        print("❌ No signal")

# === MARKET HOURS CHECK ===
def is_market_open():
    now = datetime.now()
    return (
        now.weekday() < 5 and  # Mon–Fri
        now.hour >= 9 and (now.hour < 15 or (now.hour == 15 and now.minute <= 15))
    )

# === MAIN LOOP ===
if __name__ == "__main__":
    print("🚀 Bot started — monitoring SENSEX 5m candles via Upstox...")

    while True:
        if is_market_open():
            candles = get_sensex_candles()
            if candles:
                ema5 = get_ema(candles)
                latest = candles[-1]
                check_signal(latest, ema5)
        else:
            print("⏱ Outside market hours")
        time.sleep(300)  # 5 minutes
