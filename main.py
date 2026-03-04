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

INSTRUMENT_KEY = "BSE_INDEX|SENSEX"   # Confirm exact key from instruments file
EMA_PERIOD = 5
EPSILON = 0.0001
DEBUG_MODE = False

IST = pytz.timezone("Asia/Kolkata")
last_signal_times = {}

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

# === FETCH LAST 5-MIN CANDLE ===
def get_latest_candle():
    to_date = datetime.now(IST).strftime("%Y-%m-%d")
    url = f"https://api.upstox.com/v3/historical-candle/{INSTRUMENT_KEY}/minutes/5/{to_date}"

    headers = {
        "Authorization": f"Bearer {UPSTOX_ACCESS_TOKEN}",
        "Accept": "application/json"
    }

    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code != 200:
        print("❌ API Error:", r.status_code, r.text)
        return None

    candles = r.json().get("data", {}).get("candles", [])
    if len(candles) < EMA_PERIOD + 2:
        print("⚠ Not enough candles")
        return None

    # Return last N candles (for EMA calc) and the latest closed candle
    return candles[-(EMA_PERIOD+2):]

# === SIGNAL CHECK ===
def check_signal(candle, ema):
    global last_signal_times

    ts = datetime.fromisoformat(candle[0])
    high = float(candle[2])
    low = float(candle[3])
    close = float(candle[4])

    print(f"[{datetime.now(IST).strftime('%H:%M:%S')}] Close:{close:.2f} EMA5:{ema:.2f}")

    # SELL
    if low > ema + EPSILON and ts != last_signal_times.get("SELL"):
        message = (
            f"🚀 ABOVE 5 EMA SELL Signal\n\n"
            f"Candle Time: {ts.strftime('%Y-%m-%d %H:%M')}\n"
            f"H:{high} L:{low} C:{close}\nEMA5:{ema:.2f}"
        )
        print("✅ SELL Signal detected")
        if not DEBUG_MODE:
            send_telegram_message(message)
        last_signal_times["SELL"] = ts

    # BUY
    elif high < ema - EPSILON and ts != last_signal_times.get("BUY"):
        message = (
            f"🟢 BELOW 5 EMA BUY Signal\n\n"
            f"Candle Time: {ts.strftime('%Y-%m-%d %H:%M')}\n"
            f"H:{high} L:{low} C:{close}\nEMA5:{ema:.2f}"
        )
        print("✅ BUY Signal detected")
        if not DEBUG_MODE:
            send_telegram_message(message)
        last_signal_times["BUY"] = ts

    else:
        print("❌ No signal")

# === MAIN LOOP ===
if __name__ == "__main__":
    print("🚀 SENSEX EMA5 Bot Started (5m candles)...")

    while True:
        try:
            candles = get_latest_candle()
            if candles:
                ema = get_ema(candles)
                latest_candle = candles[-2]  # last closed candle
                if ema:
                    check_signal(latest_candle, ema)
            else:
                print("⚠ No candle data")
        except Exception as e:
            print("Main error:", e)

        time.sleep(300)  # run every 5 minutes
