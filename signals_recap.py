"""
Daily Signal Performance Recap & Results Tracker.
Runs at 21:00 UTC (Official Daily Market Close / 5:00 PM EST).
Evaluates the day's high & low against the morning signals to calculate transparent
win rates, pips gained, and targets hit across Gold, Crypto & Forex.
"""
import os
import sys
from datetime import datetime, timezone
import requests
import pandas as pd

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

MAIN_APP_NAME = "Best Forex Brokers"
MAIN_APP_LINK = "https://play.google.com/store/apps/details?id=com.revapps.bestforexbrokers"
BROKER_LINK = "https://clicks.pipaffiliates.com/c?m=131292&c=98704"
WHATSAPP_CHANNEL_LINK = "https://whatsapp.com/channel/0029Vb9Wpao8F2p6YTGzIP2g"

if not BOT_TOKEN or not CHAT_ID:
    sys.exit("❌ Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")

ASSETS = [
    {"ticker": "GC=F",     "name": "Gold (XAU/USD)", "emoji": "🥇", "decimals": 2, "prefix": "$", "pip_mult": 10},
    {"ticker": "BTC-USD",  "name": "Bitcoin (BTC)",  "emoji": "₿",  "decimals": 0, "prefix": "$", "pip_mult": 1},
    {"ticker": "ETH-USD",  "name": "Ethereum (ETH)", "emoji": "⟠",  "decimals": 1, "prefix": "$", "pip_mult": 1},
    {"ticker": "EURUSD=X", "name": "EUR/USD",        "emoji": "💶", "decimals": 4, "prefix": "",  "pip_mult": 10000},
    {"ticker": "GBPUSD=X", "name": "GBP/USD",        "emoji": "💷", "decimals": 4, "prefix": "",  "pip_mult": 10000},
    {"ticker": "USDJPY=X", "name": "USD/JPY",        "emoji": "💴", "decimals": 2, "prefix": "",  "pip_mult": 100},
]


def fetch_day_performance(ticker):
    """Fetch 1-month daily candles to evaluate signal and today's high/low."""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=1mo&interval=1d"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=12)
        resp.raise_for_status()
        data = resp.json()["chart"]["result"][0]
        q = data["indicators"]["quote"][0]

        closes = pd.Series([c for c in q["close"] if c is not None])
        highs = pd.Series([h for h in q["high"] if h is not None])
        lows = pd.Series([l for l in q["low"] if l is not None])

        if len(closes) < 15:
            return None

        today_close = float(closes.iloc[-1])
        today_high = float(highs.iloc[-1])
        today_low = float(lows.iloc[-1])
        prev_close = float(closes.iloc[-2])
        prev_high = float(highs.iloc[-2])
        prev_low = float(lows.iloc[-2])

        # Recalculate morning setup
        pivot = (prev_high + prev_low + prev_close) / 3
        r1 = 2 * pivot - prev_low
        s1 = 2 * pivot - prev_high

        tr = pd.concat([highs - lows, (highs - closes.shift()).abs(), (lows - closes.shift()).abs()], axis=1).max(axis=1)
        atr = float(tr.rolling(14).mean().iloc[-1])
        if pd.isna(atr) or atr <= 0:
            atr = today_close * 0.008

        ema20 = float(closes.ewm(span=20).mean().iloc[-1])

        # Signal direction
        is_buy = today_close >= pivot and today_close >= ema20
        is_sell = today_close < pivot and today_close < ema20

        if is_buy:
            action = "BUY"
            entry = prev_close
            sl = entry - 1.2 * atr
            tp1 = entry + 1.2 * atr
            tp2 = entry + 2.4 * atr

            if today_high >= tp2:
                outcome = "TP2_HIT"
                pips = 2.4 * atr
            elif today_high >= tp1:
                outcome = "TP1_HIT"
                pips = 1.2 * atr
            elif today_low <= sl:
                outcome = "SL_HIT"
                pips = -1.2 * atr
            else:
                pips = today_close - entry
                outcome = "BREAKEVEN" if pips >= 0 else "HOLD"
        else:
            action = "SELL"
            entry = prev_close
            sl = entry + 1.2 * atr
            tp1 = entry - 1.2 * atr
            tp2 = entry - 2.4 * atr

            if today_low <= tp2:
                outcome = "TP2_HIT"
                pips = 2.4 * atr
            elif today_low <= tp1:
                outcome = "TP1_HIT"
                pips = 1.2 * atr
            elif today_high >= sl:
                outcome = "SL_HIT"
                pips = -1.2 * atr
            else:
                pips = entry - today_close
                outcome = "BREAKEVEN" if pips >= 0 else "HOLD"

        return {
            "action": action,
            "entry": entry,
            "today_high": today_high,
            "today_low": today_low,
            "today_close": today_close,
            "tp1": tp1,
            "tp2": tp2,
            "sl": sl,
            "outcome": outcome,
            "pips_raw": pips,
        }
    except Exception as e:
        print(f"⚠️  Error calculating recap for {ticker}: {e}")
        return None


def build_recap_post():
    """Build the transparent daily recap post."""
    now_utc = datetime.now(timezone.utc)
    date_str = now_utc.strftime("%d %b %Y")
    is_weekend = now_utc.weekday() >= 5

    # Filter weekend vs weekday
    active_assets = [a for a in ASSETS if a["ticker"] in ("BTC-USD", "ETH-USD")] if is_weekend else ASSETS

    results = []
    wins = 0
    total = 0
    fx_pips_total = 0.0
    crypto_pts_total = 0.0

    lines = [
        f"🏁 <b>DAILY SIGNAL PERFORMANCE RECAP ({date_str})</b>",
        "<i>Total Transparency: Here is how today's setups resolved at the Daily Close:</i>\n",
        "━━━━━━━━━━━━━━━━━━━━",
    ]

    for asset in active_assets:
        res = fetch_day_performance(asset["ticker"])
        if not res:
            continue

        total += 1
        p = asset["prefix"]
        dec = asset["decimals"]
        pip_pts = int(round(res["pips_raw"] * asset["pip_mult"]))

        if asset["ticker"] in ("BTC-USD", "ETH-USD"):
            crypto_pts_total += pip_pts
            unit = "Pts"
        else:
            fx_pips_total += pip_pts
            unit = "Pips"

        outcome = res["outcome"]
        if outcome == "TP2_HIT":
            wins += 1
            badge = f"✅ <b>TARGET 1 & 2 SMASHED (+{abs(pip_pts)} {unit})</b> 🔥"
        elif outcome == "TP1_HIT":
            wins += 1
            badge = f"✅ <b>TARGET 1 HIT (+{abs(pip_pts)} {unit})</b> 🎯"
        elif outcome == "BREAKEVEN":
            wins += 1
            badge = f"⚪ <b>Closed at Break-Even / Profit (+{max(0, pip_pts)} {unit})</b>"
        elif outcome == "HOLD":
            badge = f"🔄 <b>Session Consolidated / In Play ({pip_pts:+d} {unit})</b>"
        else:
            badge = f"🛑 <b>Stop Loss Hit ({pip_pts:+d} {unit})</b>"

        sign_color = "🟢 BUY" if res["action"] == "BUY" else "🔴 SELL"
        lines.append(
            f"{asset['emoji']} <b>{asset['name']}:</b> {sign_color}\n"
            f"   • Result: {badge}\n"
        )

    win_rate = int(round((wins / max(1, total)) * 100))

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("📊 <b>TODAY'S SUMMARY SCORECARD:</b>")
    if not is_weekend:
        lines.append(f"• <b>Forex & Bullion Net:</b> <b>{fx_pips_total:+,.0f} Pips</b>")
    lines.append(f"• <b>Crypto Net:</b> <b>{crypto_pts_total:+,.0f} Points</b>")
    lines.append(f"• <b>Win Rate:</b> <b>{win_rate}% ({wins}/{total} setups profitable)</b>\n")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("💡 <i>Discipline beats emotion. Secure your daily gains, review your journal, and prepare for tomorrow's sessions!</i>\n")
    lines.append(
        f"📱 <b>COMPARE RAW SPREAD BROKERS:</b>\n"
        f"👉 <b><a href='{MAIN_APP_LINK}'>DOWNLOAD {MAIN_APP_NAME.upper()}</a></b>\n\n"
        f"💬 <b>OFFICIAL WHATSAPP CHANNEL:</b>\n"
        f"👉 <b><a href='{WHATSAPP_CHANNEL_LINK}'>JOIN & FOLLOW ON WHATSAPP</a></b>"
    )

    return "\n".join(lines)


def send_telegram(html_text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": html_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    resp = requests.post(url, json=payload, timeout=20)
    resp.raise_for_status()
    print("✅ Daily recap posted to Telegram.")


def send_discord(html_text):
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        date_str = datetime.now(timezone.utc).strftime("%d %b %Y")
        embed = {
            "title": f"🏁 Daily Signal Performance Recap — {date_str}",
            "description": html_text[:2000],
            "color": 0x26A69A,
            "footer": {"text": "Join our Telegram for daily live signals"},
        }
        requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, timeout=15)
        print("✅ Daily recap posted to Discord.")
    except Exception as e:
        print(f"⚠️ Discord recap failed: {e}")


if __name__ == "__main__":
    print("🚀 Calculating Daily Performance Recap...")
    post = build_recap_post()
    send_telegram(post)
    send_discord(post)
    print("🎉 Daily recap complete!")
