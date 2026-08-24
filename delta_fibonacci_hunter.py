import time
from datetime import datetime
import pytz
import requests

# --- TELEGRAM CONFIG ---
BOT_TOKEN = "8626042409:AAHElsiJD8_Jk9R7r5VHUj8fPjcl8Meacp4"
CHAT_ID = "706694019"

# Symbols (BTC & ETH)
DELTA_SYMBOLS = ["BTCUSD", "ETHUSD"]
LOOKBACK = 35

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, data=payload, timeout=15)
        if r.status_code == 200:
            print("Telegram Alert Sent!")
        else:
            print(f"Telegram Error: {r.text}")
    except Exception as e:
        print(f"Connection Error: {e}")

def get_delta_candles(symbol, resolution="5m", count=80):
    end_time = int(time.time())
    start_time = end_time - (count * 5 * 60)
        
    url = "https://api.india.delta.exchange/v2/history/candles"
    params = {
        "symbol": symbol,
        "resolution": resolution,
        "start": start_time,
        "end": end_time
    }
    headers = {"Accept": "application/json"}
    
    try:
        res = requests.get(url, params=params, headers=headers, timeout=15).json()
        raw_candles = res.get("result", [])
        if not raw_candles:
            return []
            
        candles = []
        for c in raw_candles:
            if isinstance(c, dict):
                candles.append({
                    "time": int(c.get("time", c.get("t", 0))),
                    "open": float(c.get("open", c.get("o", 0))),
                    "high": float(c.get("high", c.get("h", 0))),
                    "low": float(c.get("low", c.get("l", 0))),
                    "close": float(c.get("close", c.get("c", 0))),
                    "volume": float(c.get("volume", c.get("v", 0)))
                })
            elif isinstance(c, list):
                candles.append({
                    "time": int(c[0]),
                    "open": float(c[1]),
                    "high": float(c[2]),
                    "low": float(c[3]),
                    "close": float(c[4]),
                    "volume": float(c[5])
                })
        candles.reverse()  # Oldest to Newest
        return candles
    except Exception as e:
        print(f"Fetch Error ({symbol}): {e}")
        return []

def run_fibonacci_scanner():
    ist = pytz.timezone('Asia/Kolkata')
    alerts = []
    print(f"[{datetime.now(ist).strftime('%H:%M:%S')}] Scanning Delta 5m Candles...")

    for sym in DELTA_SYMBOLS:
        try:
            candles = get_delta_candles(sym, resolution="5m", count=80)
            if len(candles) < LOOKBACK + 5:
                continue

            # Latest Completed 5m Candle (-2) & Previous Candle (-3)
            latest = candles[-2]
            prev = candles[-3]

            c_time = datetime.fromtimestamp(latest["time"], ist).strftime("%H:%M")
            c_open = latest["open"]
            c_high = latest["high"]
            c_low = latest["low"]
            c_close = latest["close"]

            # 35-Candle Swing Detection Window
            window = candles[-LOOKBACK-2:-2]
            highs = [x["high"] for x in window]
            lows = [x["low"] for x in window]
            
            swing_high = max(highs)
            swing_low = min(lows)
            idx_high = highs.index(swing_high)
            idx_low = lows.index(swing_low)
            swing_range = swing_high - swing_low

            if swing_range <= 0:
                continue

            # ==============================
            # 🟢 BUY SETUP (Uptrend Pullback)
            # ==============================
            if idx_high > idx_low:
                fib_50 = swing_high - (0.50 * swing_range)
                fib_618 = swing_high - (0.618 * swing_range)

                # શરત: કિંમત 0.50 નીચે આવી હોય અને 0.618 લેવલથી ગ્રીન કેન્ડલ ક્લોઝ આપે
                touched_zone = (prev["low"] <= fib_50) or (c_low <= fib_50)
                held_above_618 = (c_close >= fib_618 * 0.998)
                is_green = (c_close > c_open)

                if touched_zone and held_above_618 and is_green:
                    alert_text = (
                        f"🎯 *FIBONACCI 0.5 - 0.618 BUY SIGNAL*\n"
                        f"💎 *Pair:* `{sym}` (5-Min)\n"
                        f"🟢 *Signal:* *STRONG BUY (Bullish Bounce)*\n"
                        f"📈 *Swing High:* `${swing_high:,.2f}`\n"
                        f"📉 *Swing Low:* `${swing_low:,.2f}`\n"
                        f"🟡 *Fib 50.0%:* `${fib_50:,.2f}`\n"
                        f"🟠 *Fib 61.8%:* `${fib_618:,.2f}`\n"
                        f"💰 *Entry:* `${c_close:,.2f}`\n"
                        f"⏱ *Time:* `{c_time} IST`"
                    )
                    alerts.append(alert_text)

            # ==============================
            # 🔴 SELL SETUP (Downtrend Pullback)
            # ==============================
            elif idx_low > idx_high:
                fib_50 = swing_low + (0.50 * swing_range)
                fib_618 = swing_low + (0.618 * swing_range)

                # શરત: કિંમત 0.50 ઉપર ગઈ હોય અને 0.618 લેવલથી રેડ કેન્ડલ ક્લોઝ આપે
                touched_zone = (prev["high"] >= fib_50) or (c_high >= fib_50)
                held_below_618 = (c_close <= fib_618 * 1.002)
                is_red = (c_close < c_open)

                if touched_zone and held_below_618 and is_red:
                    alert_text = (
                        f"🎯 *FIBONACCI 0.5 - 0.618 SELL SIGNAL*\n"
                        f"💎 *Pair:* `{sym}` (5-Min)\n"
                        f"🔴 *Signal:* *STRONG SELL (Bearish Rejection)*\n"
                        f"📈 *Swing High:* `${swing_high:,.2f}`\n"
                        f"📉 *Swing Low:* `${swing_low:,.2f}`\n"
                        f"🟠 *Fib 61.8%:* `${fib_618:,.2f}`\n"
                        f"🟡 *Fib 50.0%:* `${fib_50:,.2f}`\n"
                        f"💰 *Entry:* `${c_close:,.2f}`\n"
                        f"⏱ *Time:* `{c_time} IST`"
                    )
                    alerts.append(alert_text)

        except Exception as e:
            print(f"Error checking {sym}: {e}")
            continue

    if alerts:
        msg = "\n\n━━━━━━━━━━━━━━━━━━━━\n\n".join(alerts)
        send_telegram(msg)
    else:
        print("No setups matched on the latest 5m candle.")

if __name__ == "__main__":
    run_fibonacci_scanner()
