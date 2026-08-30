#!/bin/bash
LOGDIR=/var/log/dragonknightbeat
mkdir -p "$LOGDIR"
cd /opt/dragonknightbeat-site

SCRIPT=$1
OUTPUT=$2
LABEL=$3
LOG="$LOGDIR/${SCRIPT}.log"
WEBROOT=/var/www/dragonknightbeat.com
MAX_RETRY=10

source /opt/dragonknightbeat-site/.env

export PYTHONUNBUFFERED=1

for attempt in $(seq 1 $MAX_RETRY); do
  echo "===== $(date "+%Y-%m-%d %H:%M") $LABEL (attempt $attempt/$MAX_RETRY) =====" >> "$LOG"
  echo "[DEBUG] Starting at $(date)" >> "$LOG"
  echo "[DEBUG] MIMO_API_KEY set: $([ -n "$MIMO_API_KEY" ] && echo YES || echo NO)" >> "$LOG"
  echo "[DEBUG] python3 path: $(which python3)" >> "$LOG"

  timeout 600 python3 -u scripts/generate_${SCRIPT}.py --output "${WEBROOT}/${OUTPUT}.json" >> "$LOG" 2>&1
  R=$?
  echo "[DEBUG] Exit code: $R at $(date)" >> "$LOG"
  if [ $R -eq 0 ]; then
    echo "✅ $(date "+%H:%M") 已写入 ${WEBROOT}/${OUTPUT}.json" >> "$LOG"
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
