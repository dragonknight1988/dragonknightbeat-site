#!/usr/bin/env python3
"""每日英语晨读 JSON 生成器 — GitHub Actions 版"""
import json, os, sys, requests
from datetime import datetime, timezone, timedelta

BJ_TZ = timezone(timedelta(hours=8))
today = datetime.now(BJ_TZ).strftime("%Y-%m-%d")
OUTPUT = os.environ.get("OUTPUT_DIR", ".") + "/daily-english.json"

API_KEY = os.environ.get("DEEPSEEK_API_KEY")
BASE_URL = "https://api.deepseek.com/v1"
MODEL = "deepseek-chat"

TOPIC_MAP = {
    "1": "人工智能与科技", "2": "商业与金融", "3": "职场与沟通",
    "4": "文化与旅行", "5": "健康与生活", "6": "环境与可持续发展",
    "7": "教育与成长",
}

def main():
    if not API_KEY:
        print("❌ 未设置 DEEPSEEK_API_KEY"); sys.exit(1)
    day_of_year = datetime.now().timetuple().tm_yday
    chosen_topic = TOPIC_MAP.get(str((day_of_year % 7) + 1), "科技与创新")
    print(f"📖 主题: {chosen_topic}")

    system_prompt = f"""你是一个专业的英语教育内容创作者。请生成一份高质量的每日英语学习内容。

输出格式为 JSON，严格符合以下结构（不要输出任何其他内容）：
{{
  "date": "{today}",
  "content": {{
    "id": "en-{today}",
    "date": "{today}",
    "topic": "{chosen_topic}",
    "quote": {{"quote": "英语名言原文", "author": "作者名", "translation": "中文翻译", "explanation": "解释"}},
    "vocabulary": [
      {{"word": "单词", "phonetic": "/音标/", "partOfSpeech": "词性", "definition": "中文释义", "example": "英文例句", "translation": "中文翻译"}}
    ],
    "pattern": {{"pattern": "核心句型模板", "example": "例句", "translation": "中文翻译", "usage": "使用说明"}},
    "grammar": {{"title": "语法点名称", "explanation": "解释", "examples": ["例1", "例2"]}},
    "pronunciation": {{"word": "练习单词", "phonetic": "/音标/", "tips": "发音技巧"}},
    "reading": {{"title": "阅读文章标题", "content": "英文正文100-150词", "translation": "中文翻译"}}
  }}
}}
要求：
- vocabulary 包含 10 个单词，难度要求：**CET-4起步**，核心在 CET-6/雅思/托业/职场水平
- 严禁初中/高中基础词（good, happy, big, small 等），必须四级及以上学术/职场词汇
- 例句要实用，体现真实商务/科技/学术场景
- grammar 讲解一个实用语法点
- reading 文章要有深度，信息密度高"""

    resp = requests.post(f"{BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={"model": MODEL, "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请生成以「{chosen_topic}」为主题的英语学习内容，日期：{today}"}
        ], "max_tokens": 5000, "temperature": 0.8}, timeout=300)
    resp.raise_for_status()
    result = resp.json()["choices"][0]["message"]["content"]

    json_start = result.find("{")
    json_end = result.rfind("}") + 1
    data = json.loads(result[json_start:json_end])

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    vocab = data.get("content", {}).get("vocabulary", [])
    print(f"✅ {OUTPUT} — {len(vocab)} 词汇")

if __name__ == "__main__":
    main()
