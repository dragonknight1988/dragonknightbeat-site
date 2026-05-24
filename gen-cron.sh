#!/bin/bash
LOGDIR=/var/log/dragonknightbeat
mkdir -p "$LOGDIR"
cd /opt/dragonknightbeat-site

SCRIPT=$1
OUTPUT=$2
LABEL=$3
LOG="$LOGDIR/${SCRIPT}.log"
WEBROOT=/var/www/dragonknightbeat.com

echo "===== $(date "+%Y-%m-%d %H:%M") $LABEL =====" >> "$LOG"

source /opt/dragonknightbeat-site/.env
python3 scripts/generate_${SCRIPT}.py --output "${WEBROOT}/${OUTPUT}.json" >> "$LOG" 2>&1
R=$?
if [ $R -ne 0 ]; then
  echo "❌ 生成失败 (exit=$R)" >> "$LOG"
  exit $R
fi

echo "✅ $(date "+%H:%M") 已写入 ${WEBROOT}/${OUTPUT}.json" >> "$LOG"
echo "===== 完成 =====" >> "$LOG"
