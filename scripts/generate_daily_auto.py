#!/usr/bin/env python3
"""
每日汽车新闻日报 JSON 生成器 (DeepSeek V4 + 热搜)
用法: python3 generate_daily_auto.py [--output 路径]
"""

import json, os, sys, argparse, requests, re, urllib.parse
from datetime import datetime, timezone, timedelta

BJ_TZ = timezone(timedelta(hours=8))

# 默认输出位置（会被 --output 覆盖）
SITE_DIR = os.path.expanduser("~/.openclaw/workspace/dragonknightbeat-site")
JSON_PATH = os.path.join(SITE_DIR, "daily-auto.json")

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-flash"

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def call_deepseek(system_prompt, user_prompt, max_tokens=8000):
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        "max_tokens": max_tokens, "temperature": 0.7
    }
    try:
        resp = requests.post(f"{DEEPSEEK_BASE_URL}/chat/completions", headers=headers, json=payload, timeout=300)
        resp.raise_for_status()
        data = resp.json()
        usage = data.get("usage", {})
        if usage:
            print(f"📊 Token: 输入 {usage.get('prompt_tokens','?')} | 输出 {usage.get('completion_tokens','?')}")
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"❌ API 调用失败: {e}")
        return None


# ======================== 热搜抓取 ========================

def fetch_baidu_hot():
    """从百度热搜API获取实时热点"""
    print("🔥 正在抓取百度热搜...")
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
                if title:
                    results.append(title)
        print(f"  ✅ 获取 {len(results)} 条热搜")
        return results
    except Exception as e:
        print(f"  ⚠️ 百度热搜抓取失败: {e}")
        return results


def fetch_auto_news_from_bing(max_items=15):
    """从必应抓取汽车相关新闻"""
    print("🚗 正在抓取必应汽车新闻...")
    results = []
    try:
        r = requests.get(
            "https://cn.bing.com/news/search?q=%E6%B1%BD%E8%BD%A6+%E6%96%B0%E9%97%BB&setlang=zh-Hans-CN",
            headers={"User-Agent": USER_AGENT}, timeout=10
        )
        r.encoding = "utf-8"
        titles = re.findall(r'<a[^>]*class="title"[^>]*>(.*?)</a>', r.text, re.DOTALL)
        for t in titles:
            t2 = re.sub(r'<[^>]+>', '', t).strip()
            if t2 and len(t2) > 6:
                results.append(t2)
    except Exception as e:
        print(f"  ⚠️ 必应抓取失败: {e}")

    # 再抓一页新能源汽车
    try:
        r2 = requests.get(
            "https://cn.bing.com/news/search?q=%E6%96%B0%E8%83%BD%E6%BA%90%E6%B1%BD%E8%BD%A6&setlang=zh-Hans-CN",
            headers={"User-Agent": USER_AGENT}, timeout=10
        )
        r2.encoding = "utf-8"
        titles2 = re.findall(r'<a[^>]*class="title"[^>]*>(.*?)</a>', r2.text, re.DOTALL)
        for t in titles2:
            t2 = re.sub(r'<[^>]+>', '', t).strip()
            if t2 and len(t2) > 6:
                results.append(t2)
    except Exception as e:
        print(f"  ⚠️ 必应新能源抓取失败: {e}")

    seen = set()
    unique = []
    for t in results:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    print(f"  ✅ 获取 {len(unique)} 条汽车相关新闻")
    return unique[:max_items]


def fetch_auto_context():
    """聚合所有新闻源，返回纯文本上下文"""
    hot = fetch_baidu_hot()
    auto = fetch_auto_news_from_bing()

    # 给AI所有热搜作为参考（它自己会判断哪些是汽车相关）
    context_parts = []

    if hot:
        context_parts.append("【今日百度热搜（实时）】")
        for i, t in enumerate(hot, 1):
            context_parts.append(f"{i}. {t}")

    if auto:
        context_parts.append("")
        context_parts.append("【必应汽车新闻】")
        for i, t in enumerate(auto, 1):
            context_parts.append(f"{i}. {t}")

    if not hot and not auto:
        context_parts.append("（未能获取实时新闻数据，请基于你的知识生成）")

    context_parts.append(f"抓取时间: {datetime.now(BJ_TZ).strftime('%Y-%m-%d %H:%M')} 北京时间")
    result = "\n".join(context_parts)
    print(f"\n📰 共提供 {len(hot) + len(auto)} 条实时新闻作为参考")
    return result


# ======================== 生成主体 ========================

def repair_articles(data):
    """修复 AI 生成的 JSON 中可能出现的字段名错误"""
    aliases = {"dynamic": "detail", "description": "detail", "content": "detail"}
    fixed = 0
    for section in data.get("sections", []):
        for article in section.get("articles", []):
            for wrong, correct in aliases.items():
                if wrong in article and correct not in article:
                    article[correct] = article.pop(wrong)
                    fixed += 1
                    break
            for key in ["id", "title", "summary", "detail", "source"]:
                if key not in article:
                    article[key] = ""
    if fixed:
        print(f"🔧 修复了 {fixed} 个字段名错误")
    return data


def generate():
    today = datetime.now(BJ_TZ).strftime("%Y-%m-%d")

    # 抓取实时新闻
    auto_context = fetch_auto_context()

    system_prompt = f"""你是一位专业的汽车新闻编辑。以下是今日实时抓取到的汽车相关新闻：

{auto_context}

请基于以上实时新闻（结合你的知识补充细节），生成 {today} 的汽车新闻日报JSON。

要求：
- **必须基于真实新闻**，不要编造不存在的事件
- 如果热搜中有车企/车型/政策相关话题，必须收录
- 严禁编造产品发布/上市日期！不确定的不要写具体日期
- 已上市车型不能写成"刚发布"
- 每个新闻必须注明来源（真实存在的媒体）
- 语言客观简洁

JSON结构：
{{
  "date": "{today}",
  "summary": "一句话概括今日汽车圈重点",
  "sections": [
    {{
      "id": "headline",
      "title": "今日头条",
      "icon": "📰",
      "articles": [
        {{
          "id": "auto-001",
          "title": "标题",
          "summary": "一句话摘要",
          "detail": "详细内容100-200字",
          "source": "来源"
        }}
      ]
    }}
  ]
}}

5个板块（按此顺序）：
1. 今日头条：当天最重磅的汽车新闻（1篇）
2. 中国汽车市场：新车发布、政策动态（3-4篇）
3. 国际动态：国际车企、技术趋势（3-4篇）
4. 市场分析：销量数据、投资机会（2-3篇）
5. 明日展望：未来趋势预测（2篇）

直接输出JSON，不要markdown代码块。"""

    result = call_deepseek(system_prompt, f"今天是{today}。请基于实时新闻生成汽车新闻日报JSON，共5个板块，12-15篇文章。", max_tokens=8000)
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
            data = json.loads(clean[js:je])
            repair_articles(data)
            return data
        except Exception as e:
            print(f"❌ JSON解析失败: {e}")
            print(clean[:500])
            return None
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=JSON_PATH, help=f"输出路径（默认 {JSON_PATH}）")
    args = parser.parse_args()

    today = datetime.now(BJ_TZ).strftime('%Y-%m-%d')
    print(f"🚗 生成 {today} 汽车新闻日报（DeepSeek V4 + 实时热搜）...")

    content = generate()
    if content:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(content, f, ensure_ascii=False, indent=2)
        articles = sum(len(s.get("articles", [])) for s in content.get("sections", []))
        print(f"✅ 已写入: {args.output}")
        print(f"   板块: {len(content.get('sections', []))} 个 | 文章: {articles} 篇")
    else:
        print("❌ 生成失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
