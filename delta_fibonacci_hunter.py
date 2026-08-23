import time
from datetime import datetime
import pytz
import requests

# --- TELEGRAM CONFIG ---
BOT_TOKEN = "8626042409:AAHElsiJD8_Jk9R7r5VHUj8fPjcl8Meacp4"
CHAT_ID = "706694019"

# Delta Exchange Symbols
DELTA_SYMBOLS = ["BTCUSD", "ETHUSD"]

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"Telegram Error: {e}")

def get_delta_candles(symbol, resolution="5m", count=80):
    end_time = int(time.time())
    
    if resolution == "5m":
        start_time = end_time - (count * 5 * 60)
    elif resolution == "15m":
        start_time = end_time - (count * 15 * 60)
    else:
        start_time = end_time - (count * 60)
        
    url = "https://api.india.delta.exchange/v2/history/candles"
    params = {
        "symbol": symbol,
        "resolution": resolution,
        "start": start_time,
        "end": end_time
    }
    headers = {"Accept": "application/json"}
    
    try:
        res = requests.get(url, params=params, headers=headers, timeout=10).json()
        candles = res.get("result", [])
        candles.reverse()  # Oldest -> Newest
        return candles
    except Exception as e:
        print(f"Fetch Error ({symbol}): {e}")
        return []

def find_swings(candles, lookback=40):
    """
    Finds recent swing high and swing low from the candle window
    """
    highs = [float(c[2]) for c in candles[-lookback:-2]]
    lows = [float(c[3]) for c in candles[-lookback:-2]]
    
    max_high = max(highs)
    min_low = min(lows)
    
    idx_high = highs.index(max_high)
    idx_low = lows.index(min_low)
    
    return max_high, min_low, idx_high, idx_low

def run_fibonacci_scanner():
    ist = pytz.timezone('Asia/Kolkata')
    alerts = []

    print(f"[{datetime.now(ist).strftime('%H:%M:%S')}] Fibonacci 0.5 - 0.618 Scanner Active...")

    for sym in DELTA_SYMBOLS:
        try:
            # 5-minute candles fetch (Tame resolution='15m' pan kari shako cho)
            candles = get_delta_candles(sym, resolution="5m", count=60)
            if len(candles) < 35:
                continue

            # Latest completed candle (-2) & previous candle (-3)
            latest_c = candles[-2]
            prev_c = candles[-3]

            c_time = datetime.fromtimestamp(latest_c[0], ist).strftime("%H:%M")
            c_open = float(latest_c[1])
            c_high = float(latest_c[2])
            c_low = float(latest_c[3])
            c_close = float(latest_c[4])

            p_open = float(prev_c[1])
            p_high = float(prev_c[2])
            p_low = float(prev_c[3])
            p_close = float(prev_c[4])

            # Find Swings
            swing_high, swing_low, idx_high, idx_low = find_swings(candles, lookback=35)
            swing_range = swing_high - swing_low

            if swing_range <= 0:
                continue

            # ==========================================
            # 1. BUY SETUP (Uptrend: Low to High Move -> Pullback Down to 0.5-0.618)
            # ==========================================
            if idx_high > idx_low:
                # Uptrend Swing (Low was formed first, then High)
                # Fib Retracement levels from top to bottom
                fib_50 = swing_high - (0.50 * swing_range)
                fib_618 = swing_high - (0.618 * swing_range)

                # Zone: Between fib_618 (lower) and fib_50 (upper)
                zone_upper = fib_50
                zone_lower = fib_618

                # Criteria:
                # 1. Previous candle or Current candle dipped into the 0.50 - 0.618 Zone
                tested_zone = (p_low <= zone_upper and p_close >= zone_lower) or (c_low <= zone_upper and c_low >= zone_lower * 0.998)

                # 2. Trigger: Current candle is GREEN and closes above or near 0.50 level
                bullish_bounce = c_close > c_open and c_close >= zone_lower and tested_zone

                if bullish_bounce:
                    alert_text = (
                        f"🎯 *FIBONACCI 0.5 - 0.618 BUY SIGNAL*\n"
                        f"💎 *Pair:* `{sym}` (5-Min)\n"
                        f"🟢 *Signal:* *STRONG BUY (Bullish Bounce)*\n"
                        f"📈 *Swing High:* `${swing_high:,.2f}`\n"
                        f"📉 *Swing Low:* `${swing_low:,.2f}`\n"
                        f"🟡 *Fib 50.0%:* `${fib_50:,.2f}`\n"
                        f"🟠 *Fib 61.8%:* `${fib_618:,.2f}`\n"
                        f"💰 *Entry / Close:* `${c_close:,.2f}`\n"
                        f"⏱ *Candle Time:* `{c_time} IST`"
                    )
                    alerts.append(alert_text)

            # ==========================================
            # 2. SELL SETUP (Downtrend: High to Low Move -> Pullback Up to 0.5-0.618)
            # ==========================================
            elif idx_low > idx_high:
                # Downtrend Swing (High was formed first, then Low)
                # Fib Retracement levels from bottom to top
                fib_50 = swing_low + (0.50 * swing_range)
                fib_618 = swing_low + (0.618 * swing_range)

                # Zone: Between fib_50 (lower) and fib_618 (upper)
                zone_lower = fib_50
                zone_upper = fib_618

                # Criteria:
                # 1. Previous candle or Current candle touched 0.50 - 0.618 Zone
                tested_zone = (p_high >= zone_lower and p_close <= zone_upper) or (c_high >= zone_lower and c_high <= zone_upper * 1.002)

                # 2. Trigger: Current candle is RED and closes below or rejecting the zone
                bearish_rejection = c_close < c_open and c_close <= zone_upper and tested_zone

                if bearish_rejection:
                    alert_text = (
                        f"🎯 *FIBONACCI 0.5 - 0.618 SELL SIGNAL*\n"
                        f"💎 *Pair:* `{sym}` (5-Min)\n"
                        f"🔴 *Signal:* *STRONG SELL (Bearish Rejection)*\n"
                        f"📈 *Swing High:* `${swing_high:,.2f}`\n"
                        f"📉 *Swing Low:* `${swing_low:,.2f}`\n"
                        f"🟠 *Fib 61.8%:* `${fib_618:,.2f}`\n"
                        f"🟡 *Fib 50.0%:* `${fib_50:,.2f}`\n"
                        f"💰 *Entry / Close:* `${c_close:,.2f}`\n"
                        f"⏱ *Candle Time:* `{c_time} IST`"
                    )
                    alerts.append(alert_text)

        except Exception as e:
            print(f"Error {sym}: {e}")
            continue

    if alerts:
        msg = "\n\n━━━━━━━━━━━━━━━━━━━━\n\n".join(alerts)
        send_telegram(msg)
        print("Fibonacci alert sent to Telegram!")
    else:
        print("No Fibonacci 0.5-0.618 setups matched currently.")

if __name__ == "__main__":
    run_fibonacci_scanner()
