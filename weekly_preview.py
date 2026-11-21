"""
Weekly Forex & Economic Preview (Published Sundays on Market Vacation).
Prepares traders with the full week's macro roadmap, key levels, and an interactive poll.
"""
import os
import sys
from datetime import datetime, timezone
import requests

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

MAIN_APP_NAME = "Best Forex Brokers"
MAIN_APP_LINK = "https://play.google.com/store/apps/details?id=com.revapps.bestforexbrokers"
BROKER_LINK = "https://clicks.pipaffiliates.com/c?m=131292&c=98704"
WHATSAPP_CHANNEL_LINK = "https://whatsapp.com/channel/0029Vb9Wpao8F2p6YTGzIP2g"
PLAY_STORE_DEV_LINK = os.environ.get(
    "PLAY_STORE_DEV_LINK",
    "https://play.google.com/store/apps/developer?id=RevApps",
)
MYFXBOOK_CALENDAR_LINK = "https://www.myfxbook.com/forex-economic-calendar"

MAJOR_CURRENCIES = ("USD", "EUR", "GBP", "JPY", "AUD", "CAD", "NZD", "CHF")
CURRENCY_FLAGS = {
    "USD": "🇺🇸", "EUR": "🇪🇺", "GBP": "🇬🇧", "JPY": "🇯🇵",
    "AUD": "🇦🇺", "CAD": "🇨🇦", "NZD": "🇳🇿", "CHF": "🇨🇭",
}

if not BOT_TOKEN or not CHAT_ID:
    sys.exit("❌ Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")


def fetch_week_calendar():
    """Fetch all high-impact events for the coming week from ForexFactory."""
    try:
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        resp = requests.get(url, timeout=12)
        resp.raise_for_status()
        events = resp.json()

        high_events = []
        for ev in events:
            if ev.get("impact") == "High" and ev.get("country") in MAJOR_CURRENCIES:
                try:
                    dt = datetime.fromisoformat(ev["date"]).astimezone(timezone.utc)
                except Exception:
                    continue

                high_events.append({
                    "title": ev.get("title", "Event"),
                    "country": ev.get("country", ""),
                    "forecast": ev.get("forecast", ""),
                    "previous": ev.get("previous", ""),
                    "dt": dt,
                    "day_name": dt.strftime("%A"),
                    "day_short": dt.strftime("%a"),
                    "date_short": dt.strftime("%b %d"),
                    "time_str": dt.strftime("%H:%M"),
                })

        high_events.sort(key=lambda x: x["dt"])
        return high_events
    except Exception as e:
        print(f"⚠️  Error fetching weekly calendar: {e}")
        return []


def build_weekly_post(events):
    """Build the Weekly Outlook brief in HTML."""
    date_str = datetime.now(timezone.utc).strftime("%d %b %Y")

    lines = [
        f"🗓️ <b>WEEK AHEAD TRADER PLAYBOOK ({date_str})</b>\n",
        "<i>Get ready for the market open! Here is your institutional macro roadmap and high-impact schedule for the coming trading week:</i>\n",
        "━━━━━━━━━━━━━━━━━━━━",
    ]

    if not events:
        lines.append("✅ <b>No high-impact releases scheduled this week.</b> Pure technical trading conditions ahead!\n")
    else:
        # Group by day
        days_map = {}
        for ev in events:
            key = f"{ev['day_name']} ({ev['date_short']})"
            days_map.setdefault(key, []).append(ev)

        for day_label, ev_list in days_map.items():
            lines.append(f"📅 <b>{day_label.upper()}</b>")
            for ev in ev_list:
                flag = CURRENCY_FLAGS.get(ev["country"], "🌐")
                fc = f" | FC: <code>{ev['forecast']}</code>" if ev["forecast"] else ""
                prev = f" | Prev: <code>{ev['previous']}</code>" if ev["previous"] else ""
                lines.append(
                    f"• <b>{ev['time_str']} UTC</b> — {flag} <b>{ev['country']} {ev['title']}</b>{fc}{prev}"
                )
            lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("💡 <b>WEEKLY RISK RULES:</b>")
    lines.append("• <b>Sunday/Monday Open:</b> Spreads are abnormally wide during Asian session opens. Avoid breakout orders until London open.")
    lines.append("• <b>Red Folder Events:</b> Cut position sizes in half ahead of CPI, NFP, or Interest Rate releases.")
    lines.append(f"👉 <b><a href='{MYFXBOOK_CALENDAR_LINK}'>Full Live Calendar on Myfxbook</a></b>\n")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(
        f"🚨 <b>TOP REGULATED BROKER | 100% BONUS UP TO $200:</b>\n"
        f"👉 <b><a href='{BROKER_LINK}'>CLAIM YOUR TRADING BONUS HERE</a></b>\n\n"
        f"📱 <b>COMPARE ALL REGULATED SPREADS ON ANDROID:</b>\n"
        f"👉 <b><a href='{MAIN_APP_LINK}'>DOWNLOAD {MAIN_APP_NAME.upper()}</a></b>\n\n"
        f"💬 <b>OFFICIAL WHATSAPP CHANNEL:</b>\n"
        f"👉 <b><a href='{WHATSAPP_CHANNEL_LINK}'>JOIN & FOLLOW ON WHATSAPP</a></b>\n\n"
        f"🌐 <b>EXPLORE OUR 200+ TRADING & FINANCE APPS:</b>\n"
        f"👉 <b><a href='{PLAY_STORE_DEV_LINK}'>VIEW FULL PORTFOLIO</a></b>"
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
    print("✅ Weekly outlook posted to Telegram.")


def send_weekly_poll():
    """Send interactive Sunday poll to engage traders for the upcoming week."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPoll"
    payload = {
        "chat_id": CHAT_ID,
        "question": "🎯 WEEKLY TRADER POLL: What is your primary focus for this upcoming week?",
        "options": [
            {"text": "🥇 Gold (XAU/USD) Breakouts & Pivots"},
            {"text": "💶 EUR/USD & USD Majors Trend"},
            {"text": "💷 High-Beta Crosses (GBP / Yen)"},
            {"text": "🛡️ Capital Defense / Selective setups"},
        ],
        "is_anonymous": True,
    }
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()
    print("✅ Weekly sentiment poll sent.")


def post_to_discord(events):
    """Optionally crosspost to Discord."""
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        date_str = datetime.now(timezone.utc).strftime("%d %b %Y")
        fields = []

        if events:
            lines = [
                f"{CURRENCY_FLAGS.get(ev['country'], '🌐')} **{ev['day_short']} {ev['time_str']} UTC** — {ev['country']} {ev['title']}"
                for ev in events[:6]
            ]
            lines.append(f"[📅 View Full Interactive Calendar on Myfxbook]({MYFXBOOK_CALENDAR_LINK})")
            fields.append({
                "name": "🗓️ Week Ahead Top Releases",
                "value": "\n".join(lines),
                "inline": False,
            })

        embed = {
            "title": f"🗓️ Weekly Macro Playbook — {date_str}",
            "color": 0xFFD700,
            "fields": fields,
            "footer": {"text": "Join our Telegram for daily signals, charts & polls"},
        }
        requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, timeout=15)
        print("✅ Discord weekly outlook posted.")
    except Exception as e:
        print(f"⚠️  Discord weekly post failed: {e}")


if __name__ == "__main__":
    print("🚀 Generating Weekly Forex Outlook...")
    events = fetch_week_calendar()
    post = build_weekly_post(events)
    send_telegram_message(post)
    send_weekly_poll()
    post_to_discord(events)
    print("🎉 Weekly preview complete!")
