#!/usr/bin/env python3
"""
每日德语 JSON 生成器
用法: python3 generate_daily_german.py [--output 输出路径]
"""

import json, os, sys, argparse, requests
from datetime import datetime, timezone, timedelta

BJ_TZ = timezone(timedelta(hours=8))

MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "tp-c6irsm5360gu18hd64hlmz47ltg54c5rbszghj45t5z96c31")
MIMO_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
MIMO_MODEL = "xiaomi/mimo-v2.5-pro"

TOPICS = [
    "日常问候与自我介绍", "在咖啡馆点餐", "问路与交通", "购物与讨价还价",
    "在医院看病", "酒店入住与退房", "德国美食与烹饪", "节日与传统",
    "工作与面试", "租房与搬家", "天气与季节", "爱好与运动",
    "在邮局和银行", "德国教育体系", "环保与可持续发展", "德国汽车文化",
    "音乐与艺术", "德国历史人物", "科技与创新", "德国大学生活",
    "在超市购物", "德国公共交通", "德国职场文化", "德国家庭生活",
    "德国啤酒文化", "圣诞市场", "黑森林与旅游", "德国哲学",
    "足球与体育", "德国文学",
]

SYSTEM_PROMPT = """你是一个德语教学内容生成器。请严格按照以下JSON格式生成每日德语学习内容。

要求：
1. 所有内容必须准确，德语语法正确
2. 适合初中级德语学习者（A2-B1水平）
3. 单词必须标注词性（der/die/das）和复数形式
4. 例句要实用、贴近生活
5. 句型（pattern）的例句必须融入当日词汇表中的至少2个单词，让词汇在实用语境中得到复习
6. 包含一个德国文化小知识
6. 中文翻译要自然通顺

输出格式（严格JSON，不要添加任何markdown标记）：
{
  "id": "daily-german-YYYY-MM-DD",
  "date": "YYYY-MM-DD",
  "topic": "主题名称",
  "quote": {
    "quote": "德语名言",
    "author": "作者",
    "translation": "中文翻译",
    "explanation": "解读"
  },
  "vocabulary": [
    {
      "word": "德语单词",
      "article": "der/die/das",
      "plural": "复数形式（如无复数填'-'）",
      "phonetic": "发音（IPA或近似音）",
      "partOfSpeech": "词性",
      "definition": "中文释义",
      "example": "德语例句",
      "exampleTranslation": "例句中文翻译"
    }
  ],
  "pattern": {
    "pattern": "常用句型",
    "example": "例句",
    "translation": "翻译",
    "usage": "用法说明"
  },
  "grammar": {
    "title": "语法点标题",
    "explanation": "详细解释",
    "examples": ["例句1", "例句2", "例句3"]
  },
  "pronunciation": {
    "word": "发音重点词",
    "phonetic": "音标",
    "tips": "发音技巧",
    "examples": ["例词1", "例词2", "例词3"]
  },
  "reading": {
    "title": "短文标题",
    "content": "德语短文（80-120词）",
    "translation": "中文翻译"
  },
  "culture": {
    "title": "文化知识标题",
    "content": "文化知识内容（中文）"
  }
}"""

USER_PROMPT_TEMPLATE = """请生成今天的每日德语学习内容。主题：{topic}

要求：
- 10个常用单词（含词性der/die/das、复数、发音、例句）
- 1个常用句型（含用法说明）。**重要：句型的例句中必须使用上面10个词汇中的至少2个单词**，让词汇在句型语境中得到复习巩固
- 1个语法点（含3个例句）
- 1个发音重点（含技巧和3个例词）
- 1篇德语短文（80-120词，含中文翻译）
- 1个德国文化小知识
- 1句德语名言（含作者和解读）

请直接输出JSON，不要添加任何markdown标记。"""


def call_mimo(system_prompt, user_prompt, max_tokens=8192):
    headers = {"Authorization": f"Bearer {MIMO_API_KEY}", "Content-Type": "application/json"}
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
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"❌ API 调用失败: {e}")
        return None


def generate_daily_german(topic=None):
    today = datetime.now(BJ_TZ).strftime("%Y-%m-%d")
    day_idx = int(today.split("-")[2]) % len(TOPICS)
    selected_topic = topic or TOPICS[day_idx]

    print(f"🇩🇪 生成 {today} 德语学习内容（MiMo Pro）...")
    print(f"📖 主题: {selected_topic}")

    user_prompt = USER_PROMPT_TEMPLATE.format(topic=selected_topic)
    result = call_mimo(SYSTEM_PROMPT, user_prompt)

    if not result:
        return None

    # 清理可能的markdown标记
    clean = result.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
    if clean.endswith("```"):
        clean = clean[:-3]
    clean = clean.strip()

    # Auto-fix truncated JSON
    open_braces = clean.count(chr(123)) - clean.count(chr(125))
    open_brackets = clean.count(chr(91)) - clean.count(chr(93))
    if open_braces > 0 or open_brackets > 0:
        lines_list = clean.rstrip().rsplit(chr(10), 1)
        if len(lines_list) > 1:
            clean = lines_list[0]
        clean = clean.rstrip().rstrip(chr(44)) + chr(93) * open_brackets + chr(125) * open_braces
        print("JSON truncated, auto-fixed:" + str(open_braces) + " braces, " + str(open_brackets) + " brackets")


    try:
        content = json.loads(clean)
        # 包装成标准格式
        output = {"date": today, "content": content}
        print(f"✅ 生成成功！主题: {content.get('topic', 'N/A')}")
        return output
    except json.JSONDecodeError as e:
        print(f"❌ JSON解析失败: {e}")
        print(f"原始内容前200字: {result[:200]}")
        return None


def main():
    parser = argparse.ArgumentParser(description="每日德语生成器")
    parser.add_argument("--output", "-o", help="输出JSON文件路径")
    parser.add_argument("--topic", "-t", help="指定主题")
    args = parser.parse_args()

    output = generate_daily_german(args.topic)
    if not output:
        sys.exit(1)

    output_path = args.output or "/var/www/dragonknightbeat.com/daily-german.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"📁 已写入: {output_path}")
    print(f"📊 内容大小: {len(json.dumps(output, ensure_ascii=False))} 字符")


if __name__ == "__main__":
    main()
