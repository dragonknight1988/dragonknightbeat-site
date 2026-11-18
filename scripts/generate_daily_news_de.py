#!/usr/bin/env python3
"""
DK Morgenpost — 德国版每日晨报 JSON 生成器
用法: python3 generate_daily_news_de.py [--output 路径] [--dry-run]

流程：抓取德国主流科技媒体 RSS → 选当日要闻 → MiMo 生成德语晨报 → schema 校验 → 输出 JSON
铁律（2026-11-03 教训）：
  1. date/edition 等机器字段由代码强制写入，不信模型输出
  2. 字段名过 sanitize 层白名单校验
  3. 内容必须基于真实 RSS 条目，禁止模型编造新闻
信源（2026-11-18 连通性实测）：t3n / WinFuture / Golem / Macwelt / Deutsche Startups / Basic Thinking
（Heise/Spiegel/ZEIT/WELT/Tagesschau 等国内网络不可达或 403，勿加回）
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
CET = timezone(timedelta(hours=1))  # 中欧（柏林）

MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "tp-c6irsm5360gu18hd64hlmz47ltg54c5rbszghj45t5z96c31")
MIMO_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
MIMO_MODEL = os.environ.get("MIMO_MODEL", "xiaomi/mimo-v2.6-flash")
MIMO_FALLBACK = "xiaomi/mimo-v2.5-pro"

# ---- 德国信源（2026-11-18 连通性实测）----
FEEDS = [
    {"source": "Golem", "url": "https://rss.golem.de/rss.php?feed=RSS2.0"},
    {"source": "t3n", "url": "https://t3n.de/rss.xml"},
    {"source": "WinFuture", "url": "https://winfuture.de/rss"},
    {"source": "Macwelt", "url": "https://www.macwelt.de/feed"},
    {"source": "Deutsche Startups", "url": "https://www.deutsche-startups.de/feed/"},
    {"source": "Basic Thinking", "url": "https://www.basicthinking.de/blog/feed/"},
]

SECTIONS = [
    {"key": "tech", "title": "Tech"},
    {"key": "business", "title": "Wirtschaft"},
    {"key": "gadgets", "title": "Gadgets & Produkte"},
    {"key": "society", "title": "Top-Themen"},
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
            print(f"  ✅ {feed['source']}: {count} Artikel")
        except Exception as e:
            print(f"  ⚠️ {feed['source']} Abruf fehlgeschlagen: {e}")
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
            print(f"  📊 [{model}] Eingabe {data['usage']['prompt_tokens']} / Ausgabe {data['usage']['completion_tokens']}")
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"  ❌ {model} fehlgeschlagen: {e}")
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
    js["date"] = datetime.now(CET).strftime("%Y-%m-%d")
    js["locale"] = "de-DE"
    js["edition"] = "DK Morgenpost"
    return js


def build_briefing(items, today):
    corpus = "\n".join(
        f"- [{i['source']}] {i['title']} | {i['summary'][:100]} | {i['url']}" for i in items[:50]
    )
    section_spec = "\n".join(f"- {s['key']}: {s['title']}" for s in SECTIONS)

    system_prompt = f"""Du bist Chefredakteur einer bedeutenden deutschen Morgenzeitung. Verfasse auf Basis AUSSCHLIESSLICH der gelieferten echten Nachrichtenartikel eine kompakte Morgenbrifing auf Deutsch.

Ausgabe nur als JSON (kein anderer Text). Struktur:
{{
  "quote": "Ein kurzer inspirierender Satz für den Morgen (max. 60 Zeichen)",
  "sections": [
    {{
      "key": "tech",
      "title": "Tech",
      "items": [
        {{"title": "Schlagzeile (prägnantes Deutsch)", "summary": "Zusammenfassung in 60-100 Wörtern", "source": "Medium", "url": "Artikel-URL"}}
      ]
    }}
  ]
}}

Sektionen:
{section_spec}

Regeln:
- Nur Fakten aus der gelieferten Artikelliste. Keine Erfindungen oder Spekulationen
- 2-3 Beiträge pro Sektion, insgesamt 8-12 Beiträge
- summary in klarem, präzisem Deutsch
- source/url unverändert aus der Eingabeliste übernehmen
- Feldnamen key/title exakt wie in der Struktur oben"""

    user_prompt = f"Heute ist {today}. Erstelle die Morgenbriefing aus diesen echten Nachrichten:\n\n{corpus}"
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
        print("❌ JSON nicht gefunden")
        return None
    try:
        return json.loads(clean[js_start:js_end])
    except json.JSONDecodeError as e:
        print(f"❌ JSON-Parsing fehlgeschlagen: {e}")
        print(clean[:500])
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=None)
    parser.add_argument("--dry-run", action="store_true", help="nur Abruf (kein API-Aufruf)")
    args = parser.parse_args()

    today = datetime.now(CET).strftime("%Y-%m-%d")
    print(f"🌅 DK Morgenpost {today} Erzeugung gestartet")

    print("📡 Nachrichten abrufen...")
    items = fetch_feeds()
    print(f"  insgesamt {len(items)} Artikel")
    if not items:
        sys.exit("❌ 0 Artikel, Abbruch")
    if args.dry_run:
        for i in items[:10]:
            print(f"  - [{i['source']}] {i['title']}")
        return

    print("✍️ Briefing erstellen...")
    briefing = build_briefing(items, today)
    if not briefing:
        sys.exit("❌ Erzeugung fehlgeschlagen")

    output = sanitize(briefing)
    out_path = args.output or os.path.join(os.path.dirname(__file__), "daily-morning-de.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"✅ Ausgabe: {out_path}（date={output['date']} sections={len(output.get('sections', []))}）")


if __name__ == "__main__":
    main()
