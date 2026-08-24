#!/bin/bash
# 极限运动 App 服务端部署脚本
# 在 ECS 上运行

set -e

WEBROOT="/var/www/dragonknightbeat.com"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DK_API_PORT=3456

echo "🚀 部署极限运动服务端..."

# 1. 复制训练路径静态数据
echo "📚 复制训练路径数据..."
cp "$SCRIPT_DIR/extreme-training-paths.json" "$WEBROOT/"
echo "✅ 训练路径已部署"

# 2. 生成今日新闻（如果不存在）
NEWS_FILE="$WEBROOT/daily-extreme-news.json"
if [ ! -f "$NEWS_FILE" ] || [ "$(stat -c %Y "$NEWS_FILE" 2>/dev/null || stat -f %m "$NEWS_FILE" 2>/dev/null)" -lt "$(date -d 'today 00:00' +%s 2>/dev/null || date -j -f '%Y%m%d' "$(date +%Y%m%d)" +%s 2>/dev/null)" ]; then
    echo "📰 生成今日极限运动新闻..."
    cd "$SCRIPT_DIR"
    python3 generate_daily_extreme_news.py --output "$NEWS_FILE"
else
    echo "📰 今日新闻已存在，跳过"
fi

# 3. 生成赛事信息
EVENTS_FILE="$WEBROOT/daily-extreme-events.json"
if [ ! -f "$EVENTS_FILE" ]; then
    echo "🏁 生成赛事信息..."
    cd "$SCRIPT_DIR"
    python3 generate_daily_extreme_events.py --output "$EVENTS_FILE"
else
    echo "🏁 赛事信息已存在，跳过"
fi

# 4. 初始化龙骑士数据（如果不存在）
DK_FILE="$WEBROOT/dragon-knight-posts.json"
if [ ! -f "$DK_FILE" ]; then
    echo "🐉 初始化龙骑士数据..."
    cat > "$DK_FILE" << 'EOF'
{
  "date": "2026-05-31",
  "posts": [
    {
      "id": "dk-welcome",
      "title": "欢迎来到疯狂的龙骑士！",
      "content": "这里是龙骑士的极限运动专属空间。我会在这里分享极限运动的精彩瞬间、训练心得和冒险故事。敬请期待！🐉🔥",
      "type": "article",
      "mediaUrl": null,
      "link": null,
      "publishTime": "2026-05-31 00:00",
      "tags": ["公告", "欢迎"]
    }
  ]
}
EOF
    echo "✅ 龙骑士数据已初始化"
else
    echo "🐉 龙骑士数据已存在"
fi

# 5. 启动龙骑士API服务
echo "🐉 启动龙骑士API服务..."
# 检查是否已有进程
EXISTING_PID=$(pgrep -f "dragon-knight-api" || true)
if [ -n "$EXISTING_PID" ]; then
    echo "   已有运行中的进程 (PID: $EXISTING_PID)，先停止..."
    kill $EXISTING_PID 2>/dev/null || true
    sleep 1
fi

# 用nohup后台运行
cd "$SCRIPT_DIR"
nohup node dragon-knight-api.js > /var/log/dragonknightbeat/dragon-knight-api.log 2>&1 &
DK_PID=$!
echo "✅ 龙骑士API已启动 (PID: $DK_PID, Port: $DK_API_PORT)"

# 6. 添加cron任务（每日新闻和赛事）
echo "⏰ 配置定时任务..."
CRON_NEWS="0 6 * * * cd /opt/dragonknightbeat-site && source .env && python3 $SCRIPT_DIR/generate_daily_extreme_news.py --output $WEBROOT/daily-extreme-news.json >> /var/log/dragonknightbeat/daily_extreme_news.log 2>&1"
CRON_EVENTS="10 6 * * 1 cd /opt/dragonknightbeat-site && source .env && python3 $SCRIPT_DIR/generate_daily_extreme_events.py --output $WEBROOT/daily-extreme-events.json >> /var/log/dragonknightbeat/daily_extreme_events.log 2>&1"

# 检查是否已存在
(crontab -l 2>/dev/null | grep -v "daily_extreme_news\|daily_extreme_events"; echo "$CRON_NEWS"; echo "$CRON_EVENTS") | crontab -
echo "✅ 定时任务已配置"

echo ""
echo "🎉 部署完成！"
echo ""
echo "📋 数据文件："
echo "   📰 $NEWS_FILE"
echo "   🏁 $EVENTS_FILE"
echo "   📚 $WEBROOT/extreme-training-paths.json"
echo "   🐉 $DK_FILE"
echo ""
echo "🐉 龙骑士API："
echo "   推送: curl -X POST http://localhost:$DK_API_PORT/api/dragon-knight/push \\"
echo "     -H 'Authorization: Bearer dragonknight2026extreme' \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"title\":\"标题\",\"content\":\"内容\",\"type\":\"article\",\"tags\":[\"标签\"]}'"
echo ""
echo "   查看: curl http://localhost:$DK_API_PORT/api/dragon-knight/posts"
