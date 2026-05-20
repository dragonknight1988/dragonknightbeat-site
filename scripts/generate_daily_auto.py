#!/usr/bin/env python3
"""每日汽车新闻日报 JSON 生成器 — GitHub Actions 版"""
import json, os, sys, requests
from datetime import datetime, timezone, timedelta

BJ_TZ = timezone(timedelta(hours=8))
today = datetime.now(BJ_TZ).strftime("%Y-%m-%d")
OUTPUT = os.environ.get("OUTPUT_DIR", ".") + "/daily-auto.json"
API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not API_KEY:
    print("❌ 未设置 DEEPSEEK_API_KEY"); sys.exit(1)

def repair_articles(data):
    aliases = {"dynamic": "detail", "description": "detail", "content": "detail"}
    fixed = 0
    for sec in data.get("sections", []):
        for art in sec.get("articles", []):
            for wrong, correct in aliases.items():
                if wrong in art and correct not in art:
                    art[correct] = art.pop(wrong)
                    fixed += 1
                    break
    if fixed: print(f"🔧 修复 {fixed} 个字段名")
    return data

def main():
    sp = f"""你是专业的汽车新闻编辑。生成今日汽车新闻日报JSON。
必须包含5个板块：今日头条、中国汽车市场、国际动态、市场分析、明日展望。
要求数据真实、语句专业。输出JSON不要markdown代码块：
{{"date":"{today}","summary":"一句话概括","sections":[
{{"id":"headline","title":"今日头条","icon":"📰","articles":[{{"id":"auto-001","title":"标题","summary":"摘要","detail":"详情","source":"来源"}}]}},
{{"id":"china-market","title":"中国汽车市场","icon":"🇨🇳","articles":[]}},
{{"id":"international","title":"国际动态","icon":"🌍","articles":[]}},
{{"id":"market-analysis","title":"市场分析","icon":"📊","articles":[]}},
{{"id":"future-outlook","title":"明日展望","icon":"🔮","articles":[]}}
]}}"""

    resp = requests.post("https://api.deepseek.com/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={"model": "deepseek-chat", "messages": [
            {"role": "system", "content": sp},
            {"role": "user", "content": f"生成{today}汽车新闻日报，5个板块共12-15篇文章"}
        ], "max_tokens": 8000, "temperature": 0.7}, timeout=300)
    resp.raise_for_status()
    result = resp.json()["choices"][0]["message"]["content"]

    clean = result.strip()
    for p in ["```json", "```"]:
        if clean.startswith(p): clean = clean[len(p):]
    if clean.endswith("```"): clean = clean[:-3]
    js = clean.find("{"); je = clean.rfind("}") + 1
    data = repair_articles(json.loads(clean[js:je]))

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    articles = sum(len(s.get("articles", [])) for s in data.get("sections", []))
    print(f"✅ {OUTPUT} — {len(data.get('sections',[]))}板块/{articles}篇文章")

if __name__ == "__main__":
    main()
