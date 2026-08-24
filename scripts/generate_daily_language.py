#!/usr/bin/env python3
"""
每日小语种 JSON 生成器（通用版）
用法: python3 generate_daily_language.py --lang russian --output /path/to/daily-russian.json
"""

import json, os, sys, argparse, requests
from datetime import datetime, timezone, timedelta

BJ_TZ = timezone(timedelta(hours=8))
MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "tp-c6irsm5360gu18hd64hlmz47ltg54c5rbszghj45t5z96c31")
MIMO_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
MIMO_MODEL = "xiaomi/mimo-v2.5-pro"

LANGS = {
    "german":   {"flag": "🇩🇪", "name": "德语",     "country": "德国",   "article": "der/die/das",          "topics": ["日常问候与自我介绍","在咖啡馆点餐","问路与交通","购物与讨价还价","在医院看病","酒店入住与退房","德国美食与烹饪","节日与传统","工作与面试","租房与搬家","天气与季节","爱好与运动","在邮局和银行","德国教育体系","环保与可持续发展","德国汽车文化","音乐与艺术","德国历史人物","科技与创新","德国大学生活","在超市购物","德国公共交通","德国职场文化","德国家庭生活","德国啤酒文化","圣诞市场","黑森林与旅游","德国哲学","足球与体育","德国文学"]},
    "russian":  {"flag": "🇷🇺", "name": "俄语",     "country": "俄罗斯", "article": "阳性/阴性/中性",       "topics": ["俄语字母与发音基础","日常问候与礼貌用语","在餐厅点餐","莫斯科地铁出行","购物与市场","在医院看病","酒店入住","俄罗斯美食与烹饪","工作与面试","租房与搬家","天气与季节","爱好与运动","在邮局和银行","俄罗斯教育体系","环保话题","俄罗斯汽车文化","音乐与艺术","俄罗斯历史人物","科技与创新","俄罗斯大学生活","在超市购物","俄罗斯公共交通","俄罗斯职场文化","俄罗斯家庭生活","俄罗斯茶文化","新年与圣诞","贝加尔湖与旅游","俄罗斯文学","足球与体育","俄罗斯芭蕾与戏剧"]},
    "french":   {"flag": "🇫🇷", "name": "法语",     "country": "法国",   "article": "le/la/les",            "topics": ["日常问候与自我介绍","在咖啡馆点餐","巴黎地铁出行","购物与时尚","在医院看病","酒店入住与退房","法国美食与烹饪","节日与传统","工作与面试","租房与搬家","天气与季节","爱好与运动","在邮局和银行","法国教育体系","环保与可持续发展","法国汽车文化","音乐与艺术","法国历史人物","科技与创新","法国大学生活","在超市购物","法国公共交通","法国职场文化","法国家庭生活","法国葡萄酒文化","圣诞市场","普罗旺斯与旅游","法国哲学","足球与体育","法国文学与电影"]},
    "spanish":  {"flag": "🇪🇸", "name": "西班牙语", "country": "西班牙", "article": "el/la/los/las",        "topics": ["日常问候与自我介绍","在餐厅点餐","问路与交通","购物与讨价还价","在医院看病","酒店入住与退房","西班牙美食与烹饪","节日与传统","工作与面试","租房与搬家","天气与季节","爱好与运动","在邮局和银行","西班牙教育体系","环保与可持续发展","西班牙汽车文化","音乐与艺术","西班牙历史人物","科技与创新","西班牙大学生活","在超市购物","西班牙公共交通","西班牙职场文化","西班牙家庭生活","西班牙红酒文化","圣诞节与三王节","安达卢西亚与旅游","西班牙文学","足球与体育","弗拉门戈与艺术"]},
    "italian":  {"flag": "🇮🇹", "name": "意大利语", "country": "意大利", "article": "il/la/i/le",           "topics": ["日常问候与自我介绍","在咖啡馆点餐","罗马交通出行","购物与时尚","在医院看病","酒店入住与退房","意大利美食与烹饪","节日与传统","工作与面试","租房与搬家","天气与季节","爱好与运动","在邮局和银行","意大利教育体系","环保与可持续发展","意大利汽车文化","音乐与艺术","意大利历史人物","科技与创新","意大利大学生活","在超市购物","意大利公共交通","意大利职场文化","意大利家庭生活","意大利葡萄酒文化","圣诞节与复活节","托斯卡纳与旅游","意大利文学","足球与体育","歌剧与艺术"]},
}

def build_prompts(lang):
    c = LANGS[lang]
    flag = c["flag"]
    name = c["name"]
    country = c["country"]
    art = c["article"]

    lang_name = name
    sys_prompt = (
        "你是一个" + lang_name + "教学内容生成器。请严格按照以下JSON格式生成每日" + lang_name + "学习内容。\n\n"
        "要求：\n"
        "1. 所有内容必须准确，" + lang_name + "语法正确\n"
        "2. 适合初中级" + lang_name + "学习者（A2-B1水平）\n"
        "3. 单词必须标注" + art + "词性和复数形式（如有）\n"
        "4. 例句要实用、贴近生活\n"
        "5. 句型（pattern）的例句必须融入当日词汇表中的至少2个单词\n"
        "6. 包含一个" + country + "文化小知识\n"
        "7. topic、quote.translation、quote.explanation、vocabulary的definition和exampleTranslation、pattern.translation、grammar.title、grammar.explanation、reading.titleTranslation、reading.translation、culture.title、culture.content 这些字段必须用中文输出\n"
        "8. quote.quote、vocabulary的word和example、pattern.pattern/example/usage、grammar.examples、pronunciation全部字段、reading.title、reading.content 这些字段必须用目标语言" + lang_name + "输出\n\n"
        "输出格式（严格JSON，不要添加任何markdown标记）：\n"
        "{\n"
        '  "id": "daily-' + lang + '-YYYY-MM-DD",\n'
        '  "date": "YYYY-MM-DD",\n'
        '  "topic": "主题名称",\n'
        '  "quote": { "quote": "' + lang_name + '名言", "author": "作者", "translation": "中文翻译", "explanation": "中文解读" },\n'
        '  "vocabulary": [ { "word": "' + lang_name + '单词", "article": "' + art + '", "plural": "复数", "phonetic": "IPA音标", "partOfSpeech": "词性", "definition": "中文释义", "example": "' + lang_name + '例句", "exampleTranslation": "中文翻译" } ],\n'
        '  "pattern": { "pattern": "句型", "example": "例句", "translation": "中文翻译", "usage": "用法说明" },\n'
        '  "grammar": { "title": "语法标题", "explanation": "中文解释", "examples": ["例句1", "例句2", "例句3"] },\n'
        '  "pronunciation": { "word": "重点词", "phonetic": "音标", "tips": "发音技巧", "examples": ["例词1", "例词2", "例词3"] },\n'
        '  "reading": { "title": "短文标题（目标语言）", "titleTranslation": "标题中文翻译", "content": "' + lang_name + '短文80-120词", "translation": "中文翻译" },\n'
        '  "culture": { "title": "文化标题", "content": "文化内容" }\n'
        "}"
    )

    usr_template = "请生成今天的每日" + name + "学习内容。主题：{topic}\n\n要求：\n- 10个常用单词（含" + art + "词性、复数、IPA音标、例句）\n- 1个常用句型（含用法说明）。**重要：句型的例句中必须使用上面10个词汇中的至少2个单词**\n- 1个语法点（含3个例句）\n- 1个发音重点（含技巧和3个例词）\n- 1篇" + name + "短文（80-120词，含中文翻译），titleTranslation: 标题的中文翻译\n- 1个" + country + "文化小知识\n- 1句" + name + "名言（含作者和解读）\n\n请直接输出JSON，不要添加任何markdown标记。"

    return sys_prompt, usr_template


def call_mimo(sys_prompt, usr_prompt):
    headers = {"Authorization": "Bearer " + MIMO_API_KEY, "Content-Type": "application/json"}
    payload = {"model": MIMO_MODEL, "messages": [{"role": "system", "content": sys_prompt}, {"role": "user", "content": usr_prompt}], "max_tokens": 8192, "temperature": 0.8}
    try:
        resp = requests.post(MIMO_BASE_URL + "/chat/completions", headers=headers, json=payload, timeout=300)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print("API error: " + str(e))
        return None


def generate_daily(lang, topic=None):
    c = LANGS[lang]
    today = datetime.now(BJ_TZ).strftime("%Y-%m-%d")
    topics = c["topics"]
    idx = int(today.split("-")[2]) % len(topics)
    selected = topic or topics[idx]
    flag = c["flag"]
    name = c["name"]

    print(flag + " Generating " + today + " " + name + " (MiMo Pro)...")
    print("Topic: " + selected)

    sp, ut = build_prompts(lang)
    result = call_mimo(sp, ut.format(topic=selected))
    if not result:
        return None

    clean = result.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
    if clean.endswith("```"):
        clean = clean[:-3]
    clean = clean.strip()

    ob = clean.count("{") - clean.count("}")
    oj = clean.count("[") - clean.count("]")
    if ob > 0 or oj > 0:
        lines = clean.rstrip().rsplit("\n", 1)
        if len(lines) > 1:
            clean = lines[0]
        clean = clean.rstrip().rstrip(",") + "]" * oj + "}" * ob
        print("JSON truncated, auto-fixed: " + str(ob) + " braces, " + str(oj) + " brackets")

    try:
        content = json.loads(clean)
        output = {"date": today, "content": content}
        print("OK: " + content.get("topic", "N/A"))
        return output
    except json.JSONDecodeError as e:
        print("JSON parse error: " + str(e))
        return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--lang", "-l", required=True, choices=list(LANGS.keys()))
    p.add_argument("--output", "-o")
    p.add_argument("--topic", "-t")
    args = p.parse_args()

    output = generate_daily(args.lang, args.topic)
    if not output:
        sys.exit(1)

    path = args.output or "/var/www/dragonknightbeat.com/daily-" + args.lang + ".json"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("Written: " + path)


if __name__ == "__main__":
    main()
