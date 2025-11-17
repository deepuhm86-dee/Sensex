import os
import requests
import time
from datetime import datetime, time as dt_time
import pandas as pd
import pytz

# === CONFIG ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
UPSTOX_ACCESS_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN")
SENSEX_KEY = "BSE_INDEX|SENSEX"
DEBUG_MODE = False

IST = pytz.timezone("Asia/Kolkata")
last_signal_ts = None  # deduplication

# === TELEGRAM ALERT ===
def send_telegram_message(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram config missing")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        r = requests.post(url, json=payload, timeout=10)
        print("Telegram:", r.status_code, r.text)
    except Exception as e:
        print("Telegram error:", e)

# === FETCH SENSEX 5m CANDLES ===
def get_sensex_candles():
    try:
        url = "https://api.upstox.com/v2/market/candle/intraday"
        headers = {"Authorization": f"Bearer {UPSTOX_ACCESS_TOKEN}"}
        params = {"instrument_key": SENSEX_KEY, "interval": "5minute"}
        r = requests.get(url, headers=headers, params=params, timeout=10)
        r.raise_for_status()
        data = r.json().get("data", [])
        return data[-6:] if len(data) >= 6 else []
    except Exception as e:
        print("⚠️ Upstox API error:", e)
        return []

# === EMA CALCULATION ===
def get_ema(candles, period=5):
    try:
        closes = [float(c[4]) for c in candles]
        if len(closes) < period + 1:
            return None
        df = pd.DataFrame(closes, columns=["close"])
        ema = df["close"].ewm(span=period, adjust=False).mean().iloc[-2]
        return float(ema)
    except Exception as e:
        print("EMA error:", e)
        return None

# === SIGNAL CHECK ===
def check_signal(candle, ema):
    global last_signal_ts
    ts_utc = datetime.utcfromtimestamp(candle[0] / 1000).replace(tzinfo=pytz.utc)
    ts_ist = ts_utc.astimezone(IST)
    ts_str = ts_ist.strftime('%Y-%m-%d %H:%M')

    low = float(candle[3])
    close = float(candle[4])

    print(f"[{datetime.now(IST).strftime('%H:%M:%S')}] SENSEX | Low:{low:.2f} EMA5:{ema:.2f}")

    if ema and low > ema and ts_str != last_signal_ts:
        message = (
            f"🚀 SENSEX SELL Signal\n\n"
            f"Candle Time: {ts_str}\nLow: {low}\nClose: {close}\nEMA5: {ema:.2f}"
        )
        print("✅ SELL Signal detected")
        if not DEBUG_MODE:
            send_telegram_message(message)
        last_signal_ts = ts_str
    else:
        print("❌ No signal")

# === MARKET HOURS CHECK ===
def is_market_open():
    now = datetime.now(IST).time()
    return dt_time(9, 20) <= now <= dt_time(15, 15)

# === MAIN LOOP ===
if __name__ == "__main__":
    print("🚀 Bot started — monitoring SENSEX 5m candles via Upstox...")
    while True:
        if is_market_open():
            candles = get_sensex_candles()
            if candles:
                ema5 = get_ema(candles)
                if ema5:
                    latest = candles[-1]
                    check_signal(latest, ema5)
        else:
            print("⏱ Outside market hours")
        time.sleep(300)
