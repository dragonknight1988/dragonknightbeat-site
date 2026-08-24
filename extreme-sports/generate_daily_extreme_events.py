#!/usr/bin/env python3
"""
每日极限运动赛事生成器
部署在ECS上，每天自动运行
"""

import json, os, sys, argparse, requests
from datetime import datetime, timezone, timedelta

BJ_TZ = timezone(timedelta(hours=8))

MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "tp-c6irsm5360gu18hd64hlmz47ltg54c5rbszghj45t5z96c31")
MIMO_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
MIMO_MODEL = "xiaomi/mimo-v2.5-pro"


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


def generate_events():
    today = datetime.now(BJ_TZ).strftime("%Y-%m-%d")
    
    system_prompt = f"""你是一个极限运动赛事策划专家。请生成一份极限运动赛事列表，涵盖未来3-6个月的赛事。

覆盖运动：冲浪、跳伞、攀岩、蹦极、滑翔伞、滑板、单板滑雪、越野摩托、跑酷、极限潜水、翼装飞行

输出严格JSON格式：
{{
  "date": "{today}",
  "events": [
    {{
      "id": "evt-001",
      "name": "赛事名称",
      "sport": "运动类别",
      "date": "2026-XX-XX",
      "location": "城市",
      "country": "国家",
      "level": "业余/专业/国际级",
      "description": "50-100字赛事介绍",
      "registrationUrl": "报名链接（可为null）",
      "registrationDeadline": "报名截止日期",
      "status": "报名中/即将开放/已截止/进行中",
      "price": "报名费用",
      "organizer": "主办方"
    }}
  ]
}}

要求：
- 生成 15-20 场赛事
- 包含国际大赛、区域赛事、业余体验赛
- 时间分布在未来3-6个月
- 包含国内外赛事
- status 字段合理分配"""

    print(f"🏁 生成极限运动赛事...")
    result = call_mimo(system_prompt, f"请生成极限运动赛事列表，日期：{today}")
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
    parser.add_argument("--output", default="daily-extreme-events.json")
    args = parser.parse_args()
    
    data = generate_events()
    if data:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ 已写入: {args.output} ({len(data.get('events', []))} 场赛事)")
    else:
        print("❌ 生成失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
