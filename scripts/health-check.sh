#!/bin/bash
WEBROOT=/var/www/dragonknightbeat.com
TODAY=$(date +%Y-%m-%d)
FAILURES=""

check_file() {
  local file=$1
  local label=$2
  local path="${WEBROOT}/${file}.json"
  
  if [ ! -f "$path" ]; then
    FAILURES="${FAILURES}${label}: 文件不存在\n"
    return
  fi
  
  local fdate=$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("date",""))' "$path")
  if [ "$fdate" != "$TODAY" ]; then
    FAILURES="${FAILURES}${label}: 日期${fdate:-读取失败}\n"
  else
    echo "✅ ${label}: ${fdate}"
  fi
}

echo "=== 健康检查 ${TODAY} ==="
check_file "daily-news" "新闻晨报"
check_file "daily-english" "每日英语"
check_file "daily-briefing" "资讯早报"
check_file "daily-programming" "编程教程"
check_file "daily-auto" "汽车新闻"
check_file "daily-autotech" "汽车知识"

if [ -n "$FAILURES" ]; then
  echo ""
  echo "⚠️ 以下内容未更新："
  echo -e "$FAILURES"
  echo -e "$FAILURES" > /tmp/dk-health-failures.txt
  exit 1
else
  echo ""
  echo "🎉 全部OK"
  rm -f /tmp/dk-health-failures.txt
  exit 0
fi
