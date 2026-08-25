#!/usr/bin/env python3
"""批量生成百科词条JSON — 在ECS上运行"""
import json, os, sys, time, requests

API_KEY = "tp-c6irsm5360gu18hd64hlmz47ltg54c5rbszghj45t5z96c31"
BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
MODEL = "xiaomi/mimo-v2.5-pro"
OUT_DIR = "/opt/dragonknightbeat-site/encyclopedia"

CATEGORIES = [
    ("biology", "生物", "bio", ["恐龙", "DNA", "光合作用", "进化论", "细胞", "基因编辑", "病毒", "细菌", "生态系统", "灭绝事件", "珊瑚礁", "候鸟迁徙", "深海生物", "蜜蜂", "恐龙灭绝", "人类起源", "克隆技术", "微生物", "植物分类", "动物行为"]),
    ("history", "历史", "his", ["秦始皇", "罗马帝国", "文艺复兴", "工业革命", "丝绸之路", "法国大革命", "二战", "冷战", "郑和下西洋", "古埃及", "蒙古帝国", "美国独立", "明治维新", "一战", "大航海时代", "印刷术", "火药发明", "黑死病", "启蒙运动", "辛亥革命"]),
    ("technology", "科技", "tech", ["人工智能", "量子计算", "区块链", "5G", "火箭技术", "半导体", "互联网", "3D打印", "机器人", "虚拟现实", "自动驾驶", "基因测序", "太阳能", "风力发电", "超级计算机", "卫星导航", "激光技术", "核聚变", "生物芯片", "物联网"]),
    ("military", "军事", "mil", ["航空母舰", "核武器", "隐形战斗机", "坦克", "潜艇", "导弹防御系统", "无人机", "特种部队", "信息战", "电子战", "战略轰炸机", "洲际导弹", "军事卫星", "网络战", "生物武器", "化学武器", "防空系统", "两栖作战", "后勤补给", "军事战略"]),
    ("geography", "地理", "geo", ["喜马拉雅山脉", "亚马逊河", "撒哈拉沙漠", "大堡礁", "马里亚纳海沟", "尼罗河", "北极", "南极洲", "东非大裂谷", "地中海", "太平洋", "珠穆朗玛峰", "死海", "维多利亚瀑布", "黄石公园", "冰岛", "巴拿马运河", "苏伊士运河", "黑森林", "大峡谷"]),
    ("physics", "物理", "phy", ["相对论", "量子力学", "黑洞", "引力波", "超导", "暗物质", "反物质", "核裂变", "核聚变", "光电效应", "波粒二象性", "不确定性原理", "热力学定律", "电磁感应", "弦理论", "希格斯玻色子", "宇宙大爆炸", "中子星", "暗能量", "熵"]),
    ("chemistry", "化学", "chem", ["元素周期表", "化学键", "酸碱反应", "氧化还原", "有机化学", "催化剂", "电解", "聚合物", "纳米材料", "石墨烯", "碳60", "蛋白质折叠", "酶", "化学平衡", "电化学", "光化学", "超临界流体", "分子筛", "手性分子", "生物降解"]),
    ("medicine", "医学", "med", ["青霉素", "疫苗", "基因疗法", "器官移植", "微创手术", "CT扫描", "核磁共振", "心脏支架", "人工心脏", "干细胞", "免疫疗法", "mRNA疫苗", "远程医疗", "手术机器人", "血液透析", "抗生素", "麻醉术", "X射线", "基因诊断", "精准医疗"]),
    ("economics", "经济", "eco", ["供需关系", "通货膨胀", "GDP", "股票市场", "央行", "货币政策", "国际贸易", "汇率", "经济周期", "垄断", "机会成本", "边际效用", "凯恩斯主义", "自由市场", "计划经济", "混合经济", "数字货币", "量化宽松", "债务危机", "经济全球化"]),
    ("philosophy", "哲学", "phil", ["苏格拉底", "柏拉图", "亚里士多德", "康德", "黑格尔", "尼采", "存在主义", "唯物主义", "唯心主义", "辩证法", "逻辑学", "伦理学", "美学", "认识论", "形而上学", "功利主义", "社会契约论", "虚无主义", "实用主义", "现象学"]),
]

def call_mimo(system_prompt, user_prompt):
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "max_tokens": 8000,
        "temperature": 0.7
    }
    try:
        resp = requests.post(f"{BASE_URL}/chat/completions", headers=headers, json=payload, timeout=300)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        print(f"  📝 Token: {usage.get('total_tokens', '?')}")
        return content
    except Exception as e:
        print(f"  ❌ API失败: {e}")
        return None

def generate_category(cat_id, cat_name, prefix, topics):
    print(f"\n{'='*50}")
    print(f"📚 生成分类: {cat_name} ({cat_id})")
    print(f"{'='*50}")
    
    system_prompt = f"""你是百科全书编辑。请为以下{cat_name}领域的{len(topics)}个词条生成百科内容。

⚠️ 铁律：
1. 内容必须准确真实，不能编造
2. 用中文
3. 直接输出JSON数组，不要代码块
4. 每个词条格式：
{{
  "id": "{prefix}-001",
  "title": "词条名",
  "category": "{cat_id}",
  "categoryName": "{cat_name}",
  "summary": "一句话概述（30-60字）",
  "content": "详细内容（150-300字）",
  "keyFacts": ["事实1", "事实2", "事实3"],
  "relatedIds": ["其他词条id"],
  "funFact": "一个有趣的冷知识",
  "era": "相关时代（可选）",
  "importance": 4
}}

importance: 1-5（5最重要）
id格式: {prefix}-001 到 {prefix}-{len(topics):02d}
relatedIds: 至少引用2个同分类或跨分类的词条id"""

    topics_text = "、".join(topics)
    result = call_mimo(system_prompt, f"请为以下{cat_name}词条生成百科内容：\n{topics_text}")
    
    if not result:
        print(f"  ❌ {cat_name} 生成失败")
        return None
    
    # 清理JSON
    clean = result.strip()
    if clean.startswith("```json"): clean = clean[7:]
    if clean.startswith("```"): clean = clean[3:]
    if clean.endswith("```"): clean = clean[:-3]
    clean = clean.strip()
    
    # 找到JSON数组
    start = clean.find("[")
    end = clean.rfind("]") + 1
    if start < 0 or end <= start:
        print(f"  ❌ 未找到JSON数组")
        print(f"  前200字: {clean[:200]}")
        return None
    
    try:
        entries = json.loads(clean[start:end])
        # 补齐ID
        for i, e in enumerate(entries):
            if not e.get("id"):
                e["id"] = f"{prefix}-{i+1:02d}"
            if not e.get("category"):
                e["category"] = cat_id
            if not e.get("categoryName"):
                e["categoryName"] = cat_name
        
        print(f"  ✅ 生成 {len(entries)} 个词条")
        return entries
    except json.JSONDecodeError as e:
        print(f"  ❌ JSON解析失败: {e}")
        print(f"  前200字: {clean[start:start+200]}")
        return None

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    
    # 检查已有文件
    existing = {}
    for f in os.listdir(OUT_DIR) if os.path.exists(OUT_DIR) else []:
        if f.endswith(".json") and f != "index.json":
            try:
                data = json.load(open(os.path.join(OUT_DIR, f)))
                existing[f.replace(".json", "")] = len(data)
            except:
                pass
    
    if existing:
        print(f"已有数据: {existing}")
    
    all_entries = []
    results = {}
    
    for cat_id, cat_name, prefix, topics in CATEGORIES:
        if cat_id in existing and existing[cat_id] >= 15:
            print(f"\n⏭️ 跳过 {cat_name}（已有 {existing[cat_id]} 个词条）")
            data = json.load(open(os.path.join(OUT_DIR, f"{cat_id}.json")))
            all_entries.extend(data)
            continue
        
        entries = generate_category(cat_id, cat_name, prefix, topics)
        if entries:
            # 保存分类文件
            filepath = os.path.join(OUT_DIR, f"{cat_id}.json")
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(entries, f, ensure_ascii=False, indent=2)
            print(f"  💾 已保存: {filepath}")
            all_entries.extend(entries)
            results[cat_name] = len(entries)
        
        time.sleep(2)  # 避免API限流
    
    # 生成索引
    index = []
    for e in all_entries:
        index.append({
            "id": e["id"],
            "title": e["title"],
            "category": e["category"],
            "categoryName": e["categoryName"],
            "summary": e.get("summary", "")
        })
    
    index_path = os.path.join(OUT_DIR, "index.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"\n📋 索引已保存: {index_path} ({len(index)} 条)")
    
    print(f"\n{'='*50}")
    print(f"🎉 全部完成！共 {len(all_entries)} 个词条")
    for name, count in results.items():
        print(f"  📚 {name}: {count} 个")

if __name__ == "__main__":
    main()
