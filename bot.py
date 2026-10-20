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
    for
