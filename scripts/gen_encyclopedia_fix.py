#!/usr/bin/env python3
"""补生成失败的百科分类 — 分两批各10个词条"""
import json, os, time, requests

API_KEY = "tp-c6irsm5360gu18hd64hlmz47ltg54c5rbszghj45t5z96c31"
BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
MODEL = "xiaomi/mimo-v2.5-pro"
OUT_DIR = "/opt/dragonknightbeat-site/encyclopedia"

FAILED = [
    ("technology", "科技", "tech", 
     ["人工智能", "量子计算", "区块链", "5G", "火箭技术", "半导体", "互联网", "3D打印", "机器人", "虚拟现实"],
     ["自动驾驶", "基因测序", "太阳能", "风力发电", "超级计算机", "卫星导航", "激光技术", "核聚变", "生物芯片", "物联网"]),
    ("geography", "地理", "geo",
     ["喜马拉雅山脉", "亚马逊河", "撒哈拉沙漠", "大堡礁", "马里亚纳海沟", "尼罗河", "北极", "南极洲", "东非大裂谷", "地中海"],
     ["太平洋", "珠穆朗玛峰", "死海", "维多利亚瀑布", "黄石公园", "冰岛", "巴拿马运河", "苏伊士运河", "黑森林", "大峡谷"]),
    ("physics", "物理", "phy",
     ["相对论", "量子力学", "黑洞", "引力波", "超导", "暗物质", "反物质", "核裂变", "核聚变", "光电效应"],
     ["波粒二象性", "不确定性原理", "热力学定律", "电磁感应", "弦理论", "希格斯玻色子", "宇宙大爆炸", "中子星", "暗能量", "熵"]),
    ("chemistry", "化学", "chem",
     ["元素周期表", "化学键", "酸碱反应", "氧化还原", "有机化学", "催化剂", "电解", "聚合物", "纳米材料", "石墨烯"],
     ["碳60", "蛋白质折叠", "酶", "化学平衡", "电化学", "光化学", "超临界流体", "分子筛", "手性分子", "生物降解"]),
    ("economics", "经济", "eco",
     ["供需关系", "通货膨胀", "GDP", "股票市场", "央行", "货币政策", "国际贸易", "汇率", "经济周期", "垄断"],
     ["机会成本", "边际效用", "凯恩斯主义", "自由市场", "计划经济", "混合经济", "数字货币", "量化宽松", "债务危机", "经济全球化"]),
]

def call_mimo(system_prompt, user_prompt):
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {"model": MODEL, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], "max_tokens": 8000, "temperature": 0.7}
    try:
        resp = requests.post(f"{BASE_URL}/chat/completions", headers=headers, json=payload, timeout=300)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"  ❌ {e}")
        return None

def gen_batch(cat_id, cat_name, prefix, topics, start_idx):
    system_prompt = f"""你是百科全书编辑。为以下{len(topics)}个{cat_name}词条生成百科。
直接输出JSON数组，不要代码块。
每个格式: {{"id":"{prefix}-{start_idx:02d}","title":"...","category":"{cat_id}","categoryName":"{cat_name}","summary":"30-60字","content":"150-250字","keyFacts":["fact1","fact2","fact3"],"relatedIds":["{prefix}-001"],"funFact":"冷知识","importance":4}}
id从{prefix}-{start_idx:02d}到{prefix}-{start_idx+len(topics)-1:02d}。内容准确真实。"""
    
    result = call_mimo(system_prompt, "、".join(topics))
    if not result: return None
    
    clean = result.strip()
    if clean.startswith("```json"): clean = clean[7:]
    if clean.startswith("```"): clean = clean[3:]
    if clean.endswith("```"): clean = clean[:-3]
    clean = clean.strip()
    
    s = clean.find("[")
    e = clean.rfind("]") + 1
    if s < 0 or e <= s: return None
    
    try:
        return json.loads(clean[s:e])
    except json.JSONDecodeError:
        # 尝试修复常见JSON错误
        raw = clean[s:e]
        # 修复尾部逗号
        raw = raw.replace(",]", "]").replace(",}", "}")
        # 修复缺失的逗号（在}后面紧跟"的情况）
        import re
        raw = re.sub(r'}\s*"', '}, "', raw)
        try:
            return json.loads(raw)
        except:
            print(f"  ❌ 修复后仍解析失败")
            return None

def main():
    all_entries = []
    
    # 加载已有数据
    for f in os.listdir(OUT_DIR):
        if f.endswith(".json") and f != "index.json":
            data = json.load(open(os.path.join(OUT_DIR, f)))
            all_entries.extend(data)
    
    for cat_id, cat_name, prefix, batch1, batch2 in FAILED:
        filepath = os.path.join(OUT_DIR, f"{cat_id}.json")
        if os.path.exists(filepath):
            existing = json.load(open(filepath))
            if len(existing) >= 18:
                print(f"⏭️ 跳过 {cat_name}（已有 {len(existing)} 个）")
                continue
        
        print(f"\n📚 {cat_name} - 批次1")
        e1 = gen_batch(cat_id, cat_name, prefix, batch1, 1)
        time.sleep(2)
        
        print(f"📚 {cat_name} - 批次2")
        e2 = gen_batch(cat_id, cat_name, prefix, batch2, 11)
        time.sleep(2)
        
        entries = []
        if e1: entries.extend(e1)
        if e2: entries.extend(e2)
        
        if entries:
            for i, e in enumerate(entries):
                if not e.get("id"): e["id"] = f"{prefix}-{i+1:02d}"
                if not e.get("category"): e["category"] = cat_id
                if not e.get("categoryName"): e["categoryName"] = cat_name
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(entries, f, ensure_ascii=False, indent=2)
            print(f"  ✅ {len(entries)} 个词条已保存")
            all_entries.extend(entries)
        else:
            print(f"  ❌ {cat_name} 全部失败")
    
    # 重建索引
    index = [{"id": e["id"], "title": e["title"], "category": e["category"], "categoryName": e["categoryName"], "summary": e.get("summary", "")} for e in all_entries]
    with open(os.path.join(OUT_DIR, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"\n📋 索引: {len(index)} 条")

if __name__ == "__main__":
    main()
