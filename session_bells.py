"""
Session Opening Bells.
Triggers energetic, actionable notifications for the two largest market opens:
- 07:00 UTC: London Open (European Session)
- 13:00 UTC: New York Open (Wall Street & Overlap)
"""
import os
import sys
import argparse
from datetime import datetime, timezone
import requests

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

MAIN_APP_NAME = "Best Forex Brokers"
MAIN_APP_LINK = "https://play.google.com/store/apps/details?id=com.revapps.bestforexbrokers"
BROKER_LINK = "https://clicks.pipaffiliates.com/c?m=131292&c=98704"
MYFXBOOK_CALENDAR_LINK = "https://www.myfxbook.com/forex-economic-calendar"

if not BOT_TOKEN or not CHAT_ID:
    sys.exit("❌ Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")


def get_london_bell_text():
    return (
        "🔔 <b>LONDON SESSION OPEN — THE TRADING DESK IS LIVE 🇬🇧</b>\n\n"
        "<i>European institutional banks and liquidity providers have entered the market!</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ <b>SESSION FOCUS ASSETS:</b>\n"
        "• 💶 <b>EUR/USD & 💷 GBP/USD:</b> Primary European volume injection\n"
        "• 🥇 <b>Gold (XAU/USD):</b> Watch breakout from Asian consolidation range\n"
        "• 💴 <b>GBP/JPY:</b> High-beta volatility swings\n\n"
        "⚠️ <b>INSTITUTIONAL PLAYBOOK:</b>\n"
        "• <b>Asian Range Sweep:</b> London opens often hunt stop orders above/below the Asian high/low before true directional expansion begins.\n"
        "• <b>Confirmation:</b> Wait for 15m/1H candle close confirmation before jumping into initial momentum bursts.\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📱 <b>COMPARE TIGHTEST SPREADS & BROKER BONUSES:</b>\n"
        f"👉 <b><a href='{MAIN_APP_LINK}'>DOWNLOAD {MAIN_APP_NAME.upper()}</a></b> | "
        f"<b><a href='{BROKER_LINK}'>CLAIM 100% BONUS</a></b>"
    )


def get_ny_bell_text():
    return (
        "🔔 <b>WALL STREET OPEN — NEW YORK SESSION IS LIVE 🇺🇸</b>\n\n"
        "<i>The London-New York Overlap is officially underway: Over 70% of global daily forex volume trades over the next 4 hours!</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ <b>SESSION FOCUS ASSETS:</b>\n"
        "• 🥇 <b>Gold (XAU/USD):</b> Peak institutional bullion flows\n"
        "• ₿ <b>Bitcoin (BTC) & Crypto:</b> US ETF flows & spot market volume\n"
        "• 💵 <b>USD Majors (EUR/USD, GBP/USD, USD/JPY)</b>\n\n"
        "⚠️ <b>OVERLAP PLAYBOOK:</b>\n"
        "• <b>Protect London Profits:</b> Move Stop Loss to break-even or bank partial targets on morning trades.\n"
        "• <b>Macro Catalysts:</b> Keep a close eye on scheduled US economic data (CPI, PPI, PMI, FOMC).\n"
        f"👉 <b><a href='{MYFXBOOK_CALENDAR_LINK}'>Check Live Calendar on Myfxbook</a></b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📱 <b>COMPARE ALL REGULATED BROKERS ON ANDROID:</b>\n"
        f"👉 <b><a href='{MAIN_APP_LINK}'>DOWNLOAD OUR FREE APP</a></b>"
    )


def send_telegram(html_text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": html_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()
    print("✅ Session bell sent to Telegram.")


def send_discord(title, desc):
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        embed = {
            "title": title,
            "description": desc,
            "color": 0x26A69A,
            "footer": {"text": "Join Telegram for live signals & setups"},
        }
        requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, timeout=15)
        print("✅ Session bell sent to Discord.")
    except Exception as e:
        print(f"⚠️ Discord bell failed: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", choices=["london", "ny"], default=None)
    args = parser.parse_args()

    session = args.session
    if not session:
        # Auto-detect from current hour
        h = datetime.now(timezone.utc).hour
        session = "london" if h < 10 else "ny"

    if session == "london":
        text = get_london_bell_text()
        send_telegram(text)
        send_discord("🔔 London Session Open", text)
    else:
        text = get_ny_bell_text()
        send_telegram(text)
        send_discord("🔔 Wall Street / NY Session Open", text)
