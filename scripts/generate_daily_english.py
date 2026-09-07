#!/usr/bin/env python3
"""
每日英语晨读 JSON 生成器 v2
新增：从 ChinaDaily / CGTN 抓取真实新闻素材
用法: python3 generate_daily_english.py [--output 输出路径] [--topic 主题]
"""

import json, os, sys, argparse, re, requests
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser

BJ_TZ = timezone(timedelta(hours=8))

MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "tp-c6irsm5360gu18hd64hlmz47ltg54c5rbszghj45t5z96c31")
MIMO_BASE_URL = os.environ.get("MIMO_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1")
MIMO_MODEL = "xiaomi/mimo-v2.5"

TOPIC_MAP = {
    "1": "人工智能与科技",
    "2": "商业与金融",
    "3": "职场与沟通",
    "4": "文化与旅行",
    "5": "健康与生活",
    "6": "环境与可持续发展",
    "7": "教育与成长",
}

# ========== 新闻抓取 ==========

def strip_tags(html_str):
    return re.sub(r'<[^>]+>', '', html_str or '').strip()

def fetch_chinadaily_news():
    """从 ChinaDaily 抓取新闻"""
    news_list = []
    pages = [
        "https://www.chinadaily.com.cn/",
        "https://www.chinadaily.com.cn/china/",
        "https://www.chinadaily.com.cn/world/",
        "https://www.chinadaily.com.cn/business/",
        "https://www.chinadaily.com.cn/tech/",
    ]
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    
    a_pattern = r'<a\s[^>]*?href=["\']([^"\']+)["\'][^>]*?>([\s\S]*?)</a>'
    
    for url in pages:
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.encoding = 'utf-8'
            matches = re.findall(a_pattern, resp.text)
            for link, inner in matches:
                text = strip_tags(inner)
                text = re.sub(r'\s+', ' ', text).strip()
                # 只要新闻标题：长度合理、排除导航/广告
                if len(text) > 15 and len(text) < 120:
                    if any(skip in text.lower() for skip in ['photo', 'video', 'gallery', 'advertisement', 'subscribe']):
                        continue
                    # 补全链接
                    if link.startswith('//'):
                        link = 'https:' + link
                    elif link.startswith('/'):
                        link = 'https://www.chinadaily.com.cn' + link
                    # 只要 chinadaily 的文章链接
                    if 'chinadaily.com.cn' in link and '/a/' in link:
                        news_list.append({"title": text, "source": "ChinaDaily", "url": link})
        except Exception as e:
            print(f"⚠️ ChinaDaily 抓取失败 ({url}): {e}")
    
    # 去重
    seen = set()
    unique = []
    for n in news_list:
        if n['title'] not in seen:
            seen.add(n['title'])
            unique.append(n)
    return unique[:10]

def fetch_cgtn_news():
    """从 CGTN 抓取新闻"""
    news_list = []
    pages = [
        "https://www.cgtn.com/",
        "https://news.cgtn.com/",
    ]
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    
    a_pattern = r'<a\s[^>]*?href=["\']([^"\']+)["\'][^>]*?>([\s\S]*?)</a>'
    skip_words = ['shqip', 'arabic', 'belarusian', 'bengali', 'bulgarian', 'croatian', 'czech',
                  'esperanto', 'filipino', 'french', 'german', 'greek', 'hausa', 'hindi',
                  'indonesian', 'japanese', 'kazakh', 'khmer', 'korean', 'kyrgyz', 'lao',
                  'malay', 'mongolian', 'myanmar', 'nepali', 'pashto', 'persian', 'polish',
                  'portuguese', 'romanian', 'russian', 'serbian', 'sinhala', 'spanish',
                  'swahili', 'tajik', 'tamil', 'thai', 'turkish', 'ukrainian', 'urdu',
                  'uzbek', 'vietnamese', 'live', 'schedule', 'channel', 'program']
    
    for url in pages:
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.encoding = 'utf-8'
            matches = re.findall(a_pattern, resp.text)
            for link, inner in matches:
                text = strip_tags(inner)
                text = re.sub(r'\s+', ' ', text).strip()
                if len(text) > 20 and len(text) < 150:
                    if any(skip in text.lower() for skip in skip_words):
                        continue
                    if link.startswith('//'):
                        link = 'https:' + link
                    if 'cgtn.com/news/' in link or 'cgtn.com/special/' in link:
                        news_list.append({"title": text, "source": "CGTN", "url": link})
        except Exception as e:
            print(f"⚠️ CGTN 抓取失败 ({url}): {e}")
    
    seen = set()
    unique = []
    for n in news_list:
        if n['title'] not in seen:
            seen.add(n['title'])
            unique.append(n)
    return unique[:10]

def fetch_all_news():
    """汇总所有新闻源"""
    print("📰 正在抓取最新英文新闻...")
    
    cd_news = fetch_chinadaily_news()
    print(f"   ChinaDaily: {len(cd_news)} 条")
    
    cgtn_news = fetch_cgtn_news()
    print(f"   CGTN: {len(cgtn_news)} 条")
    
    all_news = cd_news + cgtn_news
    
    # 按日期排序（新链接包含日期），取最新的
    all_news.sort(key=lambda x: x.get('url', ''), reverse=True)
    
    print(f"   📊 合计: {len(all_news)} 条")
    return all_news[:15]

# ========== AI 内容生成 ==========

def call_mimo(system_prompt, user_prompt, max_tokens=5000):
    if not MIMO_API_KEY:
        print("❌ 未设置 MIMO_API_KEY")
        return None
    headers = {"Authorization": f"Bearer {MIMO_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": MIMO_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "max_tokens": max_tokens,
        "temperature": 0.7
    }
    try:
        resp = requests.post(f"{MIMO_BASE_URL}/chat/completions", headers=headers, json=payload, timeout=(15, 300))
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

def fetch_article_snippet(url, max_chars=400):
    """抓取文章正文摘要"""
    if not url:
        return ""
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = 'utf-8'
        # 提取正文段落
        paragraphs = re.findall(r'<p[^>]*>([\s\S]*?)</p>', resp.text)
        text_parts = []
        for p in paragraphs:
            clean = strip_tags(p).strip()
            if len(clean) > 30:
                text_parts.append(clean)
        full_text = ' '.join(text_parts)
        return full_text[:max_chars]
    except:
        return ""

def generate_english_content(news_list, topic=None):
    """基于真实新闻生成英语学习内容"""
    today = datetime.now(BJ_TZ).strftime("%Y-%m-%d")
    day_of_year = datetime.now().timetuple().tm_yday
    chosen_topic = topic or TOPIC_MAP.get(str((day_of_year % 7) + 1), "科技与创新")

    # 构建新闻素材
    news_context = ""
    if news_list:
        news_context = "\n\n【今日真实新闻素材】\n"
        for i, n in enumerate(news_list[:15], 1):
            news_context += f"{i}. [{n['source']}] {n['title']}\n"
    
    # 抓取前3条正文
    snippets = []
    for n in news_list[:3]:
        s = fetch_article_snippet(n['url'], 300)
        if s and len(s) > 50:
            snippets.append(f"[{n['source']}] {n['title']}: {s[:200]}")
    if snippets:
        news_context += "\n【新闻正文摘要】\n"
        for s in snippets:
            news_context += f"- {s}\n"

    system_prompt = f"""你是一个专业的英语教育内容创作者。请基于今日真实新闻素材，生成一份高质量的每日英语学习内容。

输出格式为 JSON，严格符合以下结构（不要输出任何其他内容）：
{{
  "date": "{today}",
  "content": {{
    "id": "en-{today}",
    "date": "{today}",
    "topic": "{chosen_topic}",
    "newsHighlights": [
      {{
        "title": "新闻标题（英文）",
        "source": "来源",
        "summary": "一句话英文摘要",
        "translation": "中文翻译",
        "keyWords": ["关键词1", "关键词2"]
      }}
    ],
    "quote": {{
      "quote": "与今日新闻或主题相关的英语名言",
      "author": "作者名",
      "translation": "中文翻译",
      "explanation": "含义解释"
    }},
    "vocabulary": [
      {{
        "word": "单词",
        "phonetic": "/音标/",
        "partOfSpeech": "词性",
        "definition": "中文释义",
        "example": "来自今日新闻或与新闻相关的英文例句",
        "translation": "中文翻译",
        "newsContext": "该词在今日新闻中的出处"
      }}
    ],
    "pattern": {{
      "pattern": "从新闻中提炼的核心句型",
      "example": "句型例句（来自新闻）",
      "translation": "中文翻译",
      "usage": "使用说明"
    }},
    "grammar": {{
      "title": "从新闻中提炼的语法点",
      "explanation": "语法解释",
      "examples": ["来自新闻的例句1", "来自新闻的例句2"]
    }},
    "pronunciation": {{
      "word": "发音练习单词（来自新闻高频词）",
      "phonetic": "/音标/",
      "tips": "发音技巧",
      "examples": ["例句1", "例句2"]
    }},
    "reading": {{
      "title": "阅读文章标题",
      "content": "基于今日新闻改写的英文文章（120-180词）",
      "translation": "中文翻译",
      "sourceNote": "素材来源说明"
    }}
  }}
}}

要求：
1. vocabulary 的 10 个单词必须来自或关联今日新闻
2. 每个 vocabulary 都需要 newsContext 字段
3. reading 文章必须基于今日真实新闻改写
4. newsHighlights 选取 3-5 条最有学习价值的新闻
5. 所有音标必须准确"""

    print(f"📖 主题: {chosen_topic}")
    user_prompt = f"请基于以下今日新闻素材，生成以「{chosen_topic}」为主题的英语学习内容，日期：{today}\n{news_context}"
    
    result = call_mimo(system_prompt, user_prompt, max_tokens=6000)
    if not result:
        return None

    json_start = result.find("{")
    json_end = result.rfind("}") + 1
    if json_start >= 0 and json_end > json_start:
        json_str = result[json_start:json_end]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"❌ JSON 解析失败: {e}")
            print(f"原始输出前800字: {result[:800]}")
            return None
    return None

def main():
    parser = argparse.ArgumentParser(description="生成每日英语晨读 JSON v2")
    parser.add_argument("--output", default="daily-english.json", help="输出文件路径")
    parser.add_argument("--topic", default=None, help="指定主题")
    parser.add_argument("--no-news", action="store_true", help="跳过新闻抓取")
    args = parser.parse_args()

    today = datetime.now(BJ_TZ).strftime("%Y-%m-%d")
    print(f"📖 生成 {today} 英语晨读 v2（新闻驱动）...")

    news_list = []
    if not args.no_news:
        try:
            news_list = fetch_all_news()
        except Exception as e:
            print(f"⚠️ 新闻抓取异常: {e}")
    
    if not news_list:
        print("⚠️ 未获取到新闻，将使用纯 AI 生成模式")

    content = generate_english_content(news_list, args.topic)
    if content:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(content, f, ensure_ascii=False, indent=2)
        print(f"✅ 已写入: {args.output}")
        vocab_count = len(content.get("content", {}).get("vocabulary", []))
        news_count = len(content.get("content", {}).get("newsHighlights", []))
        print(f"   词汇: {vocab_count} 个 | 新闻: {news_count} 条 | 主题: {content.get('content', {}).get('topic', '')}")
    else:
        print("❌ 生成失败")
        sys.exit(1)

if __name__ == "__main__":
    main()
