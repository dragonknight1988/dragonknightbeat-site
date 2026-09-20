#!/bin/bash
# 检查新闻是否更新到今天
TODAY=\$(TZ=Asia/Shanghai date +%Y-%m-%d)
CONTENT_DATE=\$(curl -s 'https://dragonknightbeat.com/daily-news.json' 2>/dev/null | python3 -c 'import sys,json; print(json.load(sys.stdin).get("date","unknown"))' 2>/dev/null)

if [ "\$CONTENT_DATE" = "\$TODAY" ]; then
  echo "✅ 新闻已更新到 \$TODAY"
  exit 0
else
  echo "❌ 新闻未更新！数据日期=\$CONTENT_DATE，今天=\$TODAY"
  exit 1
fi
