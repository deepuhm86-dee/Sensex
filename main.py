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

SENSEX_KEY = "BSE_INDEX|SENSEX"
EMA_PERIOD = 5
DEBUG_MODE = False

IST = pytz.timezone("Asia/Kolkata")
last_signal_ts = None  # prevents duplicate alerts

# ================= SAFETY CHECK =================
if not UPSTOX_ACCESS_TOKEN:
    print("❌ Missing UPSTOX_ACCESS_TOKEN")
    exit()

# ================= TELEGRAM =================
def send_telegram_message(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠ Telegram config missing")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }

    try:
        r = requests.post(url, json=payload, timeout=10)
        print("📩 Telegram sent:", r.status_code)
    except Exception as e:
        print("Telegram error:", e)

# ================= FETCH CANDLES =================
def get_sensex_candles():
    try:
        url = "https://api.upstox.com/v2/market/candle/intraday"
        headers = {
            "Authorization": f"Bearer {UPSTOX_ACCESS_TOKEN}"
        }
        params = {
            "instrument_key": SENSEX_KEY,
            "interval": "5minute"
        }

        r = requests.get(url, headers=headers, params=params, timeout=10)
        r.raise_for_status()

        data = r.json().get("data", [])

        if len(data) < 20:
            print("Not enough candles for EMA")
            return []

        return data[-20:]  # last 20 candles

    except Exception as e:
        print("⚠ Upstox API error:", e)
        return []

# ================= EMA CALCULATION =================
def calculate_ema(candles, period=EMA_PERIOD):
    try:
        closes = [float(c[4]) for c in candles]

        df = pd.DataFrame(closes, columns=["close"])
        df["ema"] = df["close"].ewm(span=period, adjust=False).mean()

        # Use EMA of last CLOSED candle
        return float(df["ema"].iloc[-2])

    except Exception as e:
        print("EMA calculation error:", e)
        return None

# ================= SIGNAL LOGIC =================
def check_signal(candles, ema_value):
    global last_signal_ts

    candle = candles[-2]  # last CLOSED candle

    ts_utc = datetime.utcfromtimestamp(candle[0] / 1000).replace(tzinfo=pytz.utc)
    ts_ist = ts_utc.astimezone(IST)
    ts_str = ts_ist.strftime('%Y-%m-%d %H:%M')

    open_price = float(candle[1])
    high = float(candle[2])
    low = float(candle[3])
    close = float(candle[4])

    print(f"[{datetime.now(IST).strftime('%H:%M:%S')}] Close:{close:.2f} | EMA5:{ema_value:.2f}")

    # ===== BUY CONDITION =====
    if ema_value and low > ema_value and ts_str != last_signal_ts:

        message = (
            f"🚀 SENSEX BUY Signal\n\n"
            f"Candle Time: {ts_str}\n"
            f"Open: {open_price}\n"
            f"High: {high}\n"
            f"Low: {low}\n"
            f"Close: {close}\n"
            f"EMA5: {ema_value:.2f}"
        )

        print("✅ BUY Signal detected")

        if not DEBUG_MODE:
            send_telegram_message(message)

        last_signal_ts = ts_str

    else:
        print("❌ No signal")

# ================= MARKET HOURS =================
def is_market_open():
    now = datetime.now(IST).time()
    return dt_time(9, 20) <= now <= dt_time(15, 15)

# ================= 5-MIN ALIGNMENT =================
def sleep_until_next_5min():
    now = datetime.now(IST)

    next_minute = (now.minute // 5 + 1) * 5

    if next_minute == 60:
        next_time = now.replace(
            hour=now.hour + 1,
            minute=0,
            second=5,
            microsecond=0
        )
    else:
        next_time = now.replace(
            minute=next_minute,
            second=5,
            microsecond=0
        )

    sleep_seconds = (next_time - now).total_seconds()

    if sleep_seconds > 0:
        print(f"⏳ Sleeping {int(sleep_seconds)} sec until {next_time.strftime('%H:%M:%S')}")
        time.sleep(sleep_seconds)

# ================= MAIN LOOP =================
if __name__ == "__main__":
    print("🚀 SENSEX EMA5 Bot Started (Upstox 5m candles)...")

    while True:
        try:
            if is_market_open():
                candles = get_sensex_candles()

                if candles:
                    ema5 = calculate_ema(candles)

                    if ema5:
                        check_signal(candles, ema5)
                else:
                    print("No candle data received")

            else:
                print("⏱ Outside market hours")

        except Exception as e:
            print("Main loop error:", e)

        sleep_until_next_5min()
