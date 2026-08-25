import time
from datetime import datetime, timezone
import requests

# --- TELEGRAM CONFIG ---
BOT_TOKEN = "8626042409:AAHElsiJD8_Jk9R7r5VHUj8fPjcl8Meacp4"
CHAT_ID = "706694019"

DELTA_SYMBOLS = ["BTCUSD", "ETHUSD"]

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, data=payload, timeout=15)
        if r.status_code == 200:
            print("Telegram Alert Sent Successfully!")
        else:
            print(f"Telegram API Error: {r.text}")
    except Exception as e:
        print(f"Connection Error: {e}")

def get_delta_candles(symbol, resolution="5m", count=300):
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
        candles.reverse()  # Oldest -> Newest
        return candles
    except Exception as e:
        print(f"Fetch Error ({symbol}): {e}")
        return []

def run_fibonacci_scanner():
    now_utc = datetime.now(timezone.utc)
    start_of_day_utc = datetime(now_utc.year, now_utc.month, now_utc.day, tzinfo=timezone.utc)
    start_of_day_ts = int(start_of_day_utc.timestamp())

    print(f"[{now_utc.strftime('%H:%M:%S')} UTC] Scanning Swings & Retracements...")

    for sym in DELTA_SYMBOLS:
        try:
            candles = get_delta_candles(sym, resolution="5m", count=300)
            if len(candles) < 20:
                continue

            today_candles = [c for c in candles if c["time"] >= start_of_day_ts]
            eval_candles = today_candles if len(today_candles) >= 12 else candles[-60:]

            latest = eval_candles[-2]
            c_time = datetime.fromtimestamp(latest["time"], timezone.utc).strftime("%H:%M")
            c_open = latest["open"]
            c_high = latest["high"]
            c_low = latest["low"]
            c_close = latest["close"]

            search_window = eval_candles[:-2]
            if len(search_window) < 6:
                continue

            all_highs = [x["high"] for x in search_window]
            day_high = max(all_highs)
            day_high_idx = all_highs.index(day_high)

            all_lows = [x["low"] for x in search_window]
            day_low = min(all_lows)
            day_low_idx = all_lows.index(day_low)

            # ==========================================
            # 🔴 SELL SETUP (Day High ➔ Progressive Swing Low)
            # ==========================================
            post_high_window = search_window[day_high_idx:]
            if len(post_high_window) >= 3:
                # High પછી બનેલા મિનીમમ સ્વીંગ લો પોઈન્ટ્સ શોધવા
                post_lows = [x["low"] for x in post_high_window]
                
                # લેટેસ્ટ સ્વિંગ લો (જેના પરથી ફિબોનાચી ડ્રો થશે)
                swing_low = min(post_lows)
                swing_low_rel_idx = post_lows.index(swing_low)
                swing_low_idx = day_high_idx + swing_low_rel_idx

                if swing_low_idx > day_high_idx and (len(search_window) - 1) > swing_low_idx:
                    time_day_high = datetime.fromtimestamp(search_window[day_high_idx]["time"], timezone.utc).strftime("%H:%M")
                    time_swing_low = datetime.fromtimestamp(search_window[swing_low_idx]["time"], timezone.utc).strftime("%H:%M")

                    swing_range = day_high - swing_low
                    if swing_range > 0:
                        fib_50 = swing_low + (0.50 * swing_range)
                        fib_618 = swing_low + (0.618 * swing_range)

                        # Swing Low બન્યા પછીની કેન્ડલ્સ
                        pullback_candles = search_window[swing_low_idx:]
                        
                        # ૧. ભાવ 0.50 - 0.618 ઝોનની અંદર ક્લોઝ આપી ચૂક્યો હોવો જોઈએ
                        closed_inside_zone = any(
                            (x["close"] >= fib_50 and x["close"] <= fib_618) for x in pullback_candles
                        )

                        # ૨. જો 0.618 ની ઉપર બોડી ક્લોઝ આપી દે તો SETUP INVALID ALERT
                        if closed_inside_zone and any(x["close"] > (fib_618 * 1.001) for x in pullback_candles):
                            alert_invalid_sell = (
                                f"⚠️ *FIBONACCI SELL SETUP INVALIDATED*\n"
                                f"💎 *Pair:* `{sym}` (5-Min)\n"
                                f"❌ *Reason:* Candle closed above 0.618 level\n"
                                f"━━━━━━━━━━━━━━━━━━━━\n"
                                f"📈 *Day High:* `${day_high:,.2f}` _({time_day_high} UTC)_\n"
                                f"📉 *Swing Low:* `${swing_low:,.2f}` _({time_swing_low} UTC)_\n"
                                f"🟠 *Fib 61.8%:* `${fib_618:,.2f}`\n"
                                f"💥 *Candle Close:* `${c_close:,.2f}`\n"
                                f"⏱ *Invalid Time:* `{c_time} UTC`"
                            )
                            send_telegram(alert_invalid_sell)
                            continue

                        # ૩. કન્ફર્મેશન: કેન્ડલ 0.50 ની નીચે રેડ ક્લોઝ આપે
                        if closed_inside_zone and c_close <= fib_50 and c_close < c_open:
                            entry_price = c_low

                            # SL Logic
                            zone_highs = [x["high"] for x in pullback_candles] + [c_high]
                            max_pullback_high = max(zone_highs)

                            if max_pullback_high > fib_618:
                                stop_loss = max_pullback_high
                                sl_type = f"Spike High (${stop_loss:,.2f})"
                            else:
                                stop_loss = fib_618
                                sl_type = f"Fib 0.618 Level (${stop_loss:,.2f})"

                            risk = stop_loss - entry_price
                            if risk > 0:
                                t1 = entry_price - (1.0 * risk)
                                t2 = entry_price - (2.0 * risk)
                                t3 = entry_price - (3.0 * risk)
                                t4 = entry_price - (4.0 * risk)
                                t5 = entry_price - (5.0 * risk)

                                alert_sell = (
                                    f"🎯 *FIBONACCI SELL SIGNAL*\n"
                                    f"💎 *Pair:* `{sym}` (5-Min)\n"
                                    f"🔴 *Signal:* *STRONG SELL (Pullback Confirmed)*\n"
                                    f"━━━━━━━━━━━━━━━━━━━━\n"
                                    f"📈 *Day High:* `${day_high:,.2f}` _({time_day_high} UTC)_\n"
                                    f"📉 *Swing Low:* `${swing_low:,.2f}` _({time_swing_low} UTC)_\n"
                                    f"🟠 *Fib 61.8%:* `${fib_618:,.2f}`\n"
                                    f"🟡 *Fib 50.0%:* `${fib_50:,.2f}`\n"
                                    f"━━━━━━━━━━━━━━━━━━━━\n"
                                    f"🔻 *Entry (Candle Low):* `${entry_price:,.2f}`\n"
                                    f"🛑 *Stop Loss:* `${stop_loss:,.2f}` _({sl_type})_\n"
                                    f"📏 *Risk (1R):* `${risk:,.2f}`\n"
                                    f"━━━━━━━━━━━━━━━━━━━━\n"
                                    f"🎯 *TARGET LEVELS (1:1 to 1:5):*\n"
                                    f"  • *1:1 Target:* `${t1:,.2f}`\n"
                                    f"  • *1:2 Target:* `${t2:,.2f}`\n"
                                    f"  • *1:3 Target:* `${t3:,.2f}`\n"
                                    f"  • *1:4 Target:* `${t4:,.2f}`\n"
                                    f"  • *1:5 Target:* `${t5:,.2f}`\n"
                                    f"━━━━━━━━━━━━━━━━━━━━\n"
                                    f"⏱ *Entry Candle Time:* `{c_time} UTC`"
                                )
                                send_telegram(alert_sell)
                                continue

            # ==========================================
            # 🟢 BUY SETUP (Day Low ➔ Progressive Swing High)
            # ==========================================
            post_low_window = search_window[day_low_idx:]
            if len(post_low_window) >= 3:
                post_highs = [x["high"] for x in post_low_window]
                swing_high = max(post_highs)
                swing_high_rel_idx = post_highs.index(swing_high)
                swing_high_idx = day_low_idx + swing_high_rel_idx

                if swing_high_idx > day_low_idx and (len(search_window) - 1) > swing_high_idx:
                    time_day_low = datetime.fromtimestamp(search_window[day_low_idx]["time"], timezone.utc).strftime("%H:%M")
                    time_swing_high = datetime.fromtimestamp(search_window[swing_high_idx]["time"], timezone.utc).strftime("%H:%M")

                    swing_range = swing_high - day_low
                    if swing_range > 0:
                        fib_50 = swing_high - (0.50 * swing_range)
                        fib_618 = swing_high - (0.618 * swing_range)

                        pullback_candles = search_window[swing_high_idx:]
                        
                        closed_inside_zone = any(
                            (x["close"] <= fib_50 and x["close"] >= fib_618) for x in pullback_candles
                        )

                        if closed_inside_zone and any(x["close"] < (fib_618 * 0.999) for x in pullback_candles):
                            alert_invalid_buy = (
                                f"⚠️ *FIBONACCI BUY SETUP INVALIDATED*\n"
                                f"💎 *Pair:* `{sym}` (5-Min)\n"
                                f"❌ *Reason:* Candle closed below 0.618 level\n"
                                f"━━━━━━━━━━━━━━━━━━━━\n"
                                f"📉 *Day Low:* `${day_low:,.2f}` _({time_day_low} UTC)_\n"
                                f"📈 *Swing High:* `${swing_high:,.2f}` _({time_swing_high} UTC)_\n"
                                f"🟠 *Fib 61.8%:* `${fib_618:,.2f}`\n"
                                f"💥 *Candle Close:* `${c_close:,.2f}`\n"
                                f"⏱ *Invalid Time:* `{c_time} UTC`"
                            )
                            send_telegram(alert_invalid_buy)
                            continue

                        if closed_inside_zone and c_close >= fib_50 and c_close > c_open:
                            entry_price = c_high

                            zone_lows = [x["low"] for x in pullback_candles] + [c_low]
                            min_pullback_low = min(zone_lows)

                            if min_pullback_low < fib_618:
                                stop_loss = min_pullback_low
                                sl_type = f"Spike Low (${stop_loss:,.2f})"
                            else:
                                stop_loss = fib_618
                                sl_type = f"Fib 0.618 Level (${stop_loss:,.2f})"

                            risk = entry_price - stop_loss
                            if risk > 0:
                                t1 = entry_price + (1.0 * risk)
                                t2 = entry_price + (2.0 * risk)
                                t3 = entry_price + (3.0 * risk)
                                t4 = entry_price + (4.0 * risk)
                                t5 = entry_price + (5.0 * risk)

                                alert_buy = (
                                    f"🎯 *FIBONACCI BUY SIGNAL*\n"
                                    f"💎 *Pair:* `{sym}` (5-Min)\n"
                                    f"🟢 *Signal:* *STRONG BUY (Pullback Confirmed)*\n"
                                    f"━━━━━━━━━━━━━━━━━━━━\n"
                                    f"📉 *Day Low:* `${day_low:,.2f}` _({time_day_low} UTC)_\n"
                                    f"📈 *Swing High:* `${swing_high:,.2f}` _({time_swing_high} UTC)_\n"
                                    f"🟡 *Fib 50.0%:* `${fib_50:,.2f}`\n"
                                    f"🟠 *Fib 61.8%:* `${fib_618:,.2f}`\n"
                                    f"━━━━━━━━━━━━━━━━━━━━\n"
                                    f"🚀 *Entry (Candle High):* `${entry_price:,.2f}`\n"
                                    f"🛑 *Stop Loss:* `${stop_loss:,.2f}` _({sl_type})_\n"
                                    f"📏 *Risk (1R):* `${risk:,.2f}`\n"
                                    f"━━━━━━━━━━━━━━━━━━━━\n"
                                    f"🎯 *TARGET LEVELS (1:1 to 1:5):*\n"
                                    f"  • *1:1 Target:* `${t1:,.2f}`\n"
                                    f"  • *1:2 Target:* `${t2:,.2f}`\n"
                                    f"  • *1:3 Target:* `${t3:,.2f}`\n"
                                    f"  • *1:4 Target:* `${t4:,.2f}`\n"
                                    f"  • *1:5 Target:* `${t5:,.2f}`\n"
                                    f"━━━━━━━━━━━━━━━━━━━━\n"
                                    f"⏱ *Entry Candle Time:* `{c_time} UTC`"
                                )
                                send_telegram(alert_buy)
                                continue

        except Exception as e:
            print(f"Error checking {sym}: {e}")
            continue

if __name__ == "__main__":
    run_fibonacci_scanner()
