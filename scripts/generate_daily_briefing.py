#!/usr/bin/env python3
"""每日风口简报 JSON 生成器 — GitHub Actions 版"""
import json, os, sys, requests
from datetime import datetime, timezone, timedelta

BJ_TZ = timezone(timedelta(hours=8))
today = datetime.now(BJ_TZ).strftime("%Y-%m-%d")
OUTPUT = os.environ.get("OUTPUT_DIR", ".") + "/daily-briefing.json"
API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not API_KEY:
    print("❌ 未设置 DEEPSEEK_API_KEY"); sys.exit(1)

def main():
    sp = f"""你是一位专业的科技情报分析师。生成高质量每日风口简报。
输出JSON，不要markdown代码块：
{{"date":"{today}","briefing":{{"date":"{today}","quote":"今日引语","sections":[
{{"id":"openclaw","title":"OpenClaw 最新动态","icon":"🦞","articles":[{{"id":"brief-001","title":"标题","summary":"摘要","detail":"详情","source":"来源"}}]}},
{{"id":"hotSkills","title":"热门技能推荐","icon":"🎯","articles":[{{"id":"brief-004","title":"标题","summary":"摘要","detail":"详情","source":"来源"}}]}},
{{"id":"appTrends","title":"趋势洞察","icon":"📱","articles":[{{"id":"brief-007","title":"标题","summary":"摘要","detail":"详情","source":"来源"}}]}},
{{"id":"techFrontier","title":"科技新锐","icon":"🚀","articles":[{{"id":"brief-010","title":"标题","summary":"摘要","detail":"详情","source":"来源"}}]}}
]}}}}
要求：信息要新，不要编造，使用你知道的最新行业动态。OpenClaw相关可以写社区动态或技术趋势。每个分类3篇文章。"""

    resp = requests.post("https://api.deepseek.com/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={"model": "deepseek-chat", "messages": [
            {"role": "system", "content": sp},
            {"role": "user", "content": f"生成{today}每日风口简报"}
        ], "max_tokens": 8000, "temperature": 0.7}, timeout=300)
    resp.raise_for_status()
    result = resp.json()["choices"][0]["message"]["content"]

    clean = result.strip()
    for p in ["```json", "```"]:
        if clean.startswith(p): clean = clean[len(p):]
    if clean.endswith("```"): clean = clean[:-3]
    js = clean.find("{"); je = clean.rfind("}") + 1
    data = json.loads(clean[js:je])

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ {OUTPUT}")

if __name__ == "__main__":
    main()
