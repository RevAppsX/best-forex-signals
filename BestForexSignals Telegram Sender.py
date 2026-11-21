"""
BestForexSignals Telegram Sender
Daily forex signals with chart, economic calendar, and multi-platform posting.
"""
import os
import sys
import tempfile
from datetime import datetime, timezone
import time
import requests

# Set stdout/stderr to UTF-8 to prevent Windows terminal charmap encoding issues
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import pandas as pd

# --- Chart dependencies (optional for local testing, installed in GitHub Actions) ---
try:
    import matplotlib
    matplotlib.use("Agg")  # Headless backend for CI
    import matplotlib.pyplot as plt
    import mplfinance as mpf
    CHARTS_ENABLED = True
except ImportError:
    CHARTS_ENABLED = False
    print("[INFO] Chart plotting library not installed locally (will run in GitHub Actions).")

# --- Twitter dependency (optional) ---
try:
    import tweepy
    TWEEPY_AVAILABLE = True
except ImportError:
    TWEEPY_AVAILABLE = False


# ======================== CONFIGURATION ========================
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Optional: crossposting credentials (set via GitHub Secrets)
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
TWITTER_API_KEY = os.environ.get("TWITTER_API_KEY")
TWITTER_API_SECRET = os.environ.get("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.environ.get("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_TOKEN_SECRET = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")
TELEGRAM_GROUP_LINK = os.environ.get("TELEGRAM_GROUP_LINK", "https://t.me/YOUR_GROUP")

if not BOT_TOKEN or not CHAT_ID:
    sys.exit(
        "❌ Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID.\n"
        "   GitHub: Settings → Secrets → Actions\n"
        "   Local:  set TELEGRAM_BOT_TOKEN=... & set TELEGRAM_CHAT_ID=..."
    )

# --- Apps & Broker Links ---
MAIN_APP_NAME = "Best Forex Brokers"
MAIN_APP_LINK = "https://play.google.com/store/apps/details?id=com.revapps.bestforexbrokers"
BROKER_LINK = "https://clicks.pipaffiliates.com/c?m=131292&c=98704"

# Google Play Developer page or portfolio link (for your other 200+ apps)
PLAY_STORE_DEV_LINK = os.environ.get(
    "PLAY_STORE_DEV_LINK",
    "https://play.google.com/store/apps/developer?id=RevApps",
)

# Optional rotation of your other trading/crypto apps (picked by day of month)
# Add any package names / URLs from your 200+ portfolio here
ROTATING_APPS = [
    {
        "name": "Live Currency & Crypto Rates",
        "url": PLAY_STORE_DEV_LINK,
        "tagline": "Real-time FX & Crypto Rates",
    },
    {
        "name": "Forex Margin & Pip Calculator",
        "url": PLAY_STORE_DEV_LINK,
        "tagline": "Calculate Lots, Pip Value & Margin in Seconds",
    },
    {
        "name": "Gold & Commodities Live Tracker",
        "url": PLAY_STORE_DEV_LINK,
        "tagline": "Track Live Bullion & Energy Prices",
    },
    {
        "name": "Forex News & Economic Calendar",
        "url": PLAY_STORE_DEV_LINK,
        "tagline": "Daily Macro Releases & Central Bank Alerts",
    },
]

MYFXBOOK_CALENDAR_LINK = "https://www.myfxbook.com/forex-economic-calendar"

# Major currencies tracked for High-Impact news
MAJOR_CURRENCIES = ("USD", "EUR", "GBP", "JPY", "AUD", "CAD", "NZD", "CHF")
CURRENCY_FLAGS = {
    "USD": "🇺🇸", "EUR": "🇪🇺", "GBP": "🇬🇧", "JPY": "🇯🇵",
    "AUD": "🇦🇺", "CAD": "🇨🇦", "NZD": "🇳🇿", "CHF": "🇨🇭",
}

POST_HOUR = 6  # 06:05 UTC = 09:05 AM in UTC+3 (TRT/Local)
POST_MINUTE = 5
# ================================================================

DAILY_TIPS = [
    "💡 <b>Risk Rule:</b> Never risk more than 1–2% of your account equity on a single Gold (XAU/USD) setup—especially ahead of US session opens.",
    "💡 <b>Session Timing:</b> The highest liquidity and cleanest breakouts on EUR/USD and Gold occur during the London–New York overlap (15:00–19:00 TRT).",
    "💡 <b>Broker Tip:</b> Always check swap fees and raw spread commissions before holding indices or Gold positions overnight.",
    "💡 <b>Trading Psychology:</b> Wait for candle close confirmation above/below key pivot levels rather than chasing sudden news spikes.",
]

PAIRS = [
    {"ticker": "GC=F",     "name": "Gold (XAU/USD)", "emoji": "🥇", "decimals": 2, "prefix": "$", "type": "metal"},
    {"ticker": "BTC-USD",  "name": "Bitcoin (BTC)",  "emoji": "₿",  "decimals": 0, "prefix": "$", "type": "crypto"},
    {"ticker": "ETH-USD",  "name": "Ethereum (ETH)", "emoji": "⟠",  "decimals": 1, "prefix": "$", "type": "crypto"},
    {"ticker": "EURUSD=X", "name": "EUR/USD",        "emoji": "💶", "decimals": 4, "prefix": "",  "type": "forex"},
    {"ticker": "GBPUSD=X", "name": "GBP/USD",        "emoji": "💷", "decimals": 4, "prefix": "",  "type": "forex"},
    {"ticker": "USDJPY=X", "name": "USD/JPY",        "emoji": "💴", "decimals": 2, "prefix": "",  "type": "forex"},
]


# ======================== DATA FETCHING ========================

def fetch_yahoo_ohlc(ticker_symbol, range_period="5d", interval="1d"):
    """Fetch OHLC data from Yahoo Finance direct API."""
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker_symbol}"
        f"?range={range_period}&interval={interval}"
    )
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    result = data["chart"]["result"][0]
    quotes = result["indicators"]["quote"][0]
    return {
        "timestamps": result["timestamp"],
        "opens":   quotes["open"],
        "highs":   quotes["high"],
        "lows":    quotes["low"],
        "closes":  quotes["close"],
        "volumes": quotes.get("volume", []),
    }


def calculate_currency_strength():
    """Calculate 24h Currency Strength Matrix across 8 major currencies."""
    tickers = {
        "EUR": ("EURUSD=X", False),
        "GBP": ("GBPUSD=X", False),
        "AUD": ("AUDUSD=X", False),
        "NZD": ("NZDUSD=X", False),
        "JPY": ("USDJPY=X", True),
        "CAD": ("USDCAD=X", True),
        "CHF": ("USDCHF=X", True),
    }

    scores = {}
    for curr, (sym, inverted) in tickers.items():
        try:
            ohlc = fetch_yahoo_ohlc(sym, range_period="5d", interval="1d")
            closes = [c for c in ohlc["closes"] if c is not None]
            if len(closes) >= 2:
                pct = ((closes[-1] - closes[-2]) / closes[-2]) * 100
                scores[curr] = -pct if inverted else pct
            else:
                scores[curr] = 0.0
        except Exception:
            scores[curr] = 0.0

    scores["USD"] = -sum(scores.values()) / max(len(scores), 1)

    min_val = min(scores.values())
    max_val = max(scores.values())
    diff = max_val - min_val if max_val != min_val else 1.0

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return ranked, min_val, diff


def build_currency_strength_section():
    """Format Currency Strength Matrix as HTML."""
    try:
        ranked, min_val, diff = calculate_currency_strength()
        if not ranked:
            return ""

        lines = [
            "💪 <b>CURRENCY STRENGTH MATRIX (24H):</b>",
        ]
        for i, (curr, raw) in enumerate(ranked):
            score = 1.0 + (raw - min_val) / diff * 9.0
            bars = max(1, min(10, int(round(score))))
            flag = CURRENCY_FLAGS.get(curr, "🌐")
            if i < 2:
                bar_str = "🟩" * bars + "⬜" * (10 - bars)
                status = "Strong"
            elif i > len(ranked) - 3:
                bar_str = "🟥" * bars + "⬜" * (10 - bars)
                status = "Weak"
            else:
                bar_str = "🟨" * bars + "⬜" * (10 - bars)
                status = "Neutral"

            lines.append(f"• {flag} <b>{curr}:</b> <code>{bar_str}</code> {score:.1f} ({status})")

        strongest = ranked[0][0]
        weakest = ranked[-1][0]
        lines.append(f"\n🔥 <b>Momentum Edge:</b> BUY <b>{strongest}/{weakest}</b> (Strongest vs Weakest)\n")
        return "\n".join(lines)
    except Exception as e:
        print(f"⚠️  Error calculating currency strength: {e}")
        return ""


def calculate_signals(ohlc, decimals=4):
    """
    Calculate institutional trading signals:
    - Directional Bias (BUY / SELL / BUY ON DIP / SELL ON RALLY)
    - Actionable Entry Zone, Stop Loss (SL), Take Profit (TP1 & TP2)
    - Daily Pivots (Classic Pivot, R1, S1)
    - 20 EMA, 14 ATR, and 14 RSI for technical confirmation
    """
    closes = pd.Series([c for c in ohlc["closes"] if c is not None])
    highs = pd.Series([h for h in ohlc["highs"] if h is not None])
    lows = pd.Series([l for l in ohlc["lows"] if l is not None])

    if len(closes) < 15:
        return None

    curr_price = float(closes.iloc[-1])
    prev_close = float(closes.iloc[-2])
    prev_high = float(highs.iloc[-2])
    prev_low = float(lows.iloc[-2])

    pct_change = ((curr_price - prev_close) / prev_close) * 100

    # Daily Pivots
    pivot = (prev_high + prev_low + prev_close) / 3
    r1 = 2 * pivot - prev_low
    s1 = 2 * pivot - prev_high

    # ATR (14-period Average True Range for volatility-based SL/TP)
    tr = pd.concat(
        [
            highs - lows,
            (highs - closes.shift()).abs(),
            (lows - closes.shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = float(tr.rolling(14).mean().iloc[-1])
    if pd.isna(atr) or atr <= 0:
        atr = curr_price * 0.008

    # 20 EMA
    ema20 = float(closes.ewm(span=20).mean().iloc[-1])

    # 14 RSI
    delta = closes.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / (loss.replace(0, 0.0001))
    rsi = float((100 - (100 / (1 + rs))).iloc[-1])
    if pd.isna(rsi):
        rsi = 50.0

    # Determine Actionable Signal Setup
    if curr_price >= pivot and curr_price >= ema20:
        action = "🟢 BUY / LONG"
        entry_low = curr_price - 0.15 * atr
        entry_high = curr_price + 0.10 * atr
        sl = curr_price - 1.2 * atr
        tp1 = curr_price + 1.2 * atr
        tp2 = curr_price + 2.4 * atr
        rationale = f"Bullish structure above Daily Pivot & 20 EMA (RSI: {rsi:.0f})"
    elif curr_price < pivot and curr_price < ema20:
        action = "🔴 SELL / SHORT"
        entry_low = curr_price - 0.10 * atr
        entry_high = curr_price + 0.15 * atr
        sl = curr_price + 1.2 * atr
        tp1 = curr_price - 1.2 * atr
        tp2 = curr_price - 2.4 * atr
        rationale = f"Bearish momentum below Daily Pivot & 20 EMA (RSI: {rsi:.0f})"
    elif curr_price >= pivot:
        action = "🟢 BUY ON DIP"
        entry_low = max(s1, curr_price - 0.4 * atr)
        entry_high = curr_price
        sl = s1 - 0.5 * atr
        tp1 = r1
        tp2 = r1 + 1.0 * atr
        rationale = f"Holding above Daily Pivot. Look for pullback entry near support (RSI: {rsi:.0f})"
    else:
        action = "🔴 SELL ON RALLY"
        entry_low = curr_price
        entry_high = min(r1, curr_price + 0.4 * atr)
        sl = r1 + 0.5 * atr
        tp1 = s1
        tp2 = s1 - 1.0 * atr
        rationale = f"Rejected below Daily Pivot. Look for rally fade near resistance (RSI: {rsi:.0f})"

    arrow = "🟢 ▲" if pct_change >= 0 else "🔴 ▼"

    return {
        "price": round(curr_price, decimals),
        "price_str": f"{curr_price:.{decimals}f}",
        "change_str": f"{arrow} {pct_change:+.2f}%",
        "action": action,
        "entry_low": round(entry_low, decimals),
        "entry_high": round(entry_high, decimals),
        "entry_str": f"{entry_low:.{decimals}f} – {entry_high:.{decimals}f}",
        "sl": round(sl, decimals),
        "sl_str": f"{sl:.{decimals}f}",
        "tp1": round(tp1, decimals),
        "tp1_str": f"{tp1:.{decimals}f}",
        "tp2": round(tp2, decimals),
        "tp2_str": f"{tp2:.{decimals}f}",
        "pivot": round(pivot, decimals),
        "pivot_str": f"{pivot:.{decimals}f}",
        "r1": round(r1, decimals),
        "r1_str": f"{r1:.{decimals}f}",
        "s1": round(s1, decimals),
        "s1_str": f"{s1:.{decimals}f}",
        "rsi": round(rsi, 1),
        "rationale": rationale,
    }


def get_pair_data(pair):
    """Fetch data and calculate actionable signals for one currency pair."""
    try:
        ohlc = fetch_yahoo_ohlc(pair["ticker"], range_period="1mo", interval="1d")
        return calculate_signals(ohlc, pair["decimals"])
    except Exception as e:
        print(f"⚠️  Error fetching {pair['name']}: {e}")
        return None


def get_economic_calendar():
    """Fetch and parse this week's high-impact economic events from ForexFactory feed."""
    try:
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        events = resp.json()

        now_utc = datetime.now(timezone.utc)
        today_date = now_utc.date()

        parsed = []
        for ev in events:
            if ev.get("impact") == "High" and ev.get("country") in MAJOR_CURRENCIES:
                try:
                    dt = datetime.fromisoformat(ev["date"]).astimezone(timezone.utc)
                except Exception:
                    continue

                parsed.append({
                    "title": ev.get("title", "Event"),
                    "country": ev.get("country", ""),
                    "forecast": ev.get("forecast", ""),
                    "previous": ev.get("previous", ""),
                    "dt": dt,
                    "date_str": dt.strftime("%Y-%m-%d"),
                    "date_short": dt.strftime("%b %d"),
                    "day_name": dt.strftime("%a"),
                    "time_str": dt.strftime("%H:%M"),
                    "is_today": dt.date() == today_date,
                    "is_upcoming": dt >= now_utc,
                })

        return parsed
    except Exception as e:
        print(f"⚠️  Economic calendar unavailable: {e}")
        return []


# ======================== CHART GENERATION ========================

def generate_chart(ticker_symbol, pair_name, stats):
    """Generate a professional TradingView-style candlestick chart with visual Entry, SL, and TP levels."""
    if not CHARTS_ENABLED or stats is None:
        return None
    try:
        ohlc = fetch_yahoo_ohlc(ticker_symbol, range_period="1mo", interval="1d")

        dates = [
            datetime.fromtimestamp(ts, tz=timezone.utc) for ts in ohlc["timestamps"]
        ]
        df = pd.DataFrame(
            {
                "Open":   ohlc["opens"],
                "High":   ohlc["highs"],
                "Low":    ohlc["lows"],
                "Close":  ohlc["closes"],
                "Volume": ohlc["volumes"],
            },
            index=pd.DatetimeIndex(dates),
        )
        df = df.dropna()
        if len(df) < 5:
            print(f"⚠️  Not enough data to chart {pair_name}")
            return None

        # TradingView dark theme
        mc = mpf.make_marketcolors(
            up="#26a69a", down="#ef5350", edge="inherit",
            wick={"up": "#26a69a", "down": "#ef5350"},
        )
        style = mpf.make_mpf_style(
            base_mpf_style="nightclouds", marketcolors=mc,
            figcolor="#131722", facecolor="#131722",
            gridcolor="#1e222d", gridstyle="--",
            y_on_right=True, rc={"font.size": 10},
        )

        entry_mid = (stats["entry_low"] + stats["entry_high"]) / 2
        sl = stats["sl"]
        tp1 = stats["tp1"]
        tp2 = stats["tp2"]

        hlines = dict(
            hlines=[entry_mid, sl, tp1, tp2],
            colors=["#29b6f6", "#ef5350", "#26a69a", "#ffd700"],
            linestyle=["--", "-", "--", "--"],
            linewidths=[1.2, 1.4, 1.2, 1.2],
        )

        date_str = datetime.now(timezone.utc).strftime("%d %b %Y")
        filepath = os.path.join(tempfile.gettempdir(), "signal_chart.png")

        fig, axes = mpf.plot(
            df, type="candle", style=style,
            title=f"\n{pair_name} — {stats['action']}\nTrade Setup & Key Target Levels • {date_str}",
            hlines=hlines, figsize=(10, 5.5),
            tight_layout=True, returnfig=True,
        )

        # Label each signal line inside the chart
        ax = axes[0]
        xmin, xmax = ax.get_xlim()
        x_pos = xmin + (xmax - xmin) * 0.015
        for val, label, color in [
            (entry_mid, f"ENTRY ZONE: {entry_mid:,.2f}", "#29b6f6"),
            (sl,        f"STOP LOSS: {sl:,.2f}",         "#ef5350"),
            (tp1,       f"TP 1: {tp1:,.2f}",             "#26a69a"),
            (tp2,       f"TP 2: {tp2:,.2f}",             "#ffd700"),
        ]:
            ax.text(
                x_pos, val, f" {label} ",
                color=color, fontsize=8.5, va="center", fontweight="bold",
                bbox=dict(
                    boxstyle="round,pad=0.25", facecolor="#131722",
                    edgecolor=color, alpha=0.9,
                ),
            )

        fig.savefig(
            filepath, dpi=150, bbox_inches="tight",
            facecolor="#131722", edgecolor="none", pad_inches=0.3,
        )
        plt.close(fig)
        print(f"📊 Signal chart saved → {filepath}")
        return filepath

    except Exception as e:
        print(f"⚠️  Chart generation failed for {pair_name}: {e}")
        return None


# ======================== MESSAGE BUILDING ========================

def build_calendar_section(events):
    """Format economic calendar: Today's High-Impact Radar + Upcoming Events."""
    now_utc = datetime.now(timezone.utc)

    if not events:
        return (
            "⚠️ <b>ECONOMIC CALENDAR:</b>\n"
            "✅ No high-impact events scheduled.\n"
            f"👉 <b><a href='{MYFXBOOK_CALENDAR_LINK}'>Live Calendar on Myfxbook</a></b>\n"
        )

    lines = []
    today_events = [ev for ev in events if ev["is_today"]]
    if today_events:
        lines.append("🚨 <b>TODAY'S HIGH-IMPACT RADAR:</b>")
        for ev in today_events[:6]:
            flag = CURRENCY_FLAGS.get(ev["country"], "🌐")
            fc_part = f" | FC: <code>{ev['forecast']}</code>" if ev["forecast"] else ""
            prev_part = f" | Prev: <code>{ev['previous']}</code>" if ev["previous"] else ""
            lines.append(
                f"• Today {ev['date_short']}, <b>{ev['time_str']} UTC</b> — {flag} <b>{ev['country']} {ev['title']}</b>{fc_part}{prev_part}"
            )
    else:
        lines.append("⚠️ <b>TODAY'S ECONOMIC RADAR:</b>")
        lines.append("✅ No high-impact releases scheduled for today.")
        upcoming = [ev for ev in events if ev["is_upcoming"]]
        if upcoming:
            next_ev = upcoming[0]
            flag = CURRENCY_FLAGS.get(next_ev["country"], "🌐")
            lines.append(
                f"👀 <i>Next High-Impact: {next_ev['day_name']} {next_ev['time_str']} UTC — {flag} {next_ev['country']} {next_ev['title']}</i>"
            )

    lines.append(
        f"👉 <b><a href='{MYFXBOOK_CALENDAR_LINK}'>Live Calendar on Myfxbook</a></b>\n"
    )
    return "\n".join(lines)


def build_market_post(pair_data, calendar_events):
    """Build the main actionable Telegram signal brief in HTML."""
    now_utc = datetime.now(timezone.utc)
    date_str = now_utc.strftime("%d %b %Y")
    is_weekend = now_utc.weekday() >= 5
    tip = DAILY_TIPS[now_utc.day % len(DAILY_TIPS)]
    today_app = ROTATING_APPS[now_utc.day % len(ROTATING_APPS)]

    if is_weekend:
        title = f"⚡ <b>WEEKEND 24/7 CRYPTO & BULLION SIGNALS ({date_str})</b>"
        subtitle = "<i>Actionable setups for Bitcoin, Ethereum & Gold while traditional forex banks are closed:</i>\n"
    else:
        title = f"🎯 <b>DAILY FOREX, GOLD & CRYPTO SIGNALS ({date_str})</b>"
        subtitle = "<i>Algorithmic VIP setups with precise Entry, Stop Loss (SL), and Take Profit (TP) targets:</i>\n"

    lines = [title, subtitle]

    for pair, stats in pair_data:
        if stats is None:
            continue
        p = pair["prefix"]

        # Featured layout for Gold and Bitcoin
        if pair["ticker"] in ("GC=F", "BTC-USD"):
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append(
                f"{pair['emoji']} <b>{pair['name'].upper()} — FEATURED SETUP:</b>\n"
                f"• <b>Signal:</b> <b>{stats['action']}</b>\n"
                f"• <b>Live Price:</b> {p}{stats['price_str']} ({stats['change_str']})\n"
                f"• <b>Entry Zone:</b> <code>{p}{stats['entry_str']}</code>\n"
                f"• <b>Stop Loss (SL):</b> <code>{p}{stats['sl_str']}</code>\n"
                f"• <b>Take Profit 1:</b> <code>{p}{stats['tp1_str']}</code> (1:1 Target)\n"
                f"• <b>Take Profit 2:</b> <code>{p}{stats['tp2_str']}</code> (1:2 Runner)\n"
                f"• <b>Confirmation:</b> <i>{stats['rationale']}</i>\n"
            )
        else:
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append(
                f"{pair['emoji']} <b>{pair['name'].upper()} SETUP:</b>\n"
                f"• <b>Signal:</b> <b>{stats['action']}</b> ({stats['change_str']})\n"
                f"• <b>Entry Zone:</b> <code>{p}{stats['entry_str']}</code>\n"
                f"• <b>Stop Loss (SL):</b> <code>{p}{stats['sl_str']}</code> | <b>TP:</b> <code>{p}{stats['tp1_str']}</code>\n"
                f"• <b>Key Levels:</b> Pivot: <code>{stats['pivot_str']}</code> | R1: <code>{stats['r1_str']}</code> | S1: <code>{stats['s1_str']}</code>\n"
            )

    # Add Currency Strength Matrix on weekdays
    if not is_weekend:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        cs_section = build_currency_strength_section()
        if cs_section:
            lines.append(cs_section)

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(build_calendar_section(calendar_events))
    lines.append(f"{tip}\n")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(
        f"🚨 <b>TOP BROKER OFFER | 100% BONUS UP TO $200:</b>\n"
        f"👉 <b><a href='{BROKER_LINK}'>CLICK HERE TO CLAIM YOUR BONUS</a></b>\n\n"
        f"📱 <b>COMPARE ALL REGULATED BROKERS & LIVE SPREADS:</b>\n"
        f"👉 <b><a href='{MAIN_APP_LINK}'>DOWNLOAD {MAIN_APP_NAME.upper()}</a></b>\n\n"
        f"🛠️ <b>FEATURED TRADER TOOL TODAY:</b>\n"
        f"👉 <b><a href='{today_app['url']}'>{today_app['name']} — {today_app['tagline']}</a></b>\n\n"
        f"🌐 <b>EXPLORE OUR 200+ APPS ON GOOGLE PLAY:</b>\n"
        f"👉 <b><a href='{PLAY_STORE_DEV_LINK}'>VIEW DEVELOPER PORTFOLIO</a></b>"
    )
    return "\n".join(lines)


def build_twitter_text(pair_data):
    """Build a ≤280-char teaser for X / Twitter."""
    date_str = datetime.now(timezone.utc).strftime("%d %b")
    parts = [f"🎯 Daily Forex Signals — {date_str}\n"]
    for pair, stats in pair_data[:2]:  # Gold + EUR/USD
        if stats is None:
            continue
        p = pair["prefix"]
        parts.append(f"{pair['emoji']} {pair['name']}: {stats['action']}")
        parts.append(f"  Entry: {p}{stats['entry_str']} | SL: {p}{stats['sl_str']} | TP: {p}{stats['tp1_str']}\n")
    parts.append(f"👉 Full setups: {TELEGRAM_GROUP_LINK}")
    return "\n".join(parts)[:280]


# ======================== POSTING ========================

def send_telegram_message(html_text):
    """Send an HTML message to Telegram."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": html_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()
    print("✅ Telegram message sent.")


def send_telegram_photo(photo_path, caption=""):
    """Send a photo with optional caption to Telegram."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    data = {"chat_id": CHAT_ID, "caption": caption, "parse_mode": "HTML"}
    with open(photo_path, "rb") as photo:
        resp = requests.post(url, data=data, files={"photo": photo}, timeout=30)
    resp.raise_for_status()
    print("✅ Telegram photo sent.")


def post_to_discord(pair_data, calendar_events):
    """Post a rich embed to Discord via webhook (skipped if URL not set)."""
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        date_str = datetime.now(timezone.utc).strftime("%d %b %Y")
        flags = {"USD": "🇺🇸", "EUR": "🇪🇺", "GBP": "🇬🇧"}
        fields = []

        for pair, stats in pair_data:
            if stats is None:
                continue
            p = pair["prefix"]
            fields.append({
                "name": f"{pair['emoji']} {pair['name']} — {stats['action']}",
                "value": (
                    f"**Entry Zone:** `{p}{stats['entry_str']}`\n"
                    f"**SL:** `{p}{stats['sl_str']}` | **TP:** `{p}{stats['tp1_str']}`\n"
                    f"*{stats['rationale']}*"
                ),
                "inline": False,
            })

        if calendar_events:
            today_evs = [ev for ev in calendar_events if ev.get("is_today")]
            show_evs = today_evs if today_evs else calendar_events[:4]
            cal_lines = [
                f"{flags.get(ev.get('country'), '🌐')} **{ev.get('day_name', '')} {ev.get('time_str', '')} UTC** — {ev.get('title', '?')}"
                for ev in show_evs[:4]
            ]
            cal_lines.append(f"[📅 View Live Calendar on Myfxbook]({MYFXBOOK_CALENDAR_LINK})")
            fields.append({
                "name": "⚠️ High-Impact Economic Events",
                "value": "\n".join(cal_lines),
                "inline": False,
            })

        fields.append({
            "name": "📱 Trading Apps & Tools",
            "value": (
                f"• [{MAIN_APP_NAME}]({MAIN_APP_LINK}) — Compare Regulated Brokers\n"
                f"• [Explore 200+ Apps on Google Play]({PLAY_STORE_DEV_LINK})"
            ),
            "inline": False,
        })

        embed = {
            "title": f"📊 Daily Market Brief — {date_str}",
            "color": 0x26A69A,
            "fields": fields,
            "footer": {"text": "Join our Telegram for daily signals & charts"},
            "url": TELEGRAM_GROUP_LINK,
        }
        resp = requests.post(
            DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, timeout=15
        )
        resp.raise_for_status()
        print("✅ Discord post sent.")
    except Exception as e:
        print(f"⚠️  Discord posting failed: {e}")


def post_to_twitter(pair_data):
    """Post a teaser to X / Twitter (skipped if credentials not set)."""
    if not TWEEPY_AVAILABLE:
        return
    if not all([
        TWITTER_API_KEY, TWITTER_API_SECRET,
        TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET,
    ]):
        return
    try:
        client = tweepy.Client(
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_TOKEN_SECRET,
        )
        text = build_twitter_text(pair_data)
        client.create_tweet(text=text)
        print("✅ Tweet posted.")
    except Exception as e:
        print(f"⚠️  Twitter posting failed: {e}")


# ======================== MAIN ========================

def run_daily_signal():
    """Generate and send the daily market brief across all platforms."""
    now_utc = datetime.now(timezone.utc)
    is_weekend = now_utc.weekday() >= 5  # Saturday = 5, Sunday = 6

    # Select active assets: On weekends, focus on 24/7 Crypto + Gold bullion levels
    if is_weekend:
        print("⚡ Weekend detected: Running 24/7 Crypto & Bullion signal engine...")
        active_pairs = [p for p in PAIRS if p["type"] in ("crypto", "metal")]
    else:
        print("🎯 Weekday detected: Running full Forex, Gold & Crypto signal engine...")
        active_pairs = PAIRS

    print("⏳ Fetching market data...")
    pair_data = [(pair, get_pair_data(pair)) for pair in active_pairs]

    print("📅 Fetching economic calendar...")
    calendar_events = get_economic_calendar()

    # Generate Chart: On weekends chart Bitcoin; on weekdays chart Gold
    chart_pair = active_pairs[1] if (is_weekend and len(active_pairs) > 1) else active_pairs[0]
    chart_stats = next((s for p, s in pair_data if p["ticker"] == chart_pair["ticker"]), None)

    chart_path = None
    if chart_stats:
        print(f"📊 Generating {chart_pair['name']} signal chart...")
        chart_path = generate_chart(
            chart_pair["ticker"], chart_pair["name"], chart_stats
        )

    # Build text message
    post_html = build_market_post(pair_data, calendar_events)

    # --- Telegram ---
    if chart_path and chart_stats:
        p = chart_pair["prefix"]
        send_telegram_photo(
            chart_path,
            caption=(
                f"🎯 <b>{chart_pair['name']} — {chart_stats['action']}</b>\n"
                f"📈 Entry: <code>{p}{chart_stats['entry_str']}</code> | 🛑 SL: <code>{p}{chart_stats['sl_str']}</code> | 🎯 TP: <code>{p}{chart_stats['tp1_str']}</code>"
            ),
        )
    send_telegram_message(post_html)

    # --- Discord (optional) ---
    post_to_discord(pair_data, calendar_events)

    # --- Twitter / X (optional) ---
    post_to_twitter(pair_data)

    print("🎉 All done!")


if __name__ == "__main__":
    if os.environ.get("GITHUB_ACTIONS"):
        # --- CI MODE: run once and exit ---
        print("🤖 Running in GitHub Actions — sending signal now...")
        try:
            run_daily_signal()
        except Exception as e:
            print(f"❌ Fatal error: {e}")
            sys.exit(1)
    else:
        # --- LOCAL MODE: loop until scheduled time ---
        print(
            f"🤖 Telegram Autoposter started! "
            f"Scheduled to post daily at {POST_HOUR:02d}:{POST_MINUTE:02d}."
        )
        while True:
            now = datetime.now()
            if now.hour == POST_HOUR and now.minute == POST_MINUTE:
                try:
                    print("⏳ Generating and sending daily market brief...")
                    run_daily_signal()
                    time.sleep(61)
                except Exception as e:
                    print(f"❌ Error: {e}")
                    time.sleep(60)
            else:
                time.sleep(30)
