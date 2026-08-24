#!/bin/bash
export PYTHONIOENCODING=utf-8
LOGDIR=/var/log/dragonknightbeat
mkdir -p "$LOGDIR"
cd /opt/dragonknightbeat-site

LANG=$1
LOG="$LOGDIR/daily_${LANG}.log"
WEBROOT=/var/www/dragonknightbeat.com
MAX_RETRY=3

source /opt/dragonknightbeat-site/.env

for attempt in $(seq 1 $MAX_RETRY); do
  echo "===== $(date "+%Y-%m-%d %H:%M") ${LANG} (attempt $attempt/$MAX_RETRY) =====" >> "$LOG"

  python3 scripts/generate_daily_language.py --lang "$LANG" --output "${WEBROOT}/daily-${LANG}.json" >> "$LOG" 2>&1
  R=$?
  if [ $R -eq 0 ]; then
    echo "✅ $(date "+%H:%M") 已写入 ${WEBROOT}/daily-${LANG}.json" >> "$LOG"
    echo "===== 完成 =====" >> "$LOG"
    exit 0
  fi

  echo "❌ attempt $attempt 失败 (exit=$R)" >> "$LOG"
  if [ $attempt -lt $MAX_RETRY ]; then
    echo "⏳ 等待30秒后重试..." >> "$LOG"
    sleep 30
  fi
done

echo "❌❌❌ ${MAX_RETRY}次尝试全部失败！" >> "$LOG"
echo "===== 失败 =====" >> "$LOG"
exit 1
