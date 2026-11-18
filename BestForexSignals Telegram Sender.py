from datetime import datetime
import time
import requests
import yfinance as yf

# ================= CONFIGURATION =================
BOT_TOKEN = "9142497477:AAG7Bdl7gQa6jgEjHQ0P95gs7dJuctiwM0g"
CHAT_ID = "-1003177467495"

APP_LINK = "https://play.google.com/store/apps/details?id=com.revapps.bestforexbrokers"
BROKER_LINK = "https://clicks.pipaffiliates.com/c?m=131292&c=98704"

# Set your desired daily posting time (24-hour format, e.g., 09:00 AM = 9, 0)
POST_HOUR = 9
POST_MINUTE = 0
# =================================================

DAILY_TIPS = [
    "💡 <b>Risk Rule:</b> Never risk more than 1–2% of your account equity on a single Gold (XAU/USD) setup—especially ahead of US session opens.",
    "💡 <b>Session Timing:</b> The highest liquidity and cleanest breakouts on EUR/USD and Gold occur during the London–New York overlap (15:00–19:00 TRT).",
    "💡 <b>Broker Tip:</b> Always check swap fees and raw spread commissions before holding indices or Gold positions overnight.",
    "💡 <b>Trading Psychology:</b> Wait for candle close confirmation above/below key pivot levels rather than chasing sudden news spikes.",
]

# Create a custom session with a browser user-agent to prevent Yahoo Finance from blocking/hanging cloud runners
session = requests.Session()
session.headers.update(
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
)


def get_pair_stats(ticker_symbol: str, decimals: int = 4):
    """Fetches latest price, % change, and classic Pivot levels safely with timeout."""
    try:
        ticker = yf.Ticker(ticker_symbol, session=session)
        data = ticker.history(period="5d", interval="1d", timeout=10)
        if len(data) < 2:
            return None

        prev = data.iloc[-2]
        curr = data.iloc[-1]

        last_price = float(curr["Close"])
        prev_close = float(prev["Close"])
        pct_change = ((last_price - prev_close) / prev_close) * 100

        pivot = (float(prev["High"]) + float(prev["Low"]) + prev_close) / 3
        r1 = (2 * pivot) - float(prev["Low"])
        s1 = (2 * pivot) - float(prev["High"])

        arrow = "🟢 ▲" if pct_change >= 0 else "🔴 ▼"
        return {
            "price": f"{last_price:.{decimals}f}",
            "change": f"{arrow} {pct_change:+.2f}%",
            "pivot": f"{pivot:.{decimals}f}",
            "r1": f"{r1:.{decimals}f}",
            "s1": f"{s1:.{decimals}f}",
        }
    except Exception as e:
        print(f"⚠️ Error fetching {ticker_symbol}: {e}")
        return None


def build_market_post() -> str:
    gold = get_pair_stats("GC=F", decimals=2)
    eurusd = get_pair_stats("EURUSD=X", decimals=4)
    gbpusd = get_pair_stats("GBPUSD=X", decimals=4)
    usdjpy = get_pair_stats("USDJPY=X", decimals=2)

    date_str = datetime.now().strftime("%d %b %Y")
    tip = DAILY_TIPS[datetime.now().day % len(DAILY_TIPS)]

    lines = [
        f"📊 <b>DAILY MARKET BRIEF & KEY LEVELS ({date_str})</b>\n",
    ]

    if gold:
        lines.append(
            f"🥇 <b>GOLD (XAU/USD):</b> ${gold['price']} ({gold['change']})\n"
            f"   • Pivot: <code>{gold['pivot']}</code> | R1: <code>{gold['r1']}</code> | S1: <code>{gold['s1']}</code>\n"
        )
    if eurusd:
        lines.append(
            f"💶 <b>EUR/USD:</b> {eurusd['price']} ({eurusd['change']})\n"
            f"   • Pivot: <code>{eurusd['pivot']}</code> | R1: <code>{eurusd['r1']}</code> | S1: <code>{eurusd['s1']}</code>\n"
        )
    if gbpusd:
        lines.append(
            f"💷 <b>GBP/USD:</b> {gbpusd['price']} ({gbpusd['change']})\n"
            f"   • Pivot: <code>{gbpusd['pivot']}</code> | R1: <code>{gbpusd['r1']}</code> | S1: <code>{gbpusd['s1']}</code>\n"
        )
    if usdjpy:
        lines.append(
            f"💴 <b>USD/JPY:</b> {usdjpy['price']} ({usdjpy['change']})\n"
        )

    lines.append(f"{tip}\n")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(
        f"🚨 <b>TOP BROKER OFFER | 100% BONUS UP TO $200:</b>\n"
        f"👉 <b><a href='{BROKER_LINK}'>CLICK HERE TO CLAIM YOUR BONUS</a></b>\n\n"
        f"📱 <b>COMPARE ALL REGULATED BROKERS & LIVE SPREADS:</b>\n"
        f"👉 <b><a href='{APP_LINK}'>DOWNLOAD OUR FREE ANDROID APP</a></b>"
    )

    return "\n".join(lines)


def send_telegram_message(html_text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": html_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()
    print(f"✅ [{datetime.now()}] Posted successfully to Telegram!")


if __name__ == "__main__":
    print(
        f"🤖 Telegram Autoposter started! Scheduled to post daily at {POST_HOUR:02d}:{POST_MINUTE:02d}."
    )

    while True:
        now = datetime.now()
        # Check if current time matches target hour and minute
        if now.hour == POST_HOUR and now.minute == POST_MINUTE:
            try:
                print("⏳ Generating and sending daily market brief...")
                post = build_market_post()
                send_telegram_message(post)
                # Sleep for 61 seconds so it doesn't trigger twice within the same minute
                time.sleep(61)
            except Exception as e:
                print(f"❌ Error sending post: {e}")
                time.sleep(60)
        else:
            # Check every 30 seconds
            time.sleep(30)