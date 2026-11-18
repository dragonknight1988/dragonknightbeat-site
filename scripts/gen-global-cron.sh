#!/bin/bash
# DK 全球晨报矩阵 — 各区域晨报生成（ECS crontab 调用）
# 方案 B：一区域一 App，当地语言晨报（2026-11-18 龙骑士拍板）
# 用法: gen-global-cron.sh [区域1 区域2 ...]（不带参数 = 全部区域）
#   区域: ja kr us de fr nl vn th my（后续 be 在此追加）
# 已上线：ja 日本 / kr 韩国 / us 美国 / de 德国 / fr 法国 / nl 荷兰 / vn 越南 / th 泰国 / my 马来西亚
# ⚠️ 与大陆版 gen-cron.sh 完全独立，不得互相干扰
#
# crontab（各区域按当地早晨出刊）：
#   30 4  * * * gen-global-cron.sh ja kr   # 北京凌晨 = 日韩早晨 05:30 JST/KST
#   0  21 * * * gen-global-cron.sh us      # 北京 21:00 = 美东 08:00 ET 当日早刊
#   0  15 * * * gen-global-cron.sh de fr nl # 北京 15:00 = 中欧 08:00 CET 当日早刊
#   0  6  * * * gen-global-cron.sh my      # 北京 06:00 = 马来 06:00 MYT 当日早刊
#   0  7  * * * gen-global-cron.sh vn th   # 北京 07:00 = 越泰 06:00 ICT 当日早刊

set -u
SITE=/opt/dragonknightbeat-site
WEB=/var/www/dragonknightbeat.com
LOGDIR=/var/log/dragonknightbeat
LOG=$LOGDIR/global-morning.log
mkdir -p "$WEB/morning/ja" "$WEB/morning/kr" "$WEB/morning/us" "$WEB/morning/de" "$WEB/morning/fr" "$WEB/morning/nl" "$WEB/morning/vn" "$WEB/morning/th" "$WEB/morning/my" "$LOGDIR"

REGIONS=("$@")
if [ ${#REGIONS[@]} -eq 0 ]; then
  REGIONS=(ja kr us de fr nl vn th my)
fi

echo "=== $(date '+%F %T') global-morning start [${REGIONS[*]}] ===" >> "$LOG"

for r in "${REGIONS[@]}"; do
  case "$r" in
    ja)
      # ---- 🇯🇵 日本：DK 朝報 ----
      python3 "$SITE/scripts/generate_daily_news_ja.py" --output "$WEB/morning/ja/daily-morning.json" >> "$LOG" 2>&1
      echo "[ja] exit=$?" >> "$LOG" ;;
    kr)
      # ---- 🇰🇷 韩国：DK 조간 ----
      python3 "$SITE/scripts/generate_daily_news_kr.py" --output "$WEB/morning/kr/daily-morning.json" >> "$LOG" 2>&1
      echo "[kr] exit=$?" >> "$LOG" ;;
    us)
      # ---- 🇺🇸 美国：DK Morning ----
      python3 "$SITE/scripts/generate_daily_news_us.py" --output "$WEB/morning/us/daily-morning.json" >> "$LOG" 2>&1
      echo "[us] exit=$?" >> "$LOG" ;;
    de)
      # ---- 🇩🇪 德国：DK Morgenpost ----
      python3 "$SITE/scripts/generate_daily_news_de.py" --output "$WEB/morning/de/daily-morning.json" >> "$LOG" 2>&1
      echo "[de] exit=$?" >> "$LOG" ;;
    fr)
      # ---- 🇫🇷 法国：DK Matin ----
      python3 "$SITE/scripts/generate_daily_news_fr.py" --output "$WEB/morning/fr/daily-morning.json" >> "$LOG" 2>&1
      echo "[fr] exit=$?" >> "$LOG" ;;
    nl)
      # ---- 🇳🇱 荷兰：DK Ochtend ----
      python3 "$SITE/scripts/generate_daily_news_nl.py" --output "$WEB/morning/nl/daily-morning.json" >> "$LOG" 2>&1
      echo "[nl] exit=$?" >> "$LOG" ;;
    vn)
      # ---- 🇻🇳 越南：DK Tin Sáng ----
      python3 "$SITE/scripts/generate_daily_news_vn.py" --output "$WEB/morning/vn/daily-morning.json" >> "$LOG" 2>&1
      echo "[vn] exit=$?" >> "$LOG" ;;
    th)
      # ---- 🇹🇭 泰国：DK เช้าข่าว ----
      python3 "$SITE/scripts/generate_daily_news_th.py" --output "$WEB/morning/th/daily-morning.json" >> "$LOG" 2>&1
      echo "[th] exit=$?" >> "$LOG" ;;
    my)
      # ---- 🇲🇾 马来西亚：DK Pagi ----
      python3 "$SITE/scripts/generate_daily_news_my.py" --output "$WEB/morning/my/daily-morning.json" >> "$LOG" 2>&1
      echo "[my] exit=$?" >> "$LOG" ;;
    *)
      echo "[$r] unknown region, skipped" >> "$LOG" ;;
  esac
done

chmod -R a+r "$WEB/morning" 2>/dev/null
echo "=== $(date '+%F %T') global-morning done ===" >> "$LOG"
