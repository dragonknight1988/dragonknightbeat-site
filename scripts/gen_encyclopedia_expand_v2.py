#!/usr/bin/env python3
"""百科全书扩充脚本 v2 — 每批次立即保存，支持断点续跑"""
import json, os, sys, time, requests

API_KEY = os.environ.get("MIMO_API_KEY", "tp-c6irsm5360gu18hd64hlmz47ltg54c5rbszghj45t5z96c31")
BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
MODEL = "xiaomi/mimo-v2.5-pro"
OUT_DIR = "/opt/dragonknightbeat-site/encyclopedia"
TARGET_PER_CAT = 500
BATCH_SIZE = 10

# 导入原脚本的 EXPAND_TOPICS
sys.path.insert(0, "/opt/dragonknightbeat-site/scripts")
try:
    from importlib import import_module
    orig = __import__("gen_encyclopedia_expand", fromlist=["EXPAND_TOPICS"])
    EXPAND_TOPICS = orig.EXPAND_TOPICS
except:
    # fallback: 直接从原脚本读取
    exec(open(os.path.join(os.path.dirname(__file__), "gen_encyclopedia_expand.py")).read().split("def call_mimo")[0])
    EXPAND_TOPICS = locals().get("EXPAND_TOPICS", {})

def call_mimo(system_prompt, user_prompt):
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "max_tokens": 8000,
        "temperature": 0.75
    }
    for attempt in range(3):
        try:
            resp = requests.post(f"{BASE_URL}/chat/completions", headers=headers, json=payload, timeout=300)
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 30))
                print(f"  ⏳ 限流，等待{wait}秒...", flush=True)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            print(f"  📝 Token: {usage.get('total_tokens', '?')}", flush=True)
            return content
        except Exception as e:
            print(f"  ❌ API失败(尝试{attempt+1}/3): {e}", flush=True)
            time.sleep(5)
    return None

def parse_entries(text, prefix, cat_id, cat_name, start_idx):
    clean = text.strip()
    if clean.startswith("```json"): clean = clean[7:]
    if clean.startswith("```"): clean = clean[3:]
    if clean.endswith("```"): clean = clean[:-3]
    clean = clean.strip()
    start = clean.find("[")
    end = clean.rfind("]") + 1
    if start < 0 or end <= start:
        return None
    try:
        entries = json.loads(clean[start:end])
        for i, e in enumerate(entries):
            idx = start_idx + i
            if not e.get("id"): e["id"] = f"{prefix}-{idx:03d}"
            if not e.get("category"): e["category"] = cat_id
            if not e.get("categoryName"): e["categoryName"] = cat_name
        return entries
    except json.JSONDecodeError:
        return None

def save_progress(filepath, existing, new_entries):
    """每批次后立即保存"""
    final = existing + new_entries
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)
    return final

def expand_category(cat_id, cat_name, prefix):
    filepath = os.path.join(OUT_DIR, f"{cat_id}.json")
    existing = []
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            existing = json.load(f)
    existing_count = len(existing)
    print(f"\n{'='*50}", flush=True)
    print(f"📚 {cat_name}: 已有 {existing_count} 条，目标 {TARGET_PER_CAT} 条", flush=True)
    print(f"{'='*50}", flush=True)
    if existing_count >= TARGET_PER_CAT:
        print(f"  ⏭️ 已达标，跳过", flush=True)
        return existing
    existing_titles = {e["title"] for e in existing}
    topics = EXPAND_TOPICS.get(cat_id, [])
    if not topics:
        print(f"  ⚠️ 无子话题列表，跳过", flush=True)
        return existing
    new_topics = [t for t in topics if t not in existing_titles]
    needed = TARGET_PER_CAT - existing_count
    print(f"  📝 需要新增 {needed} 条，可用子话题 {len(new_topics)} 个", flush=True)
    all_new = []
    batch_num = 0
    while len(all_new) < needed and new_topics:
        batch = new_topics[:BATCH_SIZE]
        new_topics = new_topics[BATCH_SIZE:]
        batch_num += 1
        start_idx = existing_count + len(all_new) + 1
        topics_text = "、".join(batch)
        system_prompt = f"""你是百科全书编辑。请为以下{cat_name}领域的{len(batch)}个词条生成百科内容。
⚠️ 铁律：内容必须准确真实，不能编造。用中文。直接输出JSON数组，不要代码块。
每个词条格式：{{"id":"{prefix}-{start_idx:03d}","title":"词条名","category":"{cat_id}","categoryName":"{cat_name}","summary":"一句话概述（30-60字）","content":"详细内容（150-300字）","keyFacts":["事实1","事实2","事实3"],"relatedIds":["其他词条id"],"funFact":"冷知识","importance":4}}
importance 1-5。relatedIds至少2个。不要生成已有词条。"""
        print(f"\n  🔄 批次 {batch_num}: {', '.join(batch[:5])}...", flush=True)
        result = call_mimo(system_prompt, f"请为以下{cat_name}词条生成百科内容：\n{topics_text}")
        if not result:
            print(f"  ❌ 批次 {batch_num} 失败，跳过", flush=True)
            continue
        entries = parse_entries(result, prefix, cat_id, cat_name, start_idx)
        if entries:
            new_entries = [e for e in entries if e["title"] not in existing_titles]
            for e in new_entries:
                existing_titles.add(e["title"])
            all_new.extend(new_entries)
            # ★ 每批次立即保存 ★
            save_progress(filepath, existing, all_new)
            print(f"  ✅ 批次 {batch_num}: 生成 {len(new_entries)} 条 (累计 {len(all_new)}/{needed}) 💾已保存", flush=True)
        else:
            print(f"  ❌ 批次 {batch_num}: JSON解析失败", flush=True)
        time.sleep(1)
    final = existing + all_new[:needed]
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)
    print(f"\n  💾 {cat_name}: {existing_count} → {len(final)} 条", flush=True)
    return final

def rebuild_index():
    all_entries = []
    for f in os.listdir(OUT_DIR):
        if f.endswith(".json") and f != "index.json":
            try:
                data = json.load(open(os.path.join(OUT_DIR, f)))
                all_entries.extend(data)
            except: pass
    index = [{"id": e["id"], "title": e["title"], "category": e["category"], "categoryName": e["categoryName"], "summary": e.get("summary", "")} for e in all_entries]
    with open(os.path.join(OUT_DIR, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"\n📋 索引已重建: {len(index)} 条", flush=True)

def main():
    cat = sys.argv[1] if len(sys.argv) > 1 else None
    categories = [
        ("biology", "生物", "bio"), ("history", "历史", "his"),
        ("technology", "科技", "tech"), ("military", "军事", "mil"),
        ("geography", "地理", "geo"), ("physics", "物理", "phy"),
        ("chemistry", "化学", "chem"), ("medicine", "医学", "med"),
        ("economics", "经济", "eco"), ("philosophy", "哲学", "phil"),
    ]
    if cat:
        for c in categories:
            if c[0] == cat:
                expand_category(*c)
                break
    else:
        for c in categories:
            try:
                expand_category(*c)
            except Exception as e:
                print(f"\n❌ {c[1]} 出错: {e}，继续下一个分类", flush=True)
    rebuild_index()
    total = 0
    for f in sorted(os.listdir(OUT_DIR)):
        if f.endswith(".json") and f != "index.json":
            data = json.load(open(os.path.join(OUT_DIR, f)))
            total += len(data)
            print(f"  📚 {f.replace('.json','')}: {len(data)} 条", flush=True)
    print(f"\n🎉 总计: {total} 条词条", flush=True)

if __name__ == "__main__":
    main()
