#!/bin/bash
# ECS 内存自动监控脚本 - 每2小时运行，内存危险时自动重启
LOG=/var/log/dragonknightbeat/mem-watchdog.log
MEM_AVAIL=$(free -m | awk '/^Mem:/{print $7}')
SWAP_USED=$(free -m | awk '/^Swap:/{print $3}')
SWAP_TOTAL=$(free -m | awk '/^Swap:/{print $2}')
SWAP_PCT=0
[ "$SWAP_TOTAL" -gt 0 ] && SWAP_PCT=$((SWAP_USED * 100 / SWAP_TOTAL))

echo "$(date '+%Y-%m-%d %H:%M') | avail=${MEM_AVAIL}MB swap=${SWAP_USED}/${SWAP_TOTAL}MB(${SWAP_PCT}%)" >> "$LOG"

# 安全阈值：可用内存 < 300MB 或 Swap 使用 > 40%
if [ "$MEM_AVAIL" -lt 300 ] || [ "$SWAP_PCT" -gt 40 ]; then
  echo "$(date '+%Y-%m-%d %H:%M') ⚠️ 预警！MEM_AVAIL=${MEM_AVAIL}MB, SWAP=${SWAP_USED}/${SWAP_TOTAL}MB(${SWAP_PCT}%) — 触发自动重启" >> "$LOG"
  /sbin/shutdown -r +1 "⚠️ ECS资源不足(${MEM_AVAIL}MB/${SWAP_PCT}%)，自动重启恢复"
fi
