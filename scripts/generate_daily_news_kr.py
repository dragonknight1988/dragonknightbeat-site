#!/usr/bin/env python3
"""
DK 조간 — 韩国版每日晨报 JSON 生成器
用法: python3 generate_daily_news_kr.py [--output 路径] [--dry-run]

流程：抓取韩国主流媒体 RSS → 选当日要闻 → MiMo 生成韩语晨报 → schema 校验 → 输出 JSON
铁律（2026-11-03 教训）：
  1. date/edition 等机器字段由代码强制写入，不信模型输出
  2. 字段名过 sanitize 层白名单校验
  3. 内容必须基于真实 RSS 条目，禁止模型编造新闻
信源（2026-11-18 连通性实测）：연합뉴스 / 전자신문 / AI타임스 / byline.network
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
KST = timezone(timedelta(hours=9))

MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "tp-c6irsm5360gu18hd64hlmz47ltg54c5rbszghj45t5z96c31")
MIMO_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
MIMO_MODEL = os.environ.get("MIMO_MODEL", "xiaomi/mimo-v2.6-flash")
MIMO_FALLBACK = "xiaomi/mimo-v2.5-pro"

# ---- 韩国信源（2026-11-18 连通性实测）----
FEEDS = [
    {"source": "연합뉴스", "url": "https://www.yna.co.kr/rss/news.xml"},
    {"source": "전자신문", "url": "https://rss.etnews.com/Section902.xml"},
    {"source": "AI타임스", "url": "https://www.aitimes.com/rss/allArticle.xml"},
    {"source": "byline.network", "url": "https://byline.network/feed/"},
]

SECTIONS = [
    {"key": "tech", "title": "IT·테크"},
    {"key": "business", "title": "산업·비즈니스"},
    {"key": "gadgets", "title": "신제품·가젯"},
    {"key": "society", "title": "오늘의 주요뉴스"},
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
            print(f"  ✅ {feed['source']}: {count} 件")
        except Exception as e:
            print(f"  ⚠️ {feed['source']} 가져오기 실패: {e}")
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
            print(f"  📊 [{model}] 입력 {data['usage']['prompt_tokens']} / 출력 {data['usage']['completion_tokens']}")
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"  ❌ {model} 실패: {e}")
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
    js["date"] = datetime.now(KST).strftime("%Y-%m-%d")
    js["locale"] = "ko-KR"
    js["edition"] = "DK 조간"
    return js


def build_briefing(items, today):
    corpus = "\n".join(
        f"- [{i['source']}] {i['title']} | {i['summary'][:100]} | {i['url']}" for i in items[:50]
    )
    section_spec = "\n".join(f"- {s['key']}: {s['title']}" for s in SECTIONS)

    system_prompt = f"""당신은 한국의 유력 신문사 편집장입니다. 전달된 실제 뉴스 기사 목록만을 소재로 한국어 아침 브리핑을 작성하세요.

출력은 JSON만 (다른 텍스트 금지). 구조:
{{
  "quote": "오늘 아침에 어울리는 짧은 한마디(30자 이내)",
  "sections": [
    {{
      "key": "tech",
      "title": "IT·테크",
      "items": [
        {{"title": "기사 제목(자연스러운 한국어로)", "summary": "80~120자 요약", "source": "매체명", "url": "기사 URL"}}
      ]
    }}
  ]
}}

섹션 지정:
{section_spec}

준수 사항:
- 전달된 기사 목록에 포함된 사실만 사용. 지어내기·추측 금지
- 각 섹션 2~3건, 합계 8~12건
- summary는 한국어로 간결하게. 전문용어는 자연스러운 한국어로
- source/url은 입력 목록에서 그대로 복사
- key/title 필드명은 위 구조대로 정확히"""

    user_prompt = f"오늘은 {today}입니다. 아래 실제 뉴스로 아침 브리핑을 작성하세요:\n\n{corpus}"
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
        print("❌ JSON을 찾을 수 없습니다")
        return None
    try:
        return json.loads(clean[js_start:js_end])
    except json.JSONDecodeError as e:
        print(f"❌ JSON 파싱 실패: {e}")
        print(clean[:500])
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=None)
    parser.add_argument("--dry-run", action="store_true", help="가져오기만 (API 호출 없음)")
    args = parser.parse_args()

    today = datetime.now(KST).strftime("%Y-%m-%d")
    print(f"🌅 DK 조간 {today} 생성 시작")

    print("📡 뉴스 가져오는 중...")
    items = fetch_feeds()
    print(f"  총 {len(items)} 件")
    if not items:
        sys.exit("❌ 기사가 0건이라 중단")
    if args.dry_run:
        for i in items[:10]:
            print(f"  - [{i['source']}] {i['title']}")
        return

    print("✍️ 아침 호 생성 중...")
    briefing = build_briefing(items, today)
    if not briefing:
        sys.exit("❌ 생성 실패")

    output = sanitize(briefing)
    out_path = args.output or os.path.join(os.path.dirname(__file__), "daily-morning-kr.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"✅ 출력: {out_path}（date={output['date']} sections={len(output.get('sections', []))}）")


if __name__ == "__main__":
    main()
