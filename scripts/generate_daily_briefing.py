#!/usr/bin/env python3
"""
每日风口简报 JSON 生成器 (DeepSeek V4)
用法: python3 generate_daily_briefing.py [--output 路径]
"""

import json, os, sys, subprocess, argparse, requests
from datetime import datetime, timezone, timedelta

# 北京时区
BJ_TZ = timezone(timedelta(hours=8))


DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "sk-e08c986a456f4fed99d8250596e7f9e8")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-flash"


def call_deepseek(system_prompt, user_prompt, max_tokens=8000):
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        "max_tokens": max_tokens, "temperature": 0.7
    }
    try:
        resp = requests.post(f"{DEEPSEEK_BASE_URL}/chat/completions", headers=headers, json=payload, timeout=300)
        resp.raise_for_status()
        data = resp.json()
        print(f"📊 Token: 输入 {data['usage']['prompt_tokens']} | 输出 {data['usage']['completion_tokens']}")
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"❌ API 调用失败: {e}")
        return None


def generate_briefing_content():
    today = datetime.now(BJ_TZ).strftime("%Y-%m-%d")

    system_prompt = f"""你是一位专业的科技情报分析师。请生成一份高质量的每日风口简报。

输出格式必须为 JSON，严格符合以下结构（不要输出任何其他内容）：
{{
  "date": "{today}",
  "briefing": {{
    "date": "{today}",
    "quote": "每日一句资讯感悟",
    "sections": [
      {{
        "id": "openclaw",
        "title": "OpenClaw 最新动态",
        "icon": "🦞",
        "articles": [
          {{
            "id": "brief-xxx",
            "title": "文章标题",
            "summary": "一句话摘要（30-50字）",
            "detail": "详细内容（100-200字）",
            "source": "来源"
          }}
        ]
      }}
    ]
  }},
  "hotProjects": {{
    "date": "{today}",
    "quote": "每日一句创业/投资箴言",
    "summary": "一句话总结今日最大风口趋势",
    "projects": [
      {{
        "id": "hot-xxx", "rank": 1, "name": "风口项目名称",
        "heat": "🔥🔥🔥🔥🔥", "heatLevel": 5,
        "oneLiner": "一句话概括（50字以内）",
        "whyHot": "为什么火（80-100字）",
        "highlights": ["关注点1", "关注点2", "关注点3", "关注点4"],
        "riskTip": "风险提示"
      }}
    ]
  }}
}}

具体要求：
- briefing.sections 包含4个分类：OpenClaw动态、热门技能推荐、iOS应用动态、科技新锐
- 每个分类 2-3 篇文章
- hotProjects 包含 3-4 个风口项目
- 所有内容基于当前日期和真实的科技趋势
- 使用中文，语言专业但不晦涩"""

    result = call_deepseek(
        system_prompt,
        f"请生成 {today} 的每日风口简报。要求4个资讯板块共10-12篇文章，3-4个风口项目。",
        max_tokens=8000
    )
    if not result:
        return None

    clean = result.strip()
    if clean.startswith("```json"): clean = clean[7:]
    elif clean.startswith("```"): clean = clean[3:]
    if clean.endswith("```"): clean = clean[:-3]
    clean = clean.strip()

    js = clean.find("{")
    je = clean.rfind("}") + 1
    if js >= 0 and je > js:
        try:
            return json.loads(clean[js:je])
        except json.JSONDecodeError as e:
            print(f"❌ JSON 解析失败: {e}")
            print(f"输出前500字: {result[:500]}")
            return None
    return None



def main():
    parser = argparse.ArgumentParser(description="生成每日风口简报 JSON")
    parser.add_argument("--output", default="daily-briefing.json",
                        help="输出文件路径（默认 daily-briefing.json）")
    args = parser.parse_args()

    print(f"📡 生成 {datetime.now(BJ_TZ).strftime('%Y-%m-%d')} 风口简报（DeepSeek V4）...")

    content = generate_briefing_content()
    if content:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(content, f, ensure_ascii=False, indent=2)
        b = content.get("briefing", {})
        hp = content.get("hotProjects", {})
        total_articles = sum(len(s.get("articles", [])) for s in b.get("sections", []))
        total_projects = len(hp.get("projects", []))
        print(f"✅ 已写入: {args.output}")
        print(f"   资讯: {len(b.get('sections', []))} 个板块, {total_articles} 篇文章")
        print(f"   风口: {total_projects} 个项目")
    else:
        print("❌ 生成失败")
        sys.exit(1)


if __name__ == "__main__":
    main()

