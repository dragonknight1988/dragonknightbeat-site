#!/usr/bin/env python3
"""
每日新闻晨报 JSON 生成器（增强版 v3）
用法: python3 generate_daily_news.py [--output 输出路径]

功能：
1. 从百度热搜 API + Bing 新闻抓取实时新闻标题
2. 将真实新闻标题作为 context 喂给 AI
3. AI 基于实时新闻生成每日晨报 JSON

适配 ECS crontab 运行，API Key 从 .env 环境变量读取。
"""

import json, os, sys, argparse, time, requests, re, urllib.parse
from datetime import datetime, timezone, timedelta

BJ_TZ = timezone(timedelta(hours=8))

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = "deepseek-v4-flash"

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# ========== API 调用 ==========

def call_deepseek(system_prompt, user_prompt, max_tokens=8192):
    if not DEEPSEEK_API_KEY:
        print("ERROR: DEEPSEEK_API_KEY not set")
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
        "temperature": 0.7
    }
    try:
        resp = requests.post(f"{DEEPSEEK_BASE_URL}/chat/completions",
                             headers=headers, json=payload, timeout=300)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        print(f"API raw output: {len(content)} chars")
        usage = data.get("usage", {})
        if usage:
            print(f"Tokens: in {usage.get('prompt_tokens','?')} | out {usage.get('completion_tokens','?')} | total {usage.get('total_tokens','?')}")
        return content
    except Exception as e:
        print(f"API call failed: {e}")
        return None


# ========== 新闻抓取 ==========

def fetch_baidu_hot():
    """从百度热搜API获取实时热点（最可靠）"""
    print("Fetching Baidu Hot Search...")
    results = []
    try:
        r = requests.get(
            "https://top.baidu.com/api/board?tab=realtime",
            headers={"User-Agent": USER_AGENT, "Accept": "application/json",
                     "Referer": "https://top.baidu.com/"},
            timeout=10
        )
        data = r.json()
        cards = data.get("data", {}).get("cards", [])
        if cards:
            for item in cards[0].get("content", []):
                title = item.get("word", "") or item.get("query", "")
                hot = item.get("hotScore", "")
                if title:
                    results.append(f"[{hot}] {title}")
        print(f"  Got {len(results)} Baidu hot topics")
        return results
    except Exception as e:
        print(f"  Baidu API error: {e}")
        return results


def fetch_bing_news(max_items=15):
    """从必应新闻抓取补充"""
    print("Fetching Bing News...")
    results = {}
    try:
        r = requests.get(
            "https://cn.bing.com/news/search?q=%E8%A6%81%E9%97%BB&setlang=zh-Hans-CN",
            headers={"User-Agent": USER_AGENT}, timeout=10
        )
        r.encoding = "utf-8"
        titles = re.findall(r'<a[^>]*class="title"[^>]*>(.*?)</a>', r.text, re.DOTALL)
        for t in titles:
            t2 = re.sub(r'<[^>]+>', '', t).strip()
            if t2 and len(t2) > 6:
                results[t2] = True
    except Exception as e:
        print(f"  Bing error: {e}")

    print(f"  Got {len(results)} Bing headlines")
    return list(results.keys())[:max_items]


def fetch_news_headlines():
    """聚合所有新闻源，返回纯文本"""
    all_news = []
    all_news.extend(fetch_baidu_hot())
    all_news.extend(fetch_bing_news())

    seen = set()
    unique = []
    for t in all_news:
        t_clean = re.sub(r'\s+', ' ', t).strip()
        if t_clean not in seen and len(t_clean) > 4:
            seen.add(t_clean)
            unique.append(t_clean[:80])

    print(f"\nTotal {len(unique)} real news headlines collected")
    if unique:
        print(f"First: {unique[0][:50]}...")

    context_lines = [
        "以下是从互联网实时抓取到的今日新闻标题（请参考使用）：",
    ]
    for i, t in enumerate(unique, 1):
        context_lines.append(f"{i}. {t}")
    context_lines.append(f"抓取时间: {datetime.now(BJ_TZ).strftime('%Y-%m-%d %H:%M')} 北京时间")
    return "\n".join(context_lines)


# ========== 生成主体 ==========

def build_news_content():
    today = datetime.now(BJ_TZ).strftime("%Y-%m-%d")
    news_context = fetch_news_headlines()

    system_prompt = f"""你是一个专业的新闻编辑。以下是今日实时抓取到的新闻标题：

{news_context}

请基于以上实时新闻（结合你自己的知识补充细节），生成 {today} 的新闻简报JSON。

要求：
- 5个分类，每类3-5条新闻
- 每条新闻包含标题和1-2句摘要
- **必须基于真实新闻**，不要编造不存在的事件
- 重大事件（航天、科技、政治、财经）必须优先收录
- 语言客观简洁
- 直接输出JSON，不要markdown代码块

JSON结构：
{{
  "date": "{today}",
  "sections": [
    {{
      "id": "domestic",
      "title": "国内时政",
      "icon": "🇨🇳",
      "articles": [
        {{"id": "news-001", "title": "...", "summary": "..."}}
      ]
    }}
  ]
}}

分类ID：domestic(国内时政), international(国际时政), finance(财经动态), tech(科技前沿), other(其他要闻)
注意：id需全局唯一，articles不能为空"""

    user_prompt = f"今天是{today}。请基于实时新闻数据生成新闻简报JSON。确保包含今天所有重大新闻事件。不要截断输出。"

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        print(f"\nAPI call {attempt}/{max_retries}...")
        result = call_deepseek(system_prompt, user_prompt, max_tokens=8192)
        if not result:
            print("Empty, retrying...")
            continue

        clean = result.strip()
        if clean.startswith("```json"): clean = clean[7:]
        elif clean.startswith("```"): clean = clean[3:]
        if clean.endswith("```"): clean = clean[:-3]
        clean = clean.strip()

        js = clean.find("{")
        je = clean.rfind("}") + 1
        if js >= 0 and je > js:
            try:
                data = json.loads(clean[js:je])
                data["date"] = today
                sections = data.get("sections", [])
                total = sum(len(s.get("articles", [])) for s in sections)
                if total == 0 or len(sections) < 3:
                    print(f"Incomplete ({total} articles / {len(sections)} cats), retry...")
                    time.sleep(2)
                    continue
                print(f"OK: {total} articles / {len(sections)} categories")
                return data
            except json.JSONDecodeError as e:
                print(f"JSON error: {e}")
                if attempt < 3:
                    time.sleep(2)
                continue
        else:
            print("No JSON found")
            if attempt < 3:
                time.sleep(2)
            continue

    print("All retries failed")
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="daily-news.json")
    args = parser.parse_args()

    ts = datetime.now(BJ_TZ).strftime('%Y-%m-%d')
    print(f"Generating {ts} daily news (DeepSeek V4 + real news API)...")
    print(f"API Key: {'SET' if DEEPSEEK_API_KEY else 'NOT SET'}")

    content = build_news_content()
    if content:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(content, f, ensure_ascii=False, indent=2)
        secs = content.get("sections", [])
        total = sum(len(s.get("articles", [])) for s in secs)
        print(f"Written: {args.output}")
        print(f"{total} articles, {len(secs)} categories")
        for s in secs:
            print(f"  {s.get('icon','')} {s.get('title','')}: {len(s.get('articles',[]))}")
    else:
        print("FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
