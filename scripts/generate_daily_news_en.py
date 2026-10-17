#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_daily_news_en.py — 把中文 daily JSON 翻译成英文版（海外 DK News App 数据源）
输入:  /var/www/dragonknightbeat.com/daily-news.json / daily-auto.json / daily-briefing.json
输出:  /var/www/dragonknightbeat.com/daily-news-en.json / daily-auto-en.json / daily-briefing-en.json
策略:  结构保持（keys 不变，只译值），逐 section 调用 MiMo，防输出截断；单块失败自动回退原文
"""
import os, sys, json, re, time, argparse
import requests

MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "tp-c6irsm5360gu18hd64hlmz47ltg54c5rbszghj45t5z96c31")
MIMO_BASE_URL = os.environ.get("MIMO_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1")
MIMO_MODEL = "xiaomi/mimo-v2.6-flash"

WEBROOT = "/var/www/dragonknightbeat.com"
SITE_DIR = "/opt/dragonknightbeat-site"

SYSTEM_PROMPT = """You are a professional news editor translating Chinese news digests into natural English for international readers.
Rules:
1) Keep the JSON structure and ALL keys EXACTLY the same. Translate only the string VALUES into English.
2) Do NOT change the values of "id" and "importance" fields (they are language-neutral enums).
3) Translate news titles, summaries, details, impact analysis, tags, sources, section titles into concise international wire-style English.
4) Render dates like "October 17, 2026" and weekdays in English.
5) Keep emoji icons unchanged.
6) Output MUST be valid JSON only — no markdown fences, no commentary."""

def call_mimo(user_prompt, max_tokens=8000, retries=3):
    for attempt in range(retries):
        try:
            resp = requests.post(
                f"{MIMO_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {MIMO_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": MIMO_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": max_tokens,
                },
                timeout=180,
            )
            if resp.status_code != 200:
                print(f"  ⚠️ API HTTP {resp.status_code}: {resp.text[:200]}")
                time.sleep(5)
                continue
            content = resp.json()["choices"][0]["message"]["content"]
            return extract_json(content)
        except Exception as e:
            print(f"  ⚠️ 调用失败({attempt + 1}/{retries}): {e}")
            time.sleep(5)
    return None

def extract_json(text):
    # 去掉 ```json 围栏，提取最外层 JSON
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.M)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        # 尝试去掉尾部截断的半个对象再解析
        for cut in range(end, start, -1):
            try:
                return json.loads(text[start:cut] + "}")
            except json.JSONDecodeError:
                continue
    return None

def repair_structure(src, out, key=None):
    """确保译文与原文 key 结构完全一致（防模型漏字段导致 App 解码失败）
    - id / importance / 数字 / 布尔：一律用原值
    - 字符串：译文为空则回退原文
    - dict：按原文 key 集合补齐
    - list：长度不一致直接回退原文"""
    if key in ("id", "importance"):
        return src
    if isinstance(src, dict):
        if not isinstance(out, dict):
            return src
        return {k: repair_structure(v, out.get(k), k) for k, v in src.items()}
    if isinstance(src, list):
        if not isinstance(out, list) or len(out) != len(src):
            return src
        return [repair_structure(s, o, key) for s, o in zip(src, out)]
    if isinstance(src, str):
        return out if isinstance(out, str) and out.strip() else src
    return src


def translate_chunk(chunk, label):
    """翻译一个 JSON 块；失败时返回原文（保底出片）"""
    payload = json.dumps(chunk, ensure_ascii=False)
    print(f"  🌍 翻译 {label} ({len(payload)} chars)")
    result = call_mimo("Translate this JSON:\n" + payload)
    if not isinstance(result, dict) and not isinstance(result, list):
        print(f"  ❌ {label} 翻译失败，回退原文")
        return chunk
    return repair_structure(chunk, result)

def translate_news(src_path, out_path):
    """daily-news.json → daily-news-en.json（meta + 逐 section）"""
    data = json.load(open(src_path, encoding="utf-8"))
    out = {}
    meta = {k: v for k, v in data.items() if k != "sections"}
    out.update(translate_chunk(meta, "news-meta"))
    out["sections"] = []
    for sec in data.get("sections", []):
        t = translate_chunk(sec, f"section:{sec.get('title', '?')}")
        # 结构校验：翻译结果必须保留 title/articles
        if isinstance(t, dict) and "title" in t and "articles" in t:
            t.setdefault("icon", sec.get("icon", "📰"))
            out["sections"].append(t)
        else:
            print(f"  ❌ section 结构异常，回退原文")
            out["sections"].append(sec)
    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"✅ 已写入 {out_path}")

def translate_auto(src_path, out_path):
    """daily-auto.json → daily-auto-en.json"""
    data = json.load(open(src_path, encoding="utf-8"))
    out = {}
    meta = {k: v for k, v in data.items() if k != "sections"}
    out.update(translate_chunk(meta, "auto-meta"))
    out["sections"] = []
    for sec in data.get("sections", []):
        t = translate_chunk(sec, f"auto-section:{sec.get('title', '?')}")
        if isinstance(t, dict) and "articles" in t:
            t.setdefault("icon", sec.get("icon", "🚗"))
            out["sections"].append(t)
        else:
            out["sections"].append(sec)
    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"✅ 已写入 {out_path}")

def translate_briefing(src_path, out_path):
    """daily-briefing.json → daily-briefing-en.json"""
    data = json.load(open(src_path, encoding="utf-8"))
    out = {}
    for key, value in data.items():
        if key == "briefing" and isinstance(value, dict):
            b = {}
            bmeta = {k: v for k, v in value.items() if k != "sections"}
            b.update(translate_chunk(bmeta, "briefing-meta"))
            b["sections"] = []
            for sec in value.get("sections", []):
                t = translate_chunk(sec, f"briefing-section:{sec.get('title', '?')}")
                if isinstance(t, dict) and "articles" in t:
                    t.setdefault("icon", sec.get("icon", "📡"))
                    b["sections"].append(t)
                else:
                    b["sections"].append(sec)
            out["briefing"] = b
        else:
            out[key] = translate_chunk(value, f"briefing:{key}")
    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"✅ 已写入 {out_path}")

def validate(path):
    """最低限度结构校验，防止产出空壳 JSON"""
    try:
        d = json.load(open(path, encoding="utf-8"))
        if "sections" in d and not d["sections"]:
            raise ValueError("sections 为空")
        return True
    except Exception as e:
        print(f"❌ 校验失败 {path}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=None, help="兼容 gen-cron.sh 参数，本脚本固定生成3个en文件")
    args = parser.parse_args()

    jobs = [
        ("daily-news.json", "daily-news-en.json", translate_news),
        ("daily-auto.json", "daily-auto-en.json", translate_auto),
        ("daily-briefing.json", "daily-briefing-en.json", translate_briefing),
    ]
    ok = 0
    for src_name, out_name, fn in jobs:
        src = os.path.join(WEBROOT, src_name)
        out = os.path.join(WEBROOT, out_name)
        if not os.path.exists(src):
            print(f"⚠️ 源文件不存在，跳过: {src}")
            continue
        print(f"===== 处理 {src_name} → {out_name} =====")
        fn(src, out)
        if validate(out):
            # 同步到 git 目录（与 gen-cron.sh 一致）
            try:
                import shutil
                shutil.copy(out, os.path.join(SITE_DIR, out_name))
            except Exception as e:
                print(f"⚠️ 同步 git 目录失败: {e}")
            ok += 1
    print(f"🏁 完成 {ok}/{len(jobs)}")
    sys.exit(0 if ok == len(jobs) else 1)

if __name__ == "__main__":
    main()
