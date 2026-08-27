#!/bin/bash
# 百科扩充守护进程 — 检测到停止就重启
LOG="/var/log/dragonknightbeat/encyclopedia-watchdog.log"
SRC="/opt/dragonknightbeat-site/encyclopedia"
TARGET=500

# 检查是否全部达标
all_done=true
for f in "$SRC"/*.json; do
    name=$(basename "$f" .json)
    [ "$name" = "index" ] && continue
    count=$(python3 -c "import json; print(len(json.load(open(\"$f\"))))" 2>/dev/null)
    [ "$count" -lt "$TARGET" ] && all_done=false
done

if $all_done; then
    echo "$(date "+%H:%M") 全部达标，无需重启" >> "$LOG"
    exit 0
fi

# 检查是否有进程在运行
running=$(ps aux | grep "encyclopedia-loop\|gen_encyclopedia" | grep -v grep | wc -l)
if [ "$running" -gt 0 ]; then
    echo "$(date "+%H:%M") 进程运行中($running)，无需重启" >> "$LOG"
    exit 0
fi

# 需要重启
echo "$(date "+%H:%M") 进程已停，重启中..." >> "$LOG"
nohup /opt/dragonknightbeat-site/scripts/encyclopedia-loop-v2.sh &>/dev/null &
echo "$(date "+%H:%M") 已重启 PID:$!" >> "$LOG"
