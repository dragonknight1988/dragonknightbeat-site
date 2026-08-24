#!/usr/bin/env python3
"""
每日极限运动新闻生成器
部署在ECS上，每天自动运行
"""

import json, os, sys, argparse, requests
from datetime import datetime, timezone, timedelta

BJ_TZ = timezone(timedelta(hours=8))

MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "tp-c6irsm5360gu18hd64hlmz47ltg54c5rbszghj45t5z96c31")
MIMO_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
MIMO_MODEL = "xiaomi/mimo-v2.5"


def call_mimo(system_prompt, user_prompt, max_tokens=6000):
    headers = {
        "Authorization": f"Bearer {MIMO_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MIMO_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "max_tokens": max_tokens,
        "temperature": 0.8
    }
    try:
        resp = requests.post(f"{MIMO_BASE_URL}/chat/completions", headers=headers, json=payload, timeout=300)
        resp.raise_for_status()
        data = resp.json()
        usage = data.get("usage", {})
        if usage:
            print(f"📊 Token: 输入 {usage.get('prompt_tokens', '?')} | 输出 {usage.get('completion_tokens', '?')}")
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"❌ API 调用失败: {e}")
        return None


def generate_news():
    today = datetime.now(BJ_TZ).strftime("%Y-%m-%d")
    
    system_prompt = f"""你是一个极限运动新闻编辑。请生成 {today} 的极限运动新闻摘要。

覆盖以下运动类别：冲浪、跳伞、攀岩、蹦极、滑翔伞、滑板、单板滑雪、越野摩托、跑酷、极限潜水、翼装飞行

输出严格JSON格式，不要输出其他内容：
{{
  "date": "{today}",
  "news": [
    {{
      "id": "news-001",
      "title": "新闻标题",
      "summary": "50-100字的摘要",
      "category": "运动类别（从上面选一个）",
      "source": "信息来源",
      "url": null,
      "imageUrl": null,
      "publishTime": "发布时间"
    }}
  ]
}}

要求：
- 生成 10-15 条新闻
- 涵盖国际赛事、运动员动态、装备科技、安全提示、培训资讯等
- 包含具体数据和人名（可以是真实的或合理的）
- 类别分布尽量均匀"""

    print(f"📰 生成 {today} 极限运动新闻...")
    result = call_mimo(system_prompt, f"请生成 {today} 的极限运动新闻")
    if not result:
        return None
    
    json_start = result.find("{")
    json_end = result.rfind("}") + 1
    if json_start >= 0 and json_end > json_start:
        try:
            return json.loads(result[json_start:json_end])
        except json.JSONDecodeError as e:
            print(f"❌ JSON解析失败: {e}")
            return None
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="daily-extreme-news.json")
    args = parser.parse_args()
    
    data = generate_news()
    if data:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ 已写入: {args.output} ({len(data.get('news', []))} 条新闻)")
    else:
        print("❌ 生成失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
