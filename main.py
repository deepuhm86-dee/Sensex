import os
import requests
import time
from datetime import datetime
import pandas as pd
import pytz

# === CONFIG ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
UPSTOX_ACCESS_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN")

INSTRUMENT_KEY = "BSE_FO|825565"   # Sensex Futures contract
EMA_PERIOD = 5
EPSILON = 0.0001
DEBUG_MODE = False

IST = pytz.timezone("Asia/Kolkata")
last_signal_time = None

# === TELEGRAM ALERT ===
def send_telegram_message(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠ Telegram config missing")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            print("📨 Telegram sent successfully")
        else:
            print(f"❌ Telegram error ({r.status_code}): {r.text}")
    except Exception as e:
        print("Telegram exception:", e)

# === EMA CALCULATION ===
def get_ema(candles, period=EMA_PERIOD):
    closes = [float(c[4]) for c in candles]
    if len(closes) < period + 1:
        return None
    df = pd.DataFrame(closes, columns=["close"])
    ema = df["close"].ewm(span=period, adjust=False).mean().iloc[-2]
    return float(ema)

# === FETCH LATEST 5-MIN CANDLE (today only) ===
def get_latest_candle():
    today = datetime.now(IST).strftime("%Y-%m-%d")
    url = f"https://api.upstox.com/v3/historical-candle/{INSTRUMENT_KEY}/minutes/5/{today}?from_date={today}"

    headers = {
        "Authorization": f"Bearer {UPSTOX_ACCESS_TOKEN}",
        "Accept": "application/json"
    }

    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            print("⚠ Candle API error:", r.status_code, r.text)
            return None
        candles = r.json().get("data", {}).get("candles", [])
        if len(candles) < EMA_PERIOD + 2:
            print("⚠ Not enough candles")
            return None
        return candles[-(EMA_PERIOD+2):]  # last few candles for EMA
    except Exception as e:
        print("Candle fetch exception:", e)
        return None

# === LIVE QUOTE CHECK (with fallback) ===
def get_live_quote():
    url = f"https://api.upstox.com/v3/quote/instrument/{INSTRUMENT_KEY}"
    headers = {
        "Authorization": f"Bearer {UPSTOX_ACCESS_TOKEN}",
        "Accept": "application/json"
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            print("⚠ Quote API error:", r.status_code)
            return None
        return r.json().get("data", {}).get("last_price")
    except Exception as e:
        print("Quote fetch exception:", e)
        return None

# === SIGNAL CHECK (SELL only) ===
def check_signal(candle, ema, live_price):
    global last_signal_time

    ts = datetime.fromisoformat(candle[0])
    high = float(candle[2])
    low = float(candle[3])
    close = float(candle[4])

    print(f"[{datetime.now(IST).strftime('%H:%M:%S')}] Close:{close:.2f} EMA5:{ema:.2f} Live:{live_price if live_price else 'N/A'}")

    # SELL condition only
    if low > ema + EPSILON and ts != last_signal_time:
        message = (
            f"🚀 ABOVE 5 EMA SELL Signal\n\n"
            f"Candle Time: {ts.strftime('%Y-%m-%d %H:%M')}\n"
            f"H:{high} L:{low} C:{close}\nEMA5:{ema:.2f}\nLive:{live_price if live_price else 'N/A'}"
        )
        print("✅ SELL Signal detected")
        if not DEBUG_MODE:
            send_telegram_message(message)
        last_signal_time = ts
    else:
        print("❌ No SELL signal")

# === MAIN LOOP ===
if __name__ == "__main__":
    print("🚀 SENSEX Futures EMA5 Bot Started (5m candles, SELL only)...")

    while True:
        try:
            candles = get_latest_candle()
            live_price = get_live_quote()
            if candles:
                ema = get_ema(candles)
                latest_candle = candles[-2]  # last closed candle
                if ema:
                    check_signal(latest_candle, ema, live_price)
            else:
                print("⚠ No candle data, retrying in 30s")
                time.sleep(30)
                continue
        except Exception as e:
            print("Main error:", e)

        time.sleep(300)  # run every 5 minutes
