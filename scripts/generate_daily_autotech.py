#!/usr/bin/env python3
"""
每日汽车技术知识 JSON 生成器 (MiMo Pro)
用法: python3 generate_daily_autotech.py [--output 路径]
"""

import json, os, sys, argparse, re, requests
from datetime import datetime, timezone, timedelta

BJ_TZ = timezone(timedelta(hours=8))

MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "tp-c6irsm5360gu18hd64hlmz47ltg54c5rbszghj45t5z96c31")
MIMO_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
MIMO_MODEL = "xiaomi/mimo-v2.5"

CATEGORIES = [
    "新能源汽车", "发动机与动力系统", "底盘与悬挂", "电气与电子",
    "车身与钣金", "内外饰", "安全与ADAS", "智能制造",
    "汽车材料", "技术趋势"
]


def call_mimo(system_prompt, user_prompt, max_tokens=6000):
    headers = {"Authorization": f"Bearer {MIMO_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": MIMO_MODEL,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        "max_tokens": max_tokens, "temperature": 0.7
    }
    try:
                resp = requests.post(f"{MIMO_BASE_URL}/chat/completions", headers=headers, json=payload, timeout=(15, 180), stream=True)
        resp.raise_for_status()
        import json as _json
        chunks = []
        for chunk in resp.iter_content(chunk_size=None):
            if chunk:
                chunks.append(chunk)
        raw = b"".join(chunks).decode("utf-8")
        data = _json.loads(raw)        print(f"📊 Token: 输入 {data['usage']['prompt_tokens']} | 输出 {data['usage']['completion_tokens']}")
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"❌ API 调用失败: {e}")
        return None


def generate_article():
    today = datetime.now(BJ_TZ).strftime("%Y-%m-%d")
    day_of_year = datetime.now(BJ_TZ).timetuple().tm_yday
    category = CATEGORIES[day_of_year % len(CATEGORIES)]

    system_prompt = f"""你是一位资深汽车技术工程师兼科普作家。请生成一篇专业的汽车技术知识文章，输出JSON格式。

今日分类: {category}

文章要求：
1. 主题必须是真实存在的汽车技术，如：电池热管理系统、线控制动、毫米波雷达原理、48V轻混架构等
2. 内容要有技术深度，兼顾专业性和可读性
3. 正文800-1500字，Markdown格式（可用###分级标题、列表、代码块等）
4. 总结一句话（20-40字）
5. 难度等级1-5（1最简单，5最难）
6. 3-5个标签（逗号分隔）

⚠️ 事实核查要求（非常重要）：
- 所有技术描述必须符合真实工程原理
- 严禁编造不存在的技术或数据
- 如引用具体数据必须真实可靠
- 不确定的不要写

严格输出JSON格式：
{{
  "date": "{today}",
  "article": {{
    "title": "文章标题",
    "content": "Markdown格式的完整正文...",
    "summary": "一句话概括（20-40字）",
    "category": "{category}",
    "tags": "标签1,标签2,标签3",
    "difficulty": 3,
    "orderIndex": {day_of_year}
  }},
  "quiz": [
    {{
      "question": "关于文章中提到的技术，以下哪个说法正确？",
      "options": ["选项A", "选项B", "选项C", "选项D"],
      "correctIndex": 0,
      "explanation": "为什么选这个的简要解析"
    }},
    {{
      "question": "第二道测验题...",
      "options": ["A", "B", "C", "D"],
      "correctIndex": 2,
      "explanation": "..."
    }},
    {{
      "question": "第三道测验题...",
      "options": ["A", "B", "C", "D"],
      "correctIndex": 1,
      "explanation": "..."
    }}
  ]
}}

注意：3道测验题必须基于文章内容，必须有唯一正确答案。"""

    user_prompt = f"请为 {today} 生成一篇关于「{category}」的汽车技术知识文章，含3道测验题。要求专业、准确、有深度。"
    result = call_mimo(system_prompt, user_prompt, max_tokens=6000)
    if not result:
        return None

    clean = result.strip()
    clean = re.sub(r'^```\w*\s*', '', clean)
    clean = re.sub(r'\s*```\s*$', '', clean)
    clean = clean.strip()

    js = clean.find("{")
    je = clean.rfind("}") + 1
    if js >= 0 and je > js:
        try:
            data = json.loads(clean[js:je])
            # 验证必要字段
            required = ["article", "quiz"]
            for field in required:
                if field not in data:
                    print(f"❌ 缺少必要字段: {field}")
                    return None
            art_required = ["title", "content", "summary", "category", "tags", "difficulty"]
            for field in art_required:
                if field not in data["article"]:
                    print(f"❌ 文章缺少字段: {field}")
                    return None
            if len(data.get("quiz", [])) < 3:
                print(f"❌ 测验题不足3道")
                return None
            # 确保选项格式正确
            for q in data["quiz"]:
                if "options" not in q or len(q["options"]) != 4:
                    print(f"❌ 测验题选项必须是4个")
                    return None
                if "correctIndex" not in q or not isinstance(q["correctIndex"], int):
                    print(f"❌ 测验题答案格式错误")
                    return None
            return data
        except Exception as e:
            print(f"❌ JSON解析失败: {e}")
            print(clean[:500])
            return None
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="daily-autotech.json", help="输出路径")
    args = parser.parse_args()

    print(f"🔧 生成 {datetime.now(BJ_TZ).strftime('%Y-%m-%d')} 汽车技术知识文章（MiMo Pro）...")
    content = generate_article()
    if content:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(content, f, ensure_ascii=False, indent=2)
        print(f"✅ 已写入: {args.output}")
        print(f"   标题: {content['article']['title']}")
        print(f"   分类: {content['article']['category']} | 难度: {content['article']['difficulty']}/5")
        print(f"   测验: {len(content['quiz'])} 道")
    else:
        print("❌ 生成失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
