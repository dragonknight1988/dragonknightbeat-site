#!/bin/bash
# 每5分钟生成一次状态JSON，零SSH查看ECS状态

WEBROOT="/var/www/dragonknightbeat.com"
OUT="$WEBROOT/server-status.json"

# 内存
MEM_TOTAL=$(free -m | awk "/Mem:/{print \$2}")
MEM_USED=$(free -m | awk "/Mem:/{print \$3}")
MEM_AVAIL=$(free -m | awk "/Mem:/{print \$7}")
SWAP_TOTAL=$(free -m | awk "/Swap:/{print \$2}")
SWAP_USED=$(free -m | awk "/Swap:/{print \$3}")

# CPU负载
LOAD=$(uptime | awk -F"load average:" "{print \$2}" | xargs)

# 运行时间
UPTIME=$(uptime -p | sed "s/up //")

# sshd进程数
SSHD_COUNT=$(ps aux | grep sshd | grep -v grep | wc -l)

# 僵尸进程
ZOMBIE_COUNT=$(ps aux | grep -w Z | grep -v grep | wc -l)

# 磁盘
DISK_USED=$(df -h / | awk "NR==2{print \$3}")
DISK_AVAIL=$(df -h / | awk "NR==2{print \$4}")
DISK_PCT=$(df -h / | awk "NR==2{print \$5}")

# 总进程数
TOTAL_PROCS=$(ps aux | wc -l)

# 网络可达性
ENGLISH_OK=$(curl -so /dev/null -w "%{http_code}" https://dragonknightbeat.com/daily-english.json 2>/dev/null || echo "0")
NEWS_OK=$(curl -so /dev/null -w "%{http_code}" https://dragonknightbeat.com/daily-news.json 2>/dev/null || echo "0")

cat > $OUT <<EOF
{
  "timestamp": "$(date +%Y-%m-%dT%H:%M:%S%z)",
  "uptime": "$UPTIME",
  "load": "$LOAD",
  "memory": {
    "total_mb": $MEM_TOTAL,
    "used_mb": $MEM_USED,
    "available_mb": $MEM_AVAIL,
    "used_pct": $(( MEM_USED * 100 / MEM_TOTAL ))
  },
  "swap": {
    "total_mb": $SWAP_TOTAL,
    "used_mb": $SWAP_USED,
    "used_pct": $([ "$SWAP_TOTAL" != "0" ] && echo $(( SWAP_USED * 100 / SWAP_TOTAL )) || echo 0)
  },
  "processes": {
    "total": $TOTAL_PROCS,
    "sshd": $SSHD_COUNT,
    "zombie": $ZOMBIE_COUNT
  },
  "disk": {
    "used": "$DISK_USED",
    "available": "$DISK_AVAIL",
    "used_pct": "$DISK_PCT"
  },
  "web_services": {
    "daily_english": $ENGLISH_OK,
    "daily_news": $NEWS_OK
  }
}
EOF
echo "✅ Status updated: $(date)"
