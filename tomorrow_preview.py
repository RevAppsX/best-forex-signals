"""
Tomorrow's High-Impact News Radar.
Published Monday-Thursday evening (18:00 UTC / 21:00 TRT) to alert traders about
overnight & tomorrow's major releases (e.g. Asian session NZD/JPY/AUD and European opens).
"""
import os
import sys
from datetime import datetime, timezone, timedelta
import requests

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

MAIN_APP_NAME = "Best Forex Brokers"
MAIN_APP_LINK = "https://play.google.com/store/apps/details?id=com.revapps.bestforexbrokers"
MYFXBOOK_CALENDAR_LINK = "https://www.myfxbook.com/forex-economic-calendar"

MAJOR_CURRENCIES = ("USD", "EUR", "GBP", "JPY", "AUD", "CAD", "NZD", "CHF")
CURRENCY_FLAGS = {
    "USD": "🇺🇸", "EUR": "🇪🇺", "GBP": "🇬🇧", "JPY": "🇯🇵",
    "AUD": "🇦🇺", "CAD": "🇨🇦", "NZD": "🇳🇿", "CHF": "🇨🇭",
}

if not BOT_TOKEN or not CHAT_ID:
    sys.exit("❌ Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")


def fetch_tomorrow_events():
    """Fetch high-impact events scheduled for tomorrow (UTC)."""
    try:
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        resp = requests.get(url, timeout=12)
        resp.raise_for_status()
        events = resp.json()

        now_utc = datetime.now(timezone.utc)
        tomorrow_date = (now_utc + timedelta(days=1)).date()

        tomorrow_events = []
        for ev in events:
            if ev.get("impact") == "High" and ev.get("country") in MAJOR_CURRENCIES:
                try:
                    dt = datetime.fromisoformat(ev["date"]).astimezone(timezone.utc)
                except Exception:
                    continue

                if dt.date() == tomorrow_date:
                    tomorrow_events.append({
                        "title": ev.get("title", "Event"),
                        "country": ev.get("country", ""),
                        "forecast": ev.get("forecast", ""),
                        "previous": ev.get("previous", ""),
                        "dt": dt,
                        "date_short": dt.strftime("%b %d"),
                        "day_name": dt.strftime("%A"),
                        "time_str": dt.strftime("%H:%M"),
                    })

        tomorrow_events.sort(key=lambda x: x["dt"])
        return tomorrow_events, tomorrow_date
    except Exception as e:
        print(f"⚠️  Error fetching tomorrow's events: {e}")
        return [], None


def build_tomorrow_post(events, tomorrow_date):
    """Build the evening 'Tomorrow's High-Impact Radar' post."""
    tomorrow_label = tomorrow_date.strftime("%A, %b %d") if tomorrow_date else "Tomorrow"

    lines = [
        f"🚨 <b>TOMORROW'S HIGH-IMPACT RADAR ({tomorrow_label})</b>\n",
        "<i>Overnight & Tomorrow Alert: Major macro data dropping across Asian, European, and US sessions:</i>\n",
        "━━━━━━━━━━━━━━━━━━━━",
    ]

    if not events:
        lines.append("✅ <b>No high-impact releases scheduled for tomorrow.</b> Clean technical sessions expected!\n")
    else:
        for ev in events:
            flag = CURRENCY_FLAGS.get(ev["country"], "🌐")
            fc = f" | FC: <code>{ev['forecast']}</code>" if ev["forecast"] else ""
            prev = f" | Prev: <code>{ev['previous']}</code>" if ev["previous"] else ""
            lines.append(
                f"• Tomorrow {ev['date_short']}, <b>{ev['time_str']} UTC</b> — {flag} <b>{ev['country']} {ev['title']}</b>{fc}{prev}"
            )
        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("⚠️ <b>OVERNIGHT TRADER ADVISORY:</b>")
    lines.append("• If holding positions through the Asian session, be mindful of rollover swap fees and early morning spread widening.")
    lines.append("• Protect open profits with trailing stops ahead of scheduled high-impact catalysts.")
    lines.append(f"👉 <b><a href='{MYFXBOOK_CALENDAR_LINK}'>Full Live Calendar on Myfxbook</a></b>\n")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(
        f"📱 <b>COMPARE LOW SPREAD BROKERS:</b>\n"
        f"👉 <b><a href='{MAIN_APP_LINK}'>DOWNLOAD {MAIN_APP_NAME.upper()}</a></b>"
    )

    return "\n".join(lines)


def send_telegram_message(html_text):
    """Send message to Telegram."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": html_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    resp = requests.post(url, json=payload, timeout=20)
    resp.raise_for_status()
    print("✅ Tomorrow's radar posted to Telegram.")


if __name__ == "__main__":
    print("🚀 Fetching Tomorrow's High-Impact Radar...")
    events, tomorrow_date = fetch_tomorrow_events()
    post = build_tomorrow_post(events, tomorrow_date)
    send_telegram_message(post)
    print("🎉 Tomorrow's radar complete!")
