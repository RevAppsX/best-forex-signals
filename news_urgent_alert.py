"""
Urgent 1-Hour Live Economic Alert.
Checks ForexFactory feed and triggers a bold red warning ~45-60 minutes before
any Tier-1 High-Impact release drops, warning traders about spread expansion & volatility.
"""
import os
import sys
import json
from datetime import datetime, timezone
import requests

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

MYFXBOOK_CALENDAR_LINK = "https://www.myfxbook.com/forex-economic-calendar"
CACHE_FILE = os.path.join(os.path.dirname(__file__), ".alerts_cache.json")

MAJOR_CURRENCIES = ("USD", "EUR", "GBP", "JPY", "AUD", "CAD", "NZD", "CHF")
CURRENCY_FLAGS = {
    "USD": "🇺🇸", "EUR": "🇪🇺", "GBP": "🇬🇧", "JPY": "🇯🇵",
    "AUD": "🇦🇺", "CAD": "🇨🇦", "NZD": "🇳🇿", "CHF": "🇨🇭",
}

AFFECTED_PAIRS = {
    "USD": "EUR/USD, GBP/USD, Gold (XAU/USD), USD/JPY, USD/CAD",
    "EUR": "EUR/USD, EUR/GBP, EUR/JPY, EUR/AUD",
    "GBP": "GBP/USD, EUR/GBP, GBP/JPY",
    "JPY": "USD/JPY, GBP/JPY, EUR/JPY",
    "AUD": "AUD/USD, AUD/NZD, AUD/JPY",
    "CAD": "USD/CAD, CAD/JPY",
    "NZD": "NZD/USD, AUD/NZD, NZD/JPY",
    "CHF": "USD/CHF, EUR/CHF",
}

if not BOT_TOKEN or not CHAT_ID:
    sys.exit("❌ Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")


def load_cache():
    """Load previously alerted event keys."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cache(cache):
    """Save alerted event keys."""
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        print(f"⚠️  Could not save cache: {e}")


def fetch_urgent_events(cache):
    """Find High-Impact events starting in 25 to 75 minutes that haven't been alerted."""
    try:
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        events = resp.json()

        now_utc = datetime.now(timezone.utc)
        to_alert = []

        for ev in events:
            if ev.get("impact") == "High" and ev.get("country") in MAJOR_CURRENCIES:
                try:
                    dt = datetime.fromisoformat(ev["date"]).astimezone(timezone.utc)
                except Exception:
                    continue

                diff_seconds = (dt - now_utc).total_seconds()
                diff_minutes = diff_seconds / 60.0

                # Target window: 25 to 75 minutes away (approximately 1 hour before)
                if 25 <= diff_minutes <= 75:
                    key = f"{ev.get('country')}_{ev.get('title')}_{dt.strftime('%Y-%m-%d_%H:%M')}"
                    if key not in cache:
                        to_alert.append({
                            "key": key,
                            "title": ev.get("title", "Event"),
                            "country": ev.get("country", ""),
                            "forecast": ev.get("forecast", ""),
                            "previous": ev.get("previous", ""),
                            "dt": dt,
                            "date_short": dt.strftime("%b %d"),
                            "time_str": dt.strftime("%H:%M"),
                            "mins_left": int(round(diff_minutes)),
                        })

        return to_alert
    except Exception as e:
        print(f"⚠️  Error fetching urgent events: {e}")
        return []


def build_urgent_alert(events):
    """Build the 1-hour urgent warning in bold red style."""
    lines = [
        "🔴 <b>HIGH IMPACT NEWS IN 1 HOUR</b> ⚠️\n",
        "<i>Tier-1 macro data release approaching. Prepare for extreme spread volatility:</i>\n",
        "━━━━━━━━━━━━━━━━━━━━",
    ]

    for ev in events:
        flag = CURRENCY_FLAGS.get(ev["country"], "🌐")
        pairs = AFFECTED_PAIRS.get(ev["country"], "All Major Currency Crosses")
        fc = f"<code>{ev['forecast']}</code>" if ev["forecast"] else "N/A"
        prev = f"<code>{ev['previous']}</code>" if ev["previous"] else "N/A"

        lines.append(
            f"🚨 <b>Today {ev['date_short']}, {ev['time_str']} UTC</b> (in ~{ev['mins_left']} min)\n"
            f"   • <b>Release:</b> {flag} <b>{ev['country']} {ev['title']}</b>\n"
            f"   • <b>Forecast:</b> {fc} | <b>Previous:</b> {prev}\n"
            f"   • <b>Affected Pairs:</b> <code>{pairs}</code>\n"
        )

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("⚠️ <b>CRITICAL RISK RULES:</b>")
    lines.append("• <b>Spread Widening:</b> Spreads can expand 5x to 15x across brokers during the seconds surrounding the release.")
    lines.append("• <b>Slippage:</b> Market orders often slip. Avoid chasing news spikes on initial candle bursts.")
    lines.append("• <b>Protection:</b> Tighten stop-losses or lock in profits on open trades now.")
    lines.append(f"\n👉 <b><a href='{MYFXBOOK_CALENDAR_LINK}'>Live Calendar on Myfxbook</a></b>")

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
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()
    print("✅ 1-Hour Urgent Alert posted to Telegram.")


def post_to_discord(events):
    """Optionally crosspost urgent alert to Discord."""
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        fields = []
        for ev in events:
            flag = CURRENCY_FLAGS.get(ev["country"], "🌐")
            pairs = AFFECTED_PAIRS.get(ev["country"], "All Majors")
            fields.append({
                "name": f"🚨 {flag} {ev['country']} {ev['title']} (~{ev['mins_left']}m left)",
                "value": (
                    f"**Time:** {ev['time_str']} UTC\n"
                    f"**Forecast:** `{ev['forecast'] or 'N/A'}` | **Previous:** `{ev['previous'] or 'N/A'}`\n"
                    f"**Affected Pairs:** `{pairs}`"
                ),
                "inline": False,
            })
        embed = {
            "title": "🔴 URGENT: High Impact News in 1 Hour",
            "color": 0xEF5350,  # Red
            "fields": fields,
            "footer": {"text": "Join Telegram for live signals & risk warnings"},
        }
        requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, timeout=15)
        print("✅ Discord urgent alert posted.")
    except Exception as e:
        print(f"⚠️  Discord urgent post failed: {e}")


if __name__ == "__main__":
    cache = load_cache()
    events = fetch_urgent_events(cache)

    if not events:
        print("ℹ️  No high-impact news in the 1-hour window. No alert needed.")
        sys.exit(0)

    print(f"🚨 Found {len(events)} upcoming high-impact event(s). Sending alert...")
    post = build_urgent_alert(events)
    send_telegram_message(post)
    post_to_discord(events)

    # Register events in cache
    now_ts = datetime.now(timezone.utc).isoformat()
    for ev in events:
        cache[ev["key"]] = now_ts

    # Purge old cache entries (> 7 days)
    if len(cache) > 100:
        cache = dict(list(cache.items())[-50:])

    save_cache(cache)
    print("🎉 Urgent alert dispatched & cache updated!")
