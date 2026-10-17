#!/bin/bash
# 每日英文内容生成（海外 DK News App）— 每天 03:15 在中文内容生成完成后运行
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1
LOGDIR=/var/log/dragonknightbeat
mkdir -p "$LOGDIR"
cd /opt/dragonknightbeat-site
LOG="$LOGDIR/daily_news_en.log"
MAX_RETRY=3

source /opt/dragonknightbeat-site/.env

for attempt in $(seq 1 $MAX_RETRY); do
  echo "===== $(date "+%Y-%m-%d %H:%M") 🌍 English news (attempt $attempt/$MAX_RETRY) =====" >> "$LOG"
  timeout 900 python3 -u scripts/generate_daily_news_en.py >> "$LOG" 2>&1
  R=$?
  if [ $R -eq 0 ]; then
    echo "✅ $(date "+%H:%M") 英文内容生成完成" >> "$LOG"
    echo "===== 完成 =====" >> "$LOG"
    exit 0
  fi
  echo "❌ attempt $attempt 失败 (exit=$R)" >> "$LOG"
  [ $attempt -lt $MAX_RETRY ] && sleep 30
done
echo "❌❌❌ ${MAX_RETRY}次尝试全部失败！" >> "$LOG"
exit 1
