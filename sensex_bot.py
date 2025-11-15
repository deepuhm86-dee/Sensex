import os
import requests
import time
from datetime import datetime, timedelta
import pandas as pd

# === CONFIG ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DHAN_API_KEY = os.getenv("DHAN_API_KEY")
SECURITY_ID = os.getenv("SENSEX_SECURITY_ID")  # e.g., "123456"
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
    today = datetime.now().strftime("%Y-%m-%d")
    url = "https://api.dhan.co/market/v1/instruments/candles"
    params = {
        "securityId": SECURITY_ID,
        "exchangeSegment": "BSE",
        "interval": "5MIN",
        "fromDate": today,
        "toDate": today
    }
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
    if low > ema and low != ema:
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
def is_market_open():
    now = datetime.now()
    return (
        now.weekday() < 5 and  # Mon–Fri
        now.hour >= 9 and (now.hour < 15 or (now.hour == 15 and now.minute <= 15))
    )

if __name__ == "__main__":
    print("🚀 Bot started — monitoring SENSEX 5m candles...")

    while True:
        if is_market_open():
            candles = get_sensex_candles()
            if candles:
                ema5 = get_ema(candles)
                latest = candles[-1]
                check_signal(latest, ema5)
        else:
            print("⏱ Outside market hours")
        time.sleep(300)
