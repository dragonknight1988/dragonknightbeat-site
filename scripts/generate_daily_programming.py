#!/usr/bin/env python3
"""
每日编程学习 JSON 生成器 (MiMo Pro)
用法: python3 generate_daily_programming.py [--output 路径] [--topic "Swift/React/Python"]
"""

import json, os, sys, subprocess, argparse, requests, re
from datetime import datetime, timezone, timedelta

# 北京时区
BJ_TZ = timezone(timedelta(hours=8))


MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "tp-c6irsm5360gu18hd64hlmz47ltg54c5rbszghj45t5z96c31")
MIMO_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
MIMO_MODEL = "xiaomi/mimo-v2.5-pro"

TECH_STACKS = [
    "Swift / SwiftUI", "Python", "JavaScript / TypeScript",
    "React / Next.js", "Node.js / Deno", "Go", "Rust",
    "Kotlin", "Flutter / Dart", "Git / DevOps"
]
DIFFICULTIES = ["初级", "中级", "中级", "高级"]


def call_mimo(system_prompt, user_prompt, max_tokens=6000):
    headers = {
        "Authorization": f"Bearer {MIMO_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MIMO_MODEL,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        "max_tokens": max_tokens, "temperature": 0.8
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


def generate_programming_content(user_topic=None):
    today = datetime.now(BJ_TZ).strftime("%Y-%m-%d")
    day_of_year = datetime.now().timetuple().tm_yday
    chosen_tech = user_topic or TECH_STACKS[day_of_year % len(TECH_STACKS)]
    difficulty = DIFFICULTIES[day_of_year % len(DIFFICULTIES)]

    system_prompt = f"""你是一位经验丰富的编程导师。请生成一份高质量的每日编程学习内容。
    专注技术栈：{chosen_tech}
    难度级别：{difficulty}

输出格式必须为 JSON，严格符合以下结构（不要输出任何其他内容）：
{{
  "date": "{today}",
  "contents": [
    {{
      "id": "prog-{today}",
      "date": "{today}",
      "title": "技术主题标题",
      "summary": "一句话概括今天要学什么",
      "difficulty": "{difficulty}",
      "concept": "核心概念详解（3-6段，深入浅出）",
      "codeExample": {{
        "language": "编程语言名",
        "code": "可运行的示例代码（包含注释）",
        "explanation": "代码逐行或分块解释"
      }},
      "keyPoints": ["要点1", "要点2", "要点3", "要点4", "要点5"],
      "exercise": {{
        "description": "一道可以动手实践的小练习",
        "hint": "解题思路提示",
        "challenges": [
          {{
            "id": "ch-1", "type": "fillBlank",
            "question": "填空题目描述", "codeContext": "上下文的代码片段（可选）",
            "segments": [
              {{"type": "text", "content": "代码文字段", "placeholder": null, "options": null, "correctAnswer": null}},
              {{"type": "blank", "content": null, "placeholder": "[选择]", "options": ["选项A", "选项B", "选项C"], "correctAnswer": "正确答案"}}
            ], "options": null, "correctAnswer": "正确答案", "explanation": "解析"
          }},
          {{
            "id": "ch-2", "type": "multipleChoice",
            "question": "选择题题目", "codeContext": "相关代码片段（可选）",
            "segments": null, "options": ["选项1", "选项2", "选项3", "选项4"],
            "correctAnswer": "正确选项文字", "explanation": "解析说明"
          }},
          {{
            "id": "ch-3", "type": "codePrediction",
            "question": "这段代码输出什么？", "codeContext": "示例代码",
            "segments": null, "options": ["输出结果1", "输出结果2", "输出结果3"],
            "correctAnswer": "正确答案", "explanation": "解析"
          }}
        ]
      }}
    }}
  ]
}}

要求：
- concept 要有深度，包含实际工程经验
- code 代码要可直接运行，包含注释
- difficulty="初级" 时讲基础概念和简单例子；"中级"讲实际应用；"高级"讲性能优化/架构设计
- 每个 topic 要有实用价值，能直接用在工作中"""

    print(f"💻 技术栈: {chosen_tech} | 难度: {difficulty}")
    result = call_mimo(
        system_prompt,
        f"请生成以【{chosen_tech}】为主题、难度为「{difficulty}」的今日编程学习内容，日期：{today}",
        max_tokens=6000
    )
    if not result:
        return None

    clean = result.strip()
    clean = re.sub(r'^```\w*\s*', '', clean)
    clean = re.sub(r'\s*```\s*$', '', clean)
    clean = clean.strip()

    js = clean.find("{")
    je = clean.rfind("}") + 1
    if js >= 0 and je > js:
        data = repair_json(clean[js:je])
        if data:
            return data
        print(f"❌ JSON 解析失败，输出前500字: {result[:500]}")
        return None
    return None


def repair_json(text):
    """尝试修复 AI 生成的不规范 JSON"""
    import re
    try:
        # 第1轮：严格解析
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            # 第2轮：允许控制字符
            return json.loads(text, strict=False)
        except json.JSONDecodeError:
            try:
                # 第3轮：清理常见问题
                fixed = text
                # 移除尾随逗号（, ] → ] / , } → }）
                fixed = re.sub(r',\s*\]', ']', fixed)
                fixed = re.sub(r',\s*\}', '}', fixed)
                # 修复非法控制字符（ASCII 0-31 除了 \t \n \r）
                fixed = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', fixed)
                return json.loads(fixed, strict=False)
            except json.JSONDecodeError:
                return None



def main():
    parser = argparse.ArgumentParser(description="生成每日编程学习 JSON")
    parser.add_argument("--output", default="daily-programming.json",
                        help="输出文件路径（默认 daily-programming.json）")
    parser.add_argument("--topic", default=None, help="指定技术栈")
    args = parser.parse_args()

    _today = datetime.now(BJ_TZ).strftime("%Y-%m-%d"); print(f"💻 生成 {_today} 编程学习内容（MiMo Pro）...")

    content = generate_programming_content(args.topic)
    if content:
        # 强制修正日期为今天，防止AI返回错误日期
        _today = datetime.now(BJ_TZ).strftime("%Y-%m-%d")
        if content.get("date") != _today:
            print(f"⚠️ AI返回日期 {content.get('date')}，修正为 {_today}")
            content["date"] = _today
        for c in content.get("contents", []):
            if c.get("date") != _today:
                c["date"] = _today
            if c.get("id") and not c["id"].endswith(_today):
                c["id"] = f"prog-{_today}"
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(content, f, ensure_ascii=False, indent=2)
        print(f"✅ 已写入: {args.output}")
        topic = content.get("contents", [{}])[0].get("title", "")
        diff = content.get("contents", [{}])[0].get("difficulty", "")
        print(f"   主题: {topic} | 难度: {diff}")
    else:
        print("❌ 生成失败")
        sys.exit(1)


if __name__ == "__main__":
    main()

