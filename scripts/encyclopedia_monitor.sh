#!/bin/bash
# 百科扩充任务自动监控脚本
# 每5分钟检查一次，进程挂了自动重启，全部完成自动退出

LOG="/tmp/encyclopedia_monitor.log"
EXPAND_LOG="/tmp/encyclopedia_expand_v2.log"
SCRIPT="/opt/dragonknightbeat-site/scripts/gen_encyclopedia_expand_v2.py"
DIR="/opt/dragonknightbeat-site/encyclopedia"
TARGET=500

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"; }

check_counts() {
    local total=0
    local done=0
    for f in "$DIR"/*.json; do
        fname=$(basename "$f")
        [[ "$fname" == "index.json" ]] && continue
        count=$(python3 -c "import json; print(len(json.load(open('$f'))))" 2>/dev/null || echo 0)
        total=$((total + 1))
        if [ "$count" -ge "$TARGET" ]; then
            done=$((done + 1))
        fi
        echo "  $fname: $count"
    done
    echo "完成: $done/$total 个分类"
}

is_running() {
    ps aux | grep "gen_encyclopedia_expand_v2.py" | grep python3 | grep -v grep | wc -l
}

restart() {
    log "⚠️ 进程已停止，正在重启..."
    cd /opt/dragonknightbeat-site
    nohup python3 -u scripts/gen_encyclopedia_expand_v2.py > "$EXPAND_LOG" 2>&1 &
    log "✅ 已重启，PID: $!"
}

# 检查是否全部完成
all_done() {
    local done=0
    local total=0
    for f in "$DIR"/*.json; do
        fname=$(basename "$f")
        [[ "$fname" == "index.json" ]] && continue
        total=$((total + 1))
        count=$(python3 -c "import json; print(len(json.load(open('$f'))))" 2>/dev/null || echo 0)
        [ "$count" -ge "$TARGET" ] && done=$((done + 1))
    done
    [ "$done" -eq "$total" ]
}

log "========== 监控启动 =========="

while true; do
    log "--- 检查 ---"
    
    # 先看是否全部完成
    if all_done; then
        log "🎉 所有分类已达${TARGET}条，任务完成！"
        log "最终统计:"
        check_counts >> "$LOG"
        log "========== 监控结束 =========="
        exit 0
    fi
    
    running=$(is_running)
    if [ "$running" -gt 0 ]; then
        log "✅ 进程运行中 (共 $running 个)"
        # 打印当前进度
        check_counts >> "$LOG"
    else
        log "❌ 进程已停止！"
        check_counts >> "$LOG"
        restart
    fi
    
    sleep 300  # 5分钟检查一次
done
