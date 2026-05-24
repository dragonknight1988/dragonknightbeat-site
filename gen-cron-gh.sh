#!/bin/bash
LOGDIR=/var/log/dragonknightbeat
mkdir -p "$LOGDIR"
cd /opt/dragonknightbeat-site

SCRIPT=$1
OUTPUT=$2
LABEL=$3
LOG="$LOGDIR/${SCRIPT}.log"

echo "===== $(date '+%Y-%m-%d %H:%M') $LABEL =====" >> "$LOG"

# pull latest
git checkout gh-pages >> "$LOG" 2>&1
git pull origin gh-pages --ff-only >> "$LOG" 2>&1 || true

# 脚本已本地管理，不依赖 GitHub

# generate
export DEEPSEEK_API_KEY=sk-e08c986a456f4fed99d8250596e7f9e8
python3 scripts/generate_${SCRIPT}.py --output "${OUTPUT}.json" >> "$LOG" 2>&1
R=$?
if [ $R -ne 0 ]; then
  echo "❌ 生成失败 (exit=$R)" >> "$LOG"
  exit $R
fi

# push
git add "${OUTPUT}.json" >> "$LOG" 2>&1
if git diff --staged --quiet >> "$LOG" 2>&1; then
  echo "⚠️ 无变更跳过" >> "$LOG"
else
  git commit -m "auto: ${LABEL} $(date '+%Y-%m-%d')" >> "$LOG" 2>&1
  git push origin gh-pages >> "$LOG" 2>&1
  echo "✅ 推送完成" >> "$LOG"
fi
echo "===== 完成 =====" >> "$LOG"
