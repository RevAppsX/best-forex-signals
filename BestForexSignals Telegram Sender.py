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

# --- Chart dependencies (optional but recommended) ---
try:
    import matplotlib
    matplotlib.use("Agg")  # Headless backend for CI
    import matplotlib.pyplot as plt
    import mplfinance as mpf
    import pandas as pd
    CHARTS_ENABLED = True
except ImportError:
    CHARTS_ENABLED = False
    print("ℹ️  Chart generation disabled (pip install mplfinance to enable).")

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

POST_HOUR = 9
POST_MINUTE = 0
# ================================================================

DAILY_TIPS = [
    "💡 <b>Risk Rule:</b> Never risk more than 1–2% of your account equity on a single Gold (XAU/USD) setup—especially ahead of US session opens.",
    "💡 <b>Session Timing:</b> The highest liquidity and cleanest breakouts on EUR/USD and Gold occur during the London–New York overlap (15:00–19:00 TRT).",
    "💡 <b>Broker Tip:</b> Always check swap fees and raw spread commissions before holding indices or Gold positions overnight.",
    "💡 <b>Trading Psychology:</b> Wait for candle close confirmation above/below key pivot levels rather than chasing sudden news spikes.",
]

PAIRS = [
    {"ticker": "GC=F",    "name": "Gold (XAU/USD)", "emoji": "🥇", "decimals": 2, "prefix": "$"},
    {"ticker": "EURUSD=X", "name": "EUR/USD",       "emoji": "💶", "decimals": 4, "prefix": ""},
    {"ticker": "GBPUSD=X", "name": "GBP/USD",       "emoji": "💷", "decimals": 4, "prefix": ""},
    {"ticker": "USDJPY=X", "name": "USD/JPY",       "emoji": "💴", "decimals": 2, "prefix": ""},
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


def calculate_pivots(ohlc, decimals=4):
    """Calculate current price, % change, and Classic Pivot / R1 / S1."""
    closes, highs, lows = ohlc["closes"], ohlc["highs"], ohlc["lows"]
    valid = [
        i for i, c in enumerate(closes)
        if c is not None and highs[i] is not None and lows[i] is not None
    ]
    if len(valid) < 2:
        return None

    curr, prev = valid[-1], valid[-2]
    price = float(closes[curr])
    pc    = float(closes[prev])
    ph    = float(highs[prev])
    pl    = float(lows[prev])
    pct   = ((price - pc) / pc) * 100
    pivot = (ph + pl + pc) / 3
    r1    = 2 * pivot - pl
    s1    = 2 * pivot - ph
    arrow = "🟢 ▲" if pct >= 0 else "🔴 ▼"

    return {
        "price": round(price, decimals),
        "price_str":  f"{price:.{decimals}f}",
        "change_str": f"{arrow} {pct:+.2f}%",
        "pivot": round(pivot, decimals),
        "r1":    round(r1, decimals),
        "s1":    round(s1, decimals),
        "pivot_str": f"{pivot:.{decimals}f}",
        "r1_str":    f"{r1:.{decimals}f}",
        "s1_str":    f"{s1:.{decimals}f}",
    }


def get_pair_data(pair):
    """Fetch data and calculate pivots for one currency pair."""
    try:
        ohlc = fetch_yahoo_ohlc(pair["ticker"])
        return calculate_pivots(ohlc, pair["decimals"])
    except Exception as e:
        print(f"⚠️  Error fetching {pair['name']}: {e}")
        return None


def get_economic_calendar():
    """Fetch today's high-impact economic events (ForexFactory free feed)."""
    try:
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        events = resp.json()

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        high_impact = [
            ev for ev in events
            if ev.get("impact") == "High"
            and ev.get("country") in ("USD", "EUR", "GBP")
            and ev.get("date", "")[:10] == today_str
        ]
        return high_impact
    except Exception as e:
        print(f"⚠️  Economic calendar unavailable: {e}")
        return []


# ======================== CHART GENERATION ========================

def generate_chart(ticker_symbol, pair_name, pivot, r1, s1):
    """Generate a professional candlestick chart with pivot levels."""
    if not CHARTS_ENABLED:
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
        if len(df) < 3:
            print(f"⚠️  Not enough data to chart {pair_name}")
            return None

        # TradingView-inspired dark theme
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

        hlines = dict(
            hlines=[pivot, r1, s1],
            colors=["#ffd700", "#26a69a", "#ef5350"],
            linestyle=["--", "--", "--"],
            linewidths=[1.3, 1.0, 1.0],
        )

        date_str = datetime.now(timezone.utc).strftime("%d %b %Y")
        filepath = os.path.join(tempfile.gettempdir(), "chart.png")

        fig, axes = mpf.plot(
            df, type="candle", style=style,
            title=f"\n{pair_name}  •  Daily  •  {date_str}",
            hlines=hlines, figsize=(10, 5.5),
            tight_layout=True, returnfig=True,
        )

        # Label each pivot line inside the chart
        ax = axes[0]
        xmin, xmax = ax.get_xlim()
        x_pos = xmin + (xmax - xmin) * 0.01
        for val, label, color in [
            (pivot, "Pivot", "#ffd700"),
            (r1,    "R1",    "#26a69a"),
            (s1,    "S1",    "#ef5350"),
        ]:
            ax.text(
                x_pos, val, f" {label}: {val:,.2f} ",
                color=color, fontsize=8.5, va="center", fontweight="bold",
                bbox=dict(
                    boxstyle="round,pad=0.2", facecolor="#131722",
                    edgecolor=color, alpha=0.85,
                ),
            )

        fig.savefig(
            filepath, dpi=150, bbox_inches="tight",
            facecolor="#131722", edgecolor="none", pad_inches=0.3,
        )
        plt.close(fig)
        print(f"📊 Chart saved → {filepath}")
        return filepath

    except Exception as e:
        print(f"⚠️  Chart generation failed for {pair_name}: {e}")
        return None


# ======================== MESSAGE BUILDING ========================

def build_calendar_section(events):
    """Format economic calendar events as HTML with a direct Myfxbook link."""
    lines = ["⚠️ <b>HIGH-IMPACT ECONOMIC EVENTS TODAY:</b>"]
    if not events:
        lines.append("✅ No high-impact USD/EUR/GBP events scheduled today.")
    else:
        flags = {"USD": "🇺🇸", "EUR": "🇪🇺", "GBP": "🇬🇧"}
        for ev in events[:5]:
            flag     = flags.get(ev.get("country", ""), "🌐")
            time_str = ev.get("date", "")[11:16]
            title    = ev.get("title", "Unknown")
            forecast = ev.get("forecast", "")
            fc_part  = f" (Forecast: {forecast})" if forecast else ""
            lines.append(f"🕐 {time_str} UTC — {flag} {title}{fc_part}")

    lines.append(
        f"👉 <b><a href='{MYFXBOOK_CALENDAR_LINK}'>Live Calendar on Myfxbook</a></b>\n"
    )
    return "\n".join(lines)


def build_market_post(pair_data, calendar_events):
    """Build the main Telegram market brief in HTML."""
    now_utc = datetime.now(timezone.utc)
    date_str = now_utc.strftime("%d %b %Y")
    tip = DAILY_TIPS[now_utc.day % len(DAILY_TIPS)]
    today_app = ROTATING_APPS[now_utc.day % len(ROTATING_APPS)]

    lines = [f"📊 <b>DAILY MARKET BRIEF & KEY LEVELS ({date_str})</b>\n"]

    for pair, stats in pair_data:
        if stats is None:
            continue
        p = pair["prefix"]
        lines.append(
            f"{pair['emoji']} <b>{pair['name'].upper()}:</b> "
            f"{p}{stats['price_str']} ({stats['change_str']})\n"
            f"   • Pivot: <code>{stats['pivot_str']}</code> "
            f"| R1: <code>{stats['r1_str']}</code> "
            f"| S1: <code>{stats['s1_str']}</code>\n"
        )

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
    parts = [f"📊 Daily Forex Levels — {date_str}\n"]
    for pair, stats in pair_data[:2]:  # Gold + EUR/USD
        if stats is None:
            continue
        p = pair["prefix"]
        parts.append(
            f"{pair['emoji']} {pair['name']}: {p}{stats['price_str']} "
            f"({stats['change_str']})"
        )
        parts.append(
            f"  P: {stats['pivot_str']} | R1: {stats['r1_str']} "
            f"| S1: {stats['s1_str']}\n"
        )
    parts.append(f"👉 Full levels free: {TELEGRAM_GROUP_LINK}")
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
                "name": f"{pair['emoji']} {pair['name']}",
                "value": (
                    f"**{p}{stats['price_str']}** ({stats['change_str']})\n"
                    f"Pivot: `{stats['pivot_str']}` | R1: `{stats['r1_str']}` "
                    f"| S1: `{stats['s1_str']}`"
                ),
                "inline": False,
            })

        if calendar_events:
            cal_lines = [
                f"{flags.get(ev.get('country'), '🌐')} {ev.get('title', '?')}"
                for ev in calendar_events[:4]
            ]
            cal_lines.append(f"[📅 View Live Calendar on Myfxbook]({MYFXBOOK_CALENDAR_LINK})")
            fields.append({
                "name": "⚠️ High-Impact Events Today",
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
    print("⏳ Fetching market data...")
    pair_data = [(pair, get_pair_data(pair)) for pair in PAIRS]

    print("📅 Fetching economic calendar...")
    calendar_events = get_economic_calendar()

    # Generate Gold chart
    gold_pair, gold_stats = pair_data[0]
    chart_path = None
    if gold_stats:
        print("📊 Generating Gold chart...")
        chart_path = generate_chart(
            gold_pair["ticker"], gold_pair["name"],
            gold_stats["pivot"], gold_stats["r1"], gold_stats["s1"],
        )

    # Build text message
    post_html = build_market_post(pair_data, calendar_events)

    # --- Telegram ---
    if chart_path:
        send_telegram_photo(
            chart_path,
            caption=f"📊 <b>{gold_pair['name']} — Daily Chart</b>",
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
