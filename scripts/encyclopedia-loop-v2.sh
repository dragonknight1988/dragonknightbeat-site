#!/bin/bash
# 百科循环扩充 v2 — 含自动重试
LOG="/var/log/dragonknightbeat/encyclopedia-expand.log"
SRC="/opt/dragonknightbeat-site/encyclopedia"
WEB="/var/www/dragonknightbeat.com/encyclopedia"
TARGET=500
MAX_ROUNDS=20

source /opt/dragonknightbeat-site/.env

CATEGORIES=("chemistry" "economics" "geography" "medicine" "military" "philosophy" "physics" "history" "technology")

get_count() {
    python3 -c "import json; print(len(json.load(open(\"$SRC/$1.json\"))))" 2>/dev/null
}

rebuild_index() {
    python3 -c "
import json, os, glob
src=\"$SRC\"; all_e=[]
for f in glob.glob(os.path.join(src,\"*.json\")):
    if os.path.basename(f)==\"index.json\": continue
    all_e.extend(json.load(open(f)))
idx=[{\"id\":e[\"id\"],\"title\":e[\"title\"],\"category\":e[\"category\"],\"categoryName\":e[\"categoryName\"],\"summary\":e.get(\"summary\",\"\")} for e in all_e]
with open(os.path.join(src,\"index.json\"),\"w\",encoding=\"utf-8\") as fp: json.dump(idx,fp,ensure_ascii=False,indent=2)
" 2>/dev/null
}

sync_web() { cp "$SRC"/*.json "$WEB"/ 2>/dev/null; }

echo "===== $(date "+%Y-%m-%d %H:%M") v2循环扩充启动 =====" >> "$LOG"

for round in $(seq 1 $MAX_ROUNDS); do
    echo "" >> "$LOG"
    echo "🔁 === 第 $round 轮 ===" >> "$LOG"
    all_done=true
    for cat in "${CATEGORIES[@]}"; do
        count=$(get_count "$cat")
        [ "$count" -ge "$TARGET" ] && { echo "  ✅ $cat: $count"; continue; }
        all_done=false
        echo "  🔄 $cat: $count → $TARGET" >> "$LOG"
        timeout 1800 python3 -u /opt/dragonknightbeat-site/scripts/gen_encyclopedia_expand_v2.py "$cat" >> "$LOG" 2>&1
        new_count=$(get_count "$cat")
        echo "  📊 $cat: $count → $new_count" >> "$LOG"
        rebuild_index; sync_web; sleep 3
    done
    $all_done && { echo "🎉 全部达标！"; break; }
done

sync_web
echo "===== $(date "+%Y-%m-%d %H:%M") 结束 =====" >> "$LOG"
