#!/bin/bash
# 百科全书自动扩充 + 监控脚本
LOG="/var/log/dragonknightbeat/encyclopedia-expand.log"
SRC="/opt/dragonknightbeat-site/encyclopedia"
WEB="/var/www/dragonknightbeat.com/encyclopedia"
TARGET=500

mkdir -p "$(dirname $LOG)"
echo "===== $(date "+%Y-%m-%d %H:%M") 百科全书扩充开始 =====" >> "$LOG"

source /opt/dragonknightbeat-site/.env

check_status() {
    local all_ok=true
    for f in "$SRC"/*.json; do
        local name=$(basename "$f" .json)
        [ "$name" = "index" ] && continue
        local count=$(python3 -c "import json; print(len(json.load(open(\"$f\"))))" 2>/dev/null)
        if [ "$count" -ge "$TARGET" ]; then
            echo "  ✅ $name: $count" >> "$LOG"
        else
            echo "  ⏳ $name: $count/$TARGET (差 $((TARGET-count)))" >> "$LOG"
            all_ok=false
        fi
    done
    $all_ok
}

sync_to_web() {
    cp "$SRC"/*.json "$WEB"/
    echo "  📦 已同步到网站" >> "$LOG"
}

if check_status; then
    echo "🎉 所有分类已达${TARGET}条" >> "$LOG"
    sync_to_web
    echo "===== 完成 =====" >> "$LOG"
    exit 0
fi

CATEGORIES=("chemistry" "economics" "geography" "medicine" "military" "philosophy" "physics" "history" "technology")

for cat in "${CATEGORIES[@]}"; do
    count=$(python3 -c "import json; print(len(json.load(open(\"$SRC/$cat.json\"))))" 2>/dev/null)
    if [ "$count" -ge "$TARGET" ]; then
        echo "⏭️  $cat: ${count}条 已达标" >> "$LOG"
        continue
    fi
    echo "🔄 扩充 $cat ($count → $TARGET)..." >> "$LOG"
    timeout 1800 python3 -u /opt/dragonknightbeat-site/scripts/gen_encyclopedia_expand_v2.py "$cat" >> "$LOG" 2>&1
    rc=$?
    new_count=$(python3 -c "import json; print(len(json.load(open(\"$SRC/$cat.json\"))))" 2>/dev/null)
    if [ $rc -eq 0 ]; then
        echo "✅ $cat: $count → $new_count" >> "$LOG"
    else
        echo "❌ $cat 失败(rc=$rc): $count → $new_count" >> "$LOG"
    fi
    sync_to_web
    sleep 5
done

echo "" >> "$LOG"
echo "📊 最终状态:" >> "$LOG"
check_status
sync_to_web
echo "===== 全部完成 =====" >> "$LOG"
