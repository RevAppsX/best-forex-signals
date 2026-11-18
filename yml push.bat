cmd /c "if not exist .github\workflows mkdir .github\workflows" & (
echo name: Daily Forex Signals Bot
echo.
echo on:
echo   schedule:
echo     - cron: '0 9 * * *'
echo   workflow_dispatch:
echo.
echo jobs:
echo   send-signal:
echo     runs-on: ubuntu-latest
echo     steps:
echo       - name: Checkout repository
echo         uses: actions/checkout@v4
echo       - name: Set up Python
echo         uses: actions/setup-python@v5
echo         with:
echo           python-version: '3.10'
echo           cache: 'pip'
echo       - name: Install dependencies
echo         run: |
echo           pip install requests yfinance
echo       - name: Run Telegram Sender Script
echo         env:
echo           TELEGRAM_BOT_TOKEN: `${{ secrets.TELEGRAM_BOT_TOKEN }}
echo           TELEGRAM_CHAT_ID: `${{ secrets.TELEGRAM_CHAT_ID }}
echo         run: |
echo           python "BestForexSignals Telegram Sender.py"
) > .github\workflows\telegram_cron.yml