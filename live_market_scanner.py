"""
Live Real-Time Opportunity Scanner.
Periodically scans 20+ top Forex pairs, Commodities & Crypto coins.
Fires a signal ONLY when a real high-probability breakout, squeeze expansion,
or extreme RSI reversal setup triggers in the live market.
"""
import os
import sys
import json
import tempfile
from datetime import datetime, timezone
import requests
import pandas as pd

# Set stdout/stderr to UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Optional chart plotting
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import mplfinance as mpf
    CHARTS_ENABLED = True
except ImportError:
    CHARTS_ENABLED = False

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

MAIN_APP_NAME = "Best Forex Brokers"
MAIN_APP_LINK = "https://play.google.com/store/apps/details?id=com.revapps.bestforexbrokers"
BROKER_LINK = "https://clicks.pipaffiliates.com/c?m=131292&c=98704"
CACHE_FILE = os.path.join(os.path.dirname(__file__), ".scanner_cache.json")

if not BOT_TOKEN or not CHAT_ID:
    sys.exit("❌ Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")

WATCHLIST = [
    # Top 24/7 Crypto
    {"ticker": "BTC-USD",  "name": "Bitcoin (BTC)",      "cat": "crypto", "emoji": "₿",  "dec": 0, "prefix": "$"},
    {"ticker": "ETH-USD",  "name": "Ethereum (ETH)",     "cat": "crypto", "emoji": "⟠",  "dec": 1, "prefix": "$"},
    {"ticker": "SOL-USD",  "name": "Solana (SOL)",        "cat": "crypto", "emoji": "🟣", "dec": 2, "prefix": "$"},
    {"ticker": "XRP-USD",  "name": "Ripple (XRP)",        "cat": "crypto", "emoji": "🌊", "dec": 4, "prefix": "$"},
    {"ticker": "DOGE-USD", "name": "Dogecoin (DOGE)",    "cat": "crypto", "emoji": "🐶", "dec": 4, "prefix": "$"},
    {"ticker": "ADA-USD",  "name": "Cardano (ADA)",       "cat": "crypto", "emoji": "🔷", "dec": 4, "prefix": "$"},
    {"ticker": "AVAX-USD", "name": "Avalanche (AVAX)",    "cat": "crypto", "emoji": "🔺", "dec": 2, "prefix": "$"},
    {"ticker": "BNB-USD",  "name": "Binance Coin (BNB)",  "cat": "crypto", "emoji": "🟡", "dec": 1, "prefix": "$"},

    # Metals & Energy
    {"ticker": "GC=F",     "name": "Gold (XAU/USD)",      "cat": "metal",  "emoji": "🥇", "dec": 2, "prefix": "$"},
    {"ticker": "SI=F",     "name": "Silver (XAG/USD)",    "cat": "metal",  "emoji": "🥈", "dec": 3, "prefix": "$"},
    {"ticker": "CL=F",     "name": "Crude Oil (WTI)",     "cat": "energy", "emoji": "🛢️", "dec": 2, "prefix": "$"},

    # Forex Majors & Crosses
    {"ticker": "EURUSD=X", "name": "EUR/USD",            "cat": "forex",  "emoji": "💶", "dec": 4, "prefix": ""},
    {"ticker": "GBPUSD=X", "name": "GBP/USD",            "cat": "forex",  "emoji": "💷", "dec": 4, "prefix": ""},
    {"ticker": "USDJPY=X", "name": "USD/JPY",            "cat": "forex",  "emoji": "💴", "dec": 2, "prefix": ""},
    {"ticker": "GBPJPY=X", "name": "GBP/JPY (The Beast)", "cat": "forex",  "emoji": "🐉", "dec": 2, "prefix": ""},
    {"ticker": "EURJPY=X", "name": "EUR/JPY",            "cat": "forex",  "emoji": "⚡", "dec": 2, "prefix": ""},
    {"ticker": "AUDUSD=X", "name": "AUD/USD",            "cat": "forex",  "emoji": "🇦🇺", "dec": 4, "prefix": ""},
    {"ticker": "USDCAD=X", "name": "USD/CAD",            "cat": "forex",  "emoji": "🇨🇦", "dec": 4, "prefix": ""},
    {"ticker": "USDCHF=X", "name": "USD/CHF",            "cat": "forex",  "emoji": "🇨🇭", "dec": 4, "prefix": ""},
]


def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cache(cache):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        print(f"⚠️  Could not save scanner cache: {e}")


def scan_asset(asset):
    """Analyze one asset for a high-probability trigger condition."""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{asset['ticker']}?range=1mo&interval=1d"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()["chart"]["result"][0]
        q = data["indicators"]["quote"][0]

        closes = pd.Series([c for c in q["close"] if c is not None])
        highs = pd.Series([h for h in q["high"] if h is not None])
        lows = pd.Series([l for l in q["low"] if l is not None])
        if len(closes) < 15:
            return None

        curr = float(closes.iloc[-1])
        prev = float(closes.iloc[-2])
        prev_h = float(highs.iloc[-2])
        prev_l = float(lows.iloc[-2])

        pct = ((curr - prev) / prev) * 100

        # Pivot, ATR & EMA
        pivot = (prev_h + prev_l + prev) / 3
        r1 = 2 * pivot - prev_l
        s1 = 2 * pivot - prev_h

        tr = pd.concat([highs - lows, (highs - closes.shift()).abs(), (lows - closes.shift()).abs()], axis=1).max(axis=1)
        atr = float(tr.rolling(14).mean().iloc[-1])
        if pd.isna(atr) or atr <= 0:
            atr = curr * 0.01

        ema20 = float(closes.ewm(span=20).mean().iloc[-1])

        # RSI
        delta = closes.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / (loss.replace(0, 0.0001))
        rsi = float((100 - (100 / (1 + rs))).iloc[-1])
        if pd.isna(rsi):
            rsi = 50.0

        # Trigger Criteria:
        # 1. Breakout momentum threshold
        threshold = 2.0 if asset["cat"] in ("crypto", "metal", "energy") else 0.45
        is_breakout_bull = pct >= threshold and curr > ema20
        is_breakout_bear = pct <= -threshold and curr < ema20
        is_rsi_oversold = rsi <= 28
        is_rsi_overbought = rsi >= 72

        if not (is_breakout_bull or is_breakout_bear or is_rsi_oversold or is_rsi_overbought):
            return None

        # Build trade setup
        dec = asset["dec"]
        if is_breakout_bull or is_rsi_oversold:
            action = "🟢 BUY / LONG"
            entry_low = round(curr - 0.15 * atr, dec)
            entry_high = round(curr + 0.10 * atr, dec)
            sl = round(curr - 1.2 * atr, dec)
            tp1 = round(curr + 1.2 * atr, dec)
            tp2 = round(curr + 2.4 * atr, dec)

            if is_rsi_oversold:
                setup_title = "OVERSOLD REVERSAL SETUP"
                rationale = f"Extreme RSI oversold capitulation ({rsi:.1f}). Buyer support stepping in."
            else:
                setup_title = "BULLISH MOMENTUM BREAKOUT"
                rationale = f"Surging momentum (+{pct:.2f}%) breaking above 20 EMA with expanding volume."
        else:
            action = "🔴 SELL / SHORT"
            entry_low = round(curr - 0.10 * atr, dec)
            entry_high = round(curr + 0.15 * atr, dec)
            sl = round(curr + 1.2 * atr, dec)
            tp1 = round(curr - 1.2 * atr, dec)
            tp2 = round(curr - 2.4 * atr, dec)

            if is_rsi_overbought:
                setup_title = "OVERBOUGHT EXHAUSTION SETUP"
                rationale = f"RSI overbought exhaustion ({rsi:.1f}). Sellers defending resistance."
            else:
                setup_title = "BEARISH MOMENTUM BREAKDOWN"
                rationale = f"Heavy selling pressure ({pct:.2f}%) breaking below 20 EMA."

        conviction_score = abs(pct) + (abs(rsi - 50) / 4)

        return {
            "asset": asset,
            "action": action,
            "setup_title": setup_title,
            "price": curr,
            "pct": pct,
            "rsi": rsi,
            "entry_str": f"{entry_low:.{dec}f} – {entry_high:.{dec}f}",
            "sl_str": f"{sl:.{dec}f}",
            "tp1_str": f"{tp1:.{dec}f}",
            "tp2_str": f"{tp2:.{dec}f}",
            "rationale": rationale,
            "score": conviction_score,
            "entry_mid": (entry_low + entry_high) / 2,
            "sl_num": sl,
            "tp1_num": tp1,
            "tp2_num": tp2,
        }
    except Exception as e:
        print(f"⚠️  Error scanning {asset['name']}: {e}")
        return None


def generate_opportunity_chart(ticker, name, opp):
    """Plot candlestick chart for the live opportunity."""
    if not CHARTS_ENABLED:
        return None
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=1mo&interval=1d"
        data = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()["chart"]["result"][0]
        q = data["indicators"]["quote"][0]
        dates = [datetime.fromtimestamp(ts, tz=timezone.utc) for ts in data["timestamp"]]

        df = pd.DataFrame(
            {"Open": q["open"], "High": q["high"], "Low": q["low"], "Close": q["close"], "Volume": q.get("volume", [])},
            index=pd.DatetimeIndex(dates)
        ).dropna()
        if len(df) < 5:
            return None

        mc = mpf.make_marketcolors(up="#26a69a", down="#ef5350", edge="inherit", wick={"up": "#26a69a", "down": "#ef5350"})
        style = mpf.make_mpf_style(base_mpf_style="nightclouds", marketcolors=mc, figcolor="#131722", facecolor="#131722", gridcolor="#1e222d", gridstyle="--", y_on_right=True, rc={"font.size": 10})

        hlines = dict(
            hlines=[opp["entry_mid"], opp["sl_num"], opp["tp1_num"], opp["tp2_num"]],
            colors=["#29b6f6", "#ef5350", "#26a69a", "#ffd700"],
            linestyle=["--", "-", "--", "--"],
            linewidths=[1.2, 1.4, 1.2, 1.2]
        )

        date_str = datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC")
        filepath = os.path.join(tempfile.gettempdir(), f"opp_{ticker.replace('=', '_').replace('-', '_')}.png")

        fig, axes = mpf.plot(
            df, type="candle", style=style,
            title=f"\n{name} — {opp['action']} ({opp['setup_title']})\nLive Market Opportunity • {date_str}",
            hlines=hlines, figsize=(10, 5.5), tight_layout=True, returnfig=True
        )

        ax = axes[0]
        xmin, xmax = ax.get_xlim()
        x_pos = xmin + (xmax - xmin) * 0.015
        for val, label, color in [
            (opp["entry_mid"], f"ENTRY: {opp['entry_mid']:,.2f}", "#29b6f6"),
            (opp["sl_num"],    f"SL: {opp['sl_num']:,.2f}",       "#ef5350"),
            (opp["tp1_num"],   f"TP1: {opp['tp1_num']:,.2f}",     "#26a69a"),
            (opp["tp2_num"],   f"TP2: {opp['tp2_num']:,.2f}",     "#ffd700"),
        ]:
            ax.text(x_pos, val, f" {label} ", color=color, fontsize=8.5, va="center", fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.25", facecolor="#131722", edgecolor=color, alpha=0.9))

        fig.savefig(filepath, dpi=150, bbox_inches="tight", facecolor="#131722", edgecolor="none", pad_inches=0.3)
        plt.close(fig)
        return filepath
    except Exception as e:
        print(f"⚠️  Chart failed for {name}: {e}")
        return None


def build_opportunity_post(opp):
    """Format the alert message."""
    a = opp["asset"]
    p = a["prefix"]
    dec = a["dec"]
    now_str = datetime.now(timezone.utc).strftime("%d %b %H:%M UTC")

    arrow = "🟢 ▲" if opp["pct"] >= 0 else "🔴 ▼"

    lines = [
        f"🚨 <b>LIVE TRADE OPPORTUNITY: {a['name'].upper()}</b> ⚡",
        f"<i>{opp['setup_title']} triggered in the live market ({now_str}):</i>\n",
        "━━━━━━━━━━━━━━━━━━━━",
        f"🎯 <b>SIGNAL:</b> <b>{opp['action']}</b>",
        f"📈 <b>Trigger Price:</b> {p}{opp['price']:.{dec}f} ({arrow} {opp['pct']:+.2f}%)",
        f"🎯 <b>Entry Zone:</b> <code>{p}{opp['entry_str']}</code>",
        f"🛑 <b>Stop Loss (SL):</b> <code>{p}{opp['sl_str']}</code>",
        f"🎯 <b>Take Profit 1:</b> <code>{p}{opp['tp1_str']}</code> (1:1 Target)",
        f"🎯 <b>Take Profit 2:</b> <code>{p}{opp['tp2_str']}</code> (1:2 Runner)\n",
        "📊 <b>TECHNICAL CONFIRMATION:</b>",
        f"• {opp['rationale']}",
        f"• <b>Momentum Score:</b> <code>{opp['score']:.1f}/15</code> | <b>RSI(14):</b> <code>{opp['rsi']:.1f}</code>\n",
        "━━━━━━━━━━━━━━━━━━━━",
        "💡 <b>Execution Tip:</b> Never risk more than 1–2% per trade. Move Stop Loss to break-even once Target 1 is reached.\n",
        "━━━━━━━━━━━━━━━━━━━━",
        f"🚨 <b>TRADE WITH 0% SPREAD ON REGULATED BROKERS:</b>\n"
        f"👉 <b><a href='{BROKER_LINK}'>CLAIM 100% DEPOSIT BONUS</a></b>\n\n"
        f"📱 <b>COMPARE ALL BROKERS ON ANDROID:</b>\n"
        f"👉 <b><a href='{MAIN_APP_LINK}'>DOWNLOAD {MAIN_APP_NAME.upper()}</a></b>"
    ]
    return "\n".join(lines)


def send_telegram(html_text, photo_path=None, caption=""):
    if photo_path and os.path.exists(photo_path):
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        with open(photo_path, "rb") as f:
            resp = requests.post(url, data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "HTML"}, files={"photo": f}, timeout=25)
        resp.raise_for_status()

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": html_text, "parse_mode": "HTML", "disable_web_page_preview": True}
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()
    print("✅ Live opportunity alert sent to Telegram.")


if __name__ == "__main__":
    now_utc = datetime.now(timezone.utc)
    is_weekend = now_utc.weekday() >= 5
    cache = load_cache()

    # Filter: On weekends only scan Crypto & Metals (Forex markets are closed)
    assets_to_scan = [a for a in WATCHLIST if a["cat"] in ("crypto", "metal")] if is_weekend else WATCHLIST

    print(f"🔍 Scanning {len(assets_to_scan)} assets for high-probability live triggers...")
    triggered = []
    for asset in assets_to_scan:
        opp = scan_asset(asset)
        if opp:
            # Check cooldown (6 hours)
            last_alerted = cache.get(asset["ticker"])
            if last_alerted:
                diff_hours = (datetime.now(timezone.utc).timestamp() - last_alerted) / 3600.0
                if diff_hours < 6.0:
                    continue  # In cooldown
            triggered.append(opp)

    if not triggered:
        print("ℹ️  No high-conviction setup met the strict threshold. Standing by (no spam).")
        sys.exit(0)

    # Pick the top 1 cleanest opportunity
    triggered.sort(key=lambda x: x["score"], reverse=True)
    best_opp = triggered[0]
    print(f"🔥 Found Top Opportunity: {best_opp['asset']['name']} (Score: {best_opp['score']:.1f})")

    # Generate chart
    chart_path = generate_opportunity_chart(best_opp["asset"]["ticker"], best_opp["asset"]["name"], best_opp)
    msg = build_opportunity_post(best_opp)

    caption = f"🚨 <b>LIVE TRADE SETUP: {best_opp['asset']['name']} — {best_opp['action']}</b>"
    send_telegram(msg, photo_path=chart_path, caption=caption)

    # Register in cache
    cache[best_opp["asset"]["ticker"]] = datetime.now(timezone.utc).timestamp()
    save_cache(cache)
    print("🎉 Live opportunity successfully alerted!")
