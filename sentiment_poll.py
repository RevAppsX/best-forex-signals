"""
Sentiment Poll — Sends an interactive poll to the Telegram group.
Runs daily before the London/NY overlap session via GitHub Actions cron.
"""
import os
import sys
from datetime import datetime, timezone
import requests

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    sys.exit("❌ Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")

POLLS = [
    {
        "question": "🥇 Where is Gold (XAU/USD) heading into the US Session?",
        "options": [
            "🟢 Bullish — Buy Dips",
            "🔴 Bearish — Sell Rallies",
            "⚪ Sideways — Stay Out",
        ],
    },
    {
        "question": "💶 What's your EUR/USD bias for today?",
        "options": ["🟢 Bullish", "🔴 Bearish", "⚪ Range-bound"],
    },
    {
        "question": "📈 Which pair has the best setup today?",
        "options": [
            "🥇 Gold (XAU/USD)",
            "💶 EUR/USD",
            "💷 GBP/USD",
            "💴 USD/JPY",
        ],
    },
    {
        "question": "⚡ How aggressive is your risk today?",
        "options": [
            "🟢 Full size — High conviction",
            "🟡 Half size — Cautious",
            "🔴 Sitting out — No edge",
        ],
    },
]


def send_poll(question, options):
    """Send an interactive poll to the Telegram group."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPoll"
    payload = {
        "chat_id": CHAT_ID,
        "question": question,
        "options": [{"text": opt} for opt in options],
        "is_anonymous": True,
    }
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()
    print(f"✅ Poll sent: {question}")


if __name__ == "__main__":
    # Rotate through polls based on the day of the month
    poll = POLLS[datetime.now(timezone.utc).day % len(POLLS)]
    send_poll(poll["question"], poll["options"])
