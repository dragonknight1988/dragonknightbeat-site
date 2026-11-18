#!/usr/bin/env python3
"""
DK DK เช้าข่าว — 泰国版每日晨报 JSON 生成器
用法: python3 generate_daily_news_th.py [--output 路径] [--dry-run]

流程：抓取泰国主流媒体 RSS → 选当日要闻 → MiMo 生成Thai晨报 → schema 校验 → 输出 JSON
铁律（2026-11-03 教训）：
  1. date/edition 等机器字段由代码强制写入，不信模型输出
  2. 字段名过 sanitize 层白名单校验
  3. 内容必须基于真实 RSS 条目，禁止模型编造新闻
信源（2026-11-18 连通性实测）：Techsauce / Beartai / MarketingOops
"""

import json
import os
import sys
import argparse
import html
import re
from datetime import datetime, timezone, timedelta

import requests

try:
    import xml.etree.ElementTree as ET
except ImportError:
    pass

# ---- 时区与常量 ----
LOCAL_TZ = timezone(timedelta(hours=7))

MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "tp-c6irsm5360gu18hd64hlmz47ltg54c5rbszghj45t5z96c31")
MIMO_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
MIMO_MODEL = os.environ.get("MIMO_MODEL", "xiaomi/mimo-v2.6-flash")
MIMO_FALLBACK = "xiaomi/mimo-v2.5-pro"

# ---- 泰国信源（2026-11-18 连通性实测）----
FEEDS = [
    {"source": "Techsauce", "url": "https://techsauce.co/feed"},
    {"source": "Beartai", "url": "https://www.beartai.com/feed"},
    {"source": "MarketingOops", "url": "https://www.marketingoops.com/feed/"},
]

SECTIONS = [
    {"key": "tech", "title": "เทคโนโลยี"},
    {"key": "business", "title": "ธุรกิจ"},
    {"key": "gadgets", "title": "แกดเจ็ตและผลิตภัณฑ์"},
    {"key": "society", "title": "ข่าวเด่น"},
]

# ---- schema 白名单（防字段名拼错）----
ALLOWED_ITEM_KEYS = {"title", "summary", "source", "url"}
ALLOWED_SECTION_KEYS = {"key", "title", "items"}
ALLOWED_ROOT_KEYS = {"date", "locale", "edition", "quote", "sections"}


def strip_html(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def _local(tag):
    """去掉命名空间，取本地标签名"""
    return tag.split("}")[-1] if "}" in tag else tag


def _field(node, *names):
    """命名空间无关取子元素文本（RSS2.0/RDF(RSS1.0)/Atom 通吃）"""
    for ch in node:
        if _local(ch.tag) in names and ch.text:
            return ch.text
    return ""


def fetch_feeds(max_per_feed=10):
    """抓取全部 RSS，返回条目列表 [{title, summary, source, url, published}]"""
    items = []
    for feed in FEEDS:
        try:
            resp = requests.get(feed["url"], timeout=20, headers={"User-Agent": "Mozilla/5.0 DKMorningBot/1.0"})
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            nodes = [e for e in root.iter() if _local(e.tag) in ("item", "entry")]
            count = 0
            for node in nodes:
                if count >= max_per_feed:
                    break
                title = _field(node, "title")
                link = _field(node, "link")
                if not link:
                    for ch in node:
                        if _local(ch.tag) == "link" and ch.get("href"):
                            link = ch.get("href", "")
                desc = _field(node, "description", "summary", "encoded")
                pub = _field(node, "pubDate", "date", "published", "updated")
                title = strip_html(title)
                if not title:
                    continue
                items.append({
                    "title": title[:120],
                    "summary": strip_html(desc)[:200],
                    "source": feed["source"],
                    "url": link,
                    "published": pub,
                })
                count += 1
            print(f"  OK {feed['source']}: {count} items")
        except Exception as e:
            print(f"  WARN {feed['source']} fetch failed: {e}")
    return items


def call_mimo(system_prompt, user_prompt, max_tokens=10000):
    headers = {"Authorization": f"Bearer {MIMO_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": MIMO_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.6,
    }
    for model in (MIMO_MODEL, MIMO_FALLBACK):
        payload["model"] = model
        try:
            resp = requests.post(f"{MIMO_BASE_URL}/chat/completions", headers=headers, json=payload, timeout=300)
            resp.raise_for_status()
            data = resp.json()
            print(f"  [{model}] in {data['usage']['prompt_tokens']} / out {data['usage']['completion_tokens']}")
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"  FAIL {model}: {e}")
    return None


def sanitize(js):
    """白名单清洗 + 代码强制写入机器字段"""
    for sec in js.get("sections", []):
        for bad in [k for k in sec if k not in ALLOWED_SECTION_KEYS]:
            sec.pop(bad, None)
        for item in sec.get("items", []):
            for bad in [k for k in item if k not in ALLOWED_ITEM_KEYS]:
                item.pop(bad, None)
            item.setdefault("source", "")
            item.setdefault("url", "")
    for bad in [k for k in js if k not in ALLOWED_ROOT_KEYS]:
        js.pop(bad, None)
    # 机器字段强制覆盖
    js["date"] = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")
    js["locale"] = "th-TH"
    js["edition"] = "DK เช้าข่าว"
    return js


def build_briefing(items, today):
    corpus = "\n".join(
        f"- [{i['source']}] {i['title']} | {i['summary'][:100]} | {i['url']}" for i in items[:50]
    )
    section_spec = "\n".join(f"- {s['key']}: {s['title']}" for s in SECTIONS)

    system_prompt = f"""You are the editor-in-chief of a major Thai morning newspaper. Using ONLY the real news article list provided, write a concise morning briefing entirely in Thai.

Output JSON only (no other text). Structure:
{{
  "quote": "A short inspiring line for the morning in Thai (max 60 chars)",
  "sections": [
    {{
      "key": "tech",
      "title": "use the section titles given below verbatim",
      "items": [
        {{"title": "Headline in natural Thai", "summary": "60-100 word summary in Thai", "source": "Outlet name", "url": "Article URL"}}
      ]
    }}
  ]
}}

Section spec (use these titles verbatim):
{section_spec}

Rules:
- Use only facts from the provided article list. No fabrication or speculation
- 2-3 items per section, 8-12 items total
- All title/summary/quote text must be in Thai (keep proper nouns and outlet names as-is)
- copy source/url exactly from the input list
- key/title field names must match the structure above exactly"""

    user_prompt = f"Today is {today}. Create the morning briefing from these real news items:\n\n{corpus}"
    for attempt in (1, 2):
        result = call_mimo(system_prompt, user_prompt)
        if not result:
            continue
        clean = result.strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        elif clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        clean = clean.strip()
        js_start = clean.find("{")
        js_end = clean.rfind("}") + 1
        if js_start < 0 or js_end <= js_start:
            print(f"JSON not found (attempt {attempt})")
            continue
        try:
            return json.loads(clean[js_start:js_end])
        except json.JSONDecodeError as e:
            print(f"JSON parse failed (attempt {attempt}): {e}")
            print(clean[:300])
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=None)
    parser.add_argument("--dry-run", action="store_true", help="fetch only (no API call)")
    args = parser.parse_args()

    today = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")
    print(f"DK DK เช้าข่าว {today} generation started")

    print("Fetching news...")
    items = fetch_feeds()
    print(f"  total {len(items)} items")
    if not items:
        sys.exit("0 articles, aborting")
    if args.dry_run:
        for i in items[:10]:
            print(f"  - [{i['source']}] {i['title']}")
        return

    print("Building briefing...")
    briefing = build_briefing(items, today)
    if not briefing:
        sys.exit("generation failed")

    output = sanitize(briefing)
    out_path = args.output or os.path.join(os.path.dirname(__file__), "daily-morning-th.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"Output: {out_path} (date={output['date']} sections={len(output.get('sections', []))})")


if __name__ == "__main__":
    main()
