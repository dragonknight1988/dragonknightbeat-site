#!/usr/bin/env python3
"""
每日英语晨读 JSON 生成器
用法: python3 generate_daily_english.py [--output 输出路径] [--topic 主题]
默认输出到当前目录的 daily-english.json

适配 GitHub Actions 运行，API Key 从环境变量读取。
"""

import json, os, sys, argparse, requests
from datetime import datetime

# DeepSeek API 配置（API Key 从环境变量读取）
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = "deepseek-v4-flash"

TOPIC_MAP = {
    "1": "人工智能与科技",
    "2": "商业与金融",
    "3": "职场与沟通",
    "4": "文化与旅行",
    "5": "健康与生活",
    "6": "环境与可持续发展",
    "7": "教育与成长",
}


def call_deepseek(system_prompt, user_prompt, max_tokens=5000):
    """调用 DeepSeek API 生成内容"""
    if not DEEPSEEK_API_KEY:
        print("❌ 未设置 DEEPSEEK_API_KEY 环境变量")
        return None

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "max_tokens": max_tokens,
        "temperature": 0.8
    }

    try:
        resp = requests.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=300
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        if usage:
            print(f"📊 Token: 输入 {usage.get('prompt_tokens', '?')} | 输出 {usage.get('completion_tokens', '?')}")
        return content
    except Exception as e:
        print(f"❌ API 调用失败: {e}")
        return None


def generate_english_content(topic=None):
    """用 AI 生成当日英语学习内容"""
    today = datetime.now().strftime("%Y-%m-%d")

    # 轮换主题
    day_of_year = datetime.now().timetuple().tm_yday
    chosen_topic = topic or TOPIC_MAP.get(str((day_of_year % 7) + 1), "科技与创新")

    system_prompt = f"""你是一个专业的英语教育内容创作者。请生成一份高质量的每日英语学习内容。

输出格式为 JSON，严格符合以下结构（不要输出任何其他内容）：
{{
  "date": "{today}",
  "content": {{
    "id": "en-{today}",
    "date": "{today}",
    "topic": "{chosen_topic}",
    "quote": {{
      "quote": "英语励志名言原文",
      "author": "作者名",
      "translation": "中文翻译",
      "explanation": "这句话的含义和使用场景解释"
    }},
    "vocabulary": [
      {{
        "word": "单词",
        "phonetic": "/音标/",
        "partOfSpeech": "词性",
        "definition": "中文释义",
        "example": "英文例句",
        "translation": "例句中文翻译"
      }}
    ],
    "pattern": {{
      "pattern": "核心句型模板",
      "example": "句型例句",
      "translation": "中文翻译",
      "usage": "使用说明"
    }},
    "grammar": {{
      "title": "语法点名称",
      "explanation": "语法点解释",
      "examples": ["例1", "例2"]
    }},
    "pronunciation": {{
      "word": "发音练习单词",
      "phonetic": "/音标/",
      "tips": "发音技巧提示"
    }},
    "reading": {{
      "title": "阅读文章标题",
      "content": "英文文章正文（100-150词），围绕 {chosen_topic} 主题",
      "translation": "中文翻译"
    }}
  }}
}}

要求：
- vocabulary 包含 10 个单词，难度中等（大学英语/职场英语水平）
- 单词需标注准确的音标
- 例句要实用，体现单词在真实场景中的用法
- grammar 要讲解一个实用的语法点
- reading 文章要有深度，读完能学到新知识"""

    print(f"📖 主题: {chosen_topic}")
    result = call_deepseek(
        system_prompt,
        f"请生成以「{chosen_topic}」为主题的英语学习内容，日期：{today}",
        max_tokens=5000
    )
    if not result:
        return None

    json_start = result.find("{")
    json_end = result.rfind("}") + 1
    if json_start >= 0 and json_end > json_start:
        json_str = result[json_start:json_end]
        try:
            data = json.loads(json_str)
            return data
        except json.JSONDecodeError as e:
            print(f"❌ JSON 解析失败: {e}")
            print(f"原始输出前800字: {result[:800]}")
            return None
    return None


def main():
    parser = argparse.ArgumentParser(description="生成每日英语晨读 JSON")
    parser.add_argument("--output", default="daily-english.json",
                        help="输出文件路径（默认 daily-english.json）")
    parser.add_argument("--topic", default=None, help="指定主题")
    args = parser.parse_args()

    print(f"📖 生成 {datetime.now().strftime('%Y-%m-%d')} 英语晨读（DeepSeek）...")
    print(f"🔑 API Key: {'已设置' if DEEPSEEK_API_KEY else '未设置'}")

    content = generate_english_content(args.topic)
    if content:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(content, f, ensure_ascii=False, indent=2)
        print(f"✅ 已写入: {args.output}")
        vocab_count = len(content.get("content", {}).get("vocabulary", []))
        print(f"   词汇: {vocab_count} 个 | 主题: {content.get('content', {}).get('topic', '')}")
    else:
        print("❌ 生成失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
