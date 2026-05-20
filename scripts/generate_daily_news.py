#!/usr/bin/env python3
"""每日新闻晨报 JSON 生成器 — GitHub Actions 版"""
import json, os, sys, time, requests
from datetime import datetime, timezone, timedelta

BJ_TZ = timezone(timedelta(hours=8))
today = datetime.now(BJ_TZ).strftime("%Y-%m-%d")
OUTPUT = os.environ.get("OUTPUT_DIR", ".") + "/daily-news.json"
API_KEY = os.environ.get("DEEPSEEK_API_KEY")

if not API_KEY:
    print("❌ 未设置 DEEPSEEK_API_KEY"); sys.exit(1)

def call_api(system_prompt, user_prompt):
    resp = requests.post("https://api.deepseek.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={"model": "deepseek-chat", "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ], "max_tokens": 8192, "temperature": 0.7}, timeout=300)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]

def build_news():
    sp = """你是一个专业的新闻编辑。根据你的知识生成今天的新闻简报JSON。
要求：每个分类3-5条新闻。语言简洁客观。
分类：domestic(国内时政), international(国际时政), finance(财经动态), tech(科技前沿), other(其他要闻)
注意id需全局唯一，articles不能为空。
直接输出JSON，不要用markdown代码块：

{
  "date": "2026-05-20",
  "sections": [
    {
      "id": "domestic",
      "title": "国内时政",
      "icon": "🇨🇳",
      "articles": [{"id": "news-001", "title": "...", "summary": "..."}]
    }
  ]
}"""

    for attempt in range(1, 4):
        print(f"📡 第{attempt}/3次尝试...")
        result = call_api(sp, f"今天是{today}。请生成今日新闻简报JSON。")
        clean = result.strip()
        for prefix in ["```json", "```"]:
            if clean.startswith(prefix): clean = clean[len(prefix):]
        if clean.endswith("```"): clean = clean[:-3]
        clean = clean.strip()
        js = clean.find("{")
        je = clean.rfind("}") + 1
        if js < 0 or je <= js:
            print(f"⚠️ 未找到JSON，重试..."); time.sleep(2); continue
        try:
            data = json.loads(clean[js:je])
            data["date"] = today
            total = sum(len(s.get("articles", [])) for s in data.get("sections", []))
            if total == 0 or len(data.get("sections", [])) < 3:
                print(f"⚠️ 内容不完整({total}条)，重试..."); time.sleep(2); continue
            print(f"✅ {total}条/{len(data['sections'])}分类")
            return data
        except json.JSONDecodeError as e:
            print(f"❌ JSON解析失败: {e}"); time.sleep(2)
    print("❌ 生成失败"); return None

def main():
    content = build_news()
    if not content: sys.exit(1)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, indent=2)
    print(f"✅ {OUTPUT}")

if __name__ == "__main__":
    main()
