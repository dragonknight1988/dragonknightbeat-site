#!/bin/bash
# 2026-10-28 补跑：昨晚内存耗尽导致全部每日生成任务失败/卡死
cd /opt/dragonknightbeat-site
echo "===== 补跑开始 $(date) ====="
./gen-cron.sh daily_news daily-news 📰
./gen-cron.sh daily_english daily-english 📖
./gen-cron.sh daily_briefing daily-briefing 📡
./gen-cron.sh daily_programming daily-programming 💻
./gen-cron.sh daily_auto daily-auto 🚗
./gen-cron.sh daily_autotech daily-autotech 🔧
./gen-lang-cron.sh russian
./gen-lang-cron.sh french
./gen-lang-cron.sh spanish
./gen-lang-cron.sh italian
./gen-lang-cron.sh german
./gen-en-cron.sh
echo "===== 补跑结束 $(date) ====="
