#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JSON 字段名规范化工具（2026-11-03 每日语言/英语不更新事故后新增）
LLM 生成 JSON 时字段名经常拼错（如 explation→explanation），导致 iOS App 解码失败永远显示旧缓存。
所有每日语言生成脚本在写盘前必须调用 sanitize()。
"""

# 常见幻觉拼写 → 正确字段名
KEY_FIXES = {
    "explation": "explanation",
    "explantion": "explanation",
    "expalanation": "explanation",
    "explaination": "explanation",
    "explannation": "explanation",
    "explanaton": "explanation",
    "tranlation": "translation",
    "transaltion": "translation",
    "tanslation": "translation",
    "translaiton": "translation",
    "phonetics": "phonetic",
    "phonitic": "phonetic",
    "pronounciation": "pronunciation",
    "pronuciation": "pronunciation",
    "vocabularies": "vocabulary",
    "vocabulry": "vocabulary",
    "grammer": "grammar",
    "grammer": "grammar",
    "exmaple": "example",
    "exampe": "example",
    "exmples": "examples",
    "exampls": "examples",
    "partOfSpeach": "partOfSpeech",
    "partofspeech": "partOfSpeech",
    "partOfSpech": "partOfSpeech",
    "titleTransation": "titleTranslation",
    "titletranslation": "titleTranslation",
    "newsHighlights": "newsHighlights",
    "newsHightlights": "newsHighlights",
    "author": "author",
    "autor": "author",
}

def fix_keys(o):
    if isinstance(o, dict):
        out = {}
        for k, v in o.items():
            nk = KEY_FIXES.get(k, k)
            # 兼容大小写变体
            if nk == k and k.lower() in KEY_FIXES:
                nk = KEY_FIXES[k.lower()]
            if nk in out and out[nk] != v:
                pass  # 保留先到的正确值
            else:
                out[nk] = fix_keys(v)
        return out
    if isinstance(o, list):
        return [fix_keys(x) for x in o]
    return o

def _ensure(d, key, default):
    if key not in d or d[key] is None:
        d[key] = default

def sanitize(obj, lang="en"):
    """规范化整个日报 JSON（顶层 {date, content:{...}} 结构）"""
    obj = fix_keys(obj)
    c = obj.get("content") if isinstance(obj, dict) else None
    if isinstance(c, dict):
        # 模型幻觉日期/ID 一律强制覆盖
        import datetime
        today = datetime.datetime.now(
            datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d")
        if isinstance(obj.get("date"), str):
            obj["date"] = today
        c["id"] = ("en-" if lang == "en" else "daily-%s-" % lang) + today
        c["date"] = today
        # App 解码必需字段兜底
        if isinstance(c.get("quote"), dict):
            _ensure(c["quote"], "explanation", "")
            _ensure(c["quote"], "translation", "")
            _ensure(c["quote"], "author", "")
        if isinstance(c.get("grammar"), dict):
            _ensure(c["grammar"], "explanation", "")
            _ensure(c["grammar"], "title", "")
            _ensure(c["grammar"], "examples", [])
        if isinstance(c.get("pattern"), dict):
            for k in ("pattern", "example", "translation", "usage"):
                _ensure(c["pattern"], k, "")
        if isinstance(c.get("pronunciation"), dict):
            for k in ("word", "phonetic", "tips"):
                _ensure(c["pronunciation"], k, "")
            _ensure(c["pronunciation"], "examples", [])
        if isinstance(c.get("reading"), dict):
            for k in ("title", "content", "translation"):
                _ensure(c["reading"], k, "")
        for w in c.get("vocabulary", []) if isinstance(c.get("vocabulary"), list) else []:
            if isinstance(w, dict):
                for k in ("word", "phonetic", "partOfSpeech", "definition", "example", "translation"):
                    _ensure(w, k, "")
    return obj

if __name__ == "__main__":
    import json, sys
    for p in sys.argv[1:]:
        d = json.load(open(p, encoding="utf-8"))
        lang = "en" if "english" in p else p.split("daily-")[-1].split(".json")[0]
        d = sanitize(d, lang)
        json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print("sanitized:", p)
