import os
import requests
import time
from datetime import datetime, time as dt_time
import pandas as pd
import pytz

# ================= CONFIG =================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
UPSTOX_ACCESS_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN")

# Use the correct instrument key from the instruments master file
INSTRUMENT_KEY = "BSE_INDEX|SENSEX"   # Replace with exact key if needed
EMA_PERIOD = 5
DEBUG_MODE = False

IST = pytz.timezone("Asia/Kolkata")
last_signal_ts = None

if not UPSTOX_ACCESS_TOKEN:
    print("❌ Missing UPSTOX_ACCESS_TOKEN")
    exit()

# ================= TELEGRAM =================
def send_telegram_message(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠ Telegram config missing")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}

    try:
        requests.post(url, json=payload, timeout=10)
        print("📩 Telegram sent")
    except Exception as e:
        print("Telegram error:", e)

# ================= FETCH CANDLES (v2) =================
def get_candles():
    try:
        # v2 intraday endpoint supports only 1minute or 30minute intervals
        url = f"https://api.upstox.com/v2/historical-candle/intraday/{INSTRUMENT_KEY}/30minute"

        headers = {
            "Authorization": f"Bearer {UPSTOX_ACCESS_TOKEN}",
            "Accept": "application/json"
        }

        r = requests.get(url, headers=headers, timeout=10)

        if r.status_code != 200:
            print("❌ API Error:", r.status_code, r.text)
            return []

        data = r.json().get("data", {})
        candles = data.get("candles", [])

        if len(candles) < 20:
            print("⚠ Not enough candles")
            return []

        return candles[-20:]

    except Exception as e:
        print("⚠ Fetch error:", e)
        return []

# ================= EMA =================
def calculate_ema(candles):
    closes = [float(c[4]) for c in candles]
    df = pd.DataFrame(closes, columns=["close"])
    df["ema"] = df["close"].ewm(span=EMA_PERIOD, adjust=False).mean()
    return float(df["ema"].iloc[-2])

# ================= SIGNAL =================
def check_signal(candles, ema):
    global last_signal_ts

    candle = candles[-2]

    ts = datetime.fromtimestamp(candle[0] / 1000, IST)
    ts_str = ts.strftime("%Y-%m-%d %H:%M")

    open_price = float(candle[1])
    high = float(candle[2])
    low = float(candle[3])
    close = float(candle[4])

    print(f"[{datetime.now(IST).strftime('%H:%M:%S')}] Close:{close} EMA:{ema}")

    if low > ema and ts_str != last_signal_ts:

        message = (
            f"🚀 SENSEX BUY Signal\n\n"
            f"Candle: {ts_str}\n"
            f"O:{open_price} H:{high} L:{low} C:{close}\n"
            f"EMA5:{ema}"
        )

        print("✅ BUY SIGNAL")

        if not DEBUG_MODE:
            send_telegram_message(message)

        last_signal_ts = ts_str

# ================= MARKET HOURS =================
def is_market_open():
    now = datetime.now(IST).time()
    return dt_time(9, 20) <= now <= dt_time(15, 15)

# ================= LOOP =================
if __name__ == "__main__":
    print("🚀 SENSEX EMA5 Bot Started (v2)...")

    while True:
        try:
            if is_market_open():
                candles = get_candles()
                if candles:
                    ema = calculate_ema(candles)
                    check_signal(candles, ema)
                else:
                    print("⚠ No data")
            else:
                print("⏱ Market closed")

        except Exception as e:
            print("Main error:", e)

        time.sleep(300)  # 5 minutes
