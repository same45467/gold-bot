"""
Gold Evening Breakout bot
Runs every weekday evening. Works out tonight's two pending orders for Gold (XAU/USD)
and sends them to your phone on Telegram.

Rules (tested on 2023-2026 data):
  - Day range  = gold's high and low from 23:00 last night to 21:00 tonight (UK time)
  - ATR        = average daily high-low range over the last 14 weekdays (not counting today)
  - BUY STOP   at the day high.  Stop loss = 1 x ATR below entry. Take profit = 2 x ATR above.
  - SELL STOP  at the day low.   Stop loss = 1 x ATR above entry. Take profit = 2 x ATR below.
  - Leave both orders on. At 21:00 next weekday: close anything open, cancel unfilled, place new ones.
"""
import os, sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests

UK = ZoneInfo("Europe/London")

# ---- Settings (secrets come from GitHub, never written in this file) ----
TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
TWELVEDATA_KEY   = os.environ["TWELVEDATA_KEY"]
ACCOUNT_GBP      = float(os.environ.get("ACCOUNT_GBP", "250"))   # your T212 CFD account size
RISK_PCT         = float(os.environ.get("RISK_PCT", "1"))        # % of account risked per order
MIN_POSITION_GBP = 100                                            # T212 minimum position value
STOP_ATR, TARGET_R, ATR_DAYS = 1.0, 2.0, 14


def send(text):
    r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      data={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=30)
    print("Telegram:", r.status_code, r.text[:200])


def get_hourly_bars():
    """Last ~600 hourly gold candles, timestamps in UK time."""
    r = requests.get("https://api.twelvedata.com/time_series", timeout=30, params={
        "symbol": "XAU/USD", "interval": "1h", "outputsize": 600,
        "timezone": "Europe/London", "apikey": TWELVEDATA_KEY})
    data = r.json()
    if data.get("status") != "ok":
        raise RuntimeError(f"Twelve Data error: {data}")
    bars = []
    for v in data["values"]:
        t = datetime.strptime(v["datetime"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UK)
        bars.append((t, float(v["high"]), float(v["low"]), float(v["close"])))
    return sorted(bars)


def compute_levels(bars, now):
    today = now.date()
    # 1) Today's range: 23:00 last night up to 21:00 tonight (bar start times)
    start = datetime.combine(today - timedelta(days=1), datetime.min.time(), UK).replace(hour=23)
    end = datetime.combine(today, datetime.min.time(), UK).replace(hour=21)
    todays = [b for b in bars if start <= b[0] < end]
    if len(todays) < 10:
        raise RuntimeError(f"Only {len(todays)} hourly candles for today - market closed or data missing")
    hi = max(b[1] for b in todays); lo = min(b[2] for b in todays); last = todays[-1][3]
    # 2) ATR: mean (high-low) of the last 14 completed weekdays, each day = 00:00-24:00 UK
    days = {}
    for t, h, l, c in bars:
        d = t.date()
        if d < today and d.weekday() < 5:
            dh, dl = days.get(d, (h, l)); days[d] = (max(dh, h), min(dl, l))
    recent = sorted(days)[-ATR_DAYS:]
    if len(recent) < ATR_DAYS:
        raise RuntimeError("Not enough history for ATR")
    atr = sum(days[d][0] - days[d][1] for d in recent) / ATR_DAYS
    return hi, lo, last, atr


def position_size(atr, price):
    stop_pct = STOP_ATR * atr / price                 # how far the stop is, as a % move
    risk_gbp = ACCOUNT_GBP * RISK_PCT / 100
    pos = risk_gbp / stop_pct
    pos = max(pos, MIN_POSITION_GBP)
    return round(pos), round(pos * stop_pct, 2)        # position value, £ lost if stopped


def main():
    now = datetime.now(UK)
    force = "--force" in sys.argv
    # GitHub's timer runs in UTC, so it fires twice; only the run in the UK 21:xx hour continues.
    if not force and (now.weekday() >= 5 or now.hour != 21):
        print("Not 21:xx UK on a weekday - exiting.", now); return
    try:
        bars = get_hourly_bars()
        hi, lo, last, atr = compute_levels(bars, now)
    except Exception as e:
        send(f"⚠️ Gold bot error tonight - no orders. ({e})"); raise
    sd = STOP_ATR * atr
    pos, risk = position_size(atr, last)
    msg = (
        f"🟡 GOLD orders for {now:%a %d %b}\n"
        f"(close any open gold trade + cancel old orders first)\n\n"
        f"🟢 BUY STOP  @ {hi:.2f}\n"
        f"   Stop loss   {hi - sd:.2f}\n"
        f"   Take profit {hi + TARGET_R * sd:.2f}\n\n"
        f"🔴 SELL STOP @ {lo:.2f}\n"
        f"   Stop loss   {lo + sd:.2f}\n"
        f"   Take profit {lo - TARGET_R * sd:.2f}\n\n"
        f"Size: £{pos} position on EACH order (risk ≈ £{risk} each)\n"
        f"Gold now ≈ {last:.2f} | ATR ${atr:.1f}"
    )
    print(msg); send(msg)


if __name__ == "__main__":
    main()
