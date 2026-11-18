#!/usr/bin/env python3
"""
DK 朝報 — 日本版每日晨报 JSON 生成器
用法: python3 generate_daily_news_ja.py [--output 路径] [--dry-run]

流程：抓取日本主流媒体 RSS → 选当日要闻 → MiMo 生成日语晨报 → schema 校验 → 输出 JSON
铁律（2026-11-03 教训）：
  1. date/edition 等机器字段由代码强制写入，不信模型输出
  2. 字段名过 sanitize 层白名单校验
  3. 内容必须基于真实 RSS 条目，禁止模型编造新闻
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
JST = timezone(timedelta(hours=9))

MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "tp-c6irsm5360gu18hd64hlmz47ltg54c5rbszghj45t5z96c31")
MIMO_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
MIMO_MODEL = os.environ.get("MIMO_MODEL", "xiaomi/mimo-v2.6-flash")
MIMO_FALLBACK = "xiaomi/mimo-v2.5-pro"

# ---- 日本信源（2026-11-18 连通性实测）----
FEEDS = [
    {"source": "ITmedia NEWS", "url": "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml"},
    {"source": "ASCII", "url": "https://ascii.jp/rss.xml"},
    {"source": "GIGAZINE", "url": "https://www.gigazine.net/news/rss_2.0/"},
    {"source": "Impress Watch", "url": "https://www.watch.impress.co.jp/data/rss/1.0/ipw/feed.rdf"},
    {"source": "Yahoo!ニュース", "url": "https://news.yahoo.co.jp/rss/topics/top-picks.xml"},
    {"source": "東洋経済オンライン", "url": "https://toyokeizai.net/list/feed/rss"},
]

SECTIONS = [
    {"key": "tech", "title": "テクノロジー"},
    {"key": "business", "title": "ビジネス"},
    {"key": "gadgets", "title": "ガジェット・新製品"},
    {"key": "society", "title": "今日の注目ニュース"},
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


def fetch_feeds(max_per_feed=8):
    """抓取全部 RSS，返回条目列表 [{title, summary, source, url, published}]"""
    items = []
    for feed in FEEDS:
        try:
            resp = requests.get(feed["url"], timeout=20, headers={"User-Agent": "Mozilla/5.0 DKMorningBot/1.0"})
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            # 兼容 RSS2.0 (<item>) / RDF·RSS1.0 (<item> 可能带 purl 命名空间) / Atom (<entry>)
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
            print(f"  ✅ {feed['source']}: {count} 件")
        except Exception as e:
            print(f"  ⚠️ {feed['source']} 取得失敗: {e}")
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
            print(f"  📊 [{model}] 入力 {data['usage']['prompt_tokens']} / 出力 {data['usage']['completion_tokens']}")
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"  ❌ {model} 失敗: {e}")
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
    js["date"] = datetime.now(JST).strftime("%Y-%m-%d")
    js["locale"] = "ja-JP"
    js["edition"] = "DK 朝報"
    return js


def build_briefing(items, today):
    corpus = "\n".join(
        f"- [{i['source']}] {i['title']} | {i['summary'][:100]} | {i['url']}" for i in items[:50]
    )
    section_spec = "\n".join(f"- {s['key']}: {s['title']}" for s in SECTIONS)

    system_prompt = f"""あなたは日本の一流新聞社の編集長です。配信された実際のニュース記事リストだけを素材に、日本語の朝刊ブリーフィングを作成してください。

出力は JSON のみ（他のテキスト禁止）。構造：
{{
  "quote": "今日の朝にふさわしい短い一言（30字以内）",
  "sections": [
    {{
      "key": "tech",
      "title": "テクノロジー",
      "items": [
        {{"title": "記事タイトル（原文を自然な日本語に）", "summary": "80〜120字の要約", "source": "媒体名", "url": "記事URL"}}
      ]
    }}
  ]
}}

セクション指定：
{section_spec}

厳守事項：
- 配信された記事リストに含まれる事実のみを使う。捏造・推測禁止
- 各セクション 2〜3 件、合計 8〜12 件
- summary は日本語で簡潔に。専門用語は自然な日本語
- source/url は入力リストからそのままコピー
- key/title フィールド名は上記構造どおり正確に"""

    user_prompt = f"本日は {today} です。以下の実ニュースから朝刊ブリーフィングを作成してください：\n\n{corpus}"
    result = call_mimo(system_prompt, user_prompt)
    if not result:
        return None

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
        print("❌ JSON が見つかりません")
        return None
    try:
        return json.loads(clean[js_start:js_end])
    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析失敗: {e}")
        print(clean[:500])
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=None)
    parser.add_argument("--dry-run", action="store_true", help="取得のみ（API 呼び出しなし）")
    args = parser.parse_args()

    today = datetime.now(JST).strftime("%Y-%m-%d")
    print(f"🌅 DK 朝報 {today} 生成開始")

    print("📡 ニュース取得中...")
    items = fetch_feeds()
    print(f"  合計 {len(items)} 件")
    if not items:
        sys.exit("❌ 記事が 0 件のため中断")
    if args.dry_run:
        for i in items[:10]:
            print(f"  - [{i['source']}] {i['title']}")
        return

    print("✍️ 朝刊生成中...")
    briefing = build_briefing(items, today)
    if not briefing:
        sys.exit("❌ 生成失敗")

    output = sanitize(briefing)
    out_path = args.output or os.path.join(os.path.dirname(__file__), "daily-morning-ja.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"✅ 出力: {out_path}（date={output['date']} sections={len(output.get('sections', []))}）")


if __name__ == "__main__":
    main()
