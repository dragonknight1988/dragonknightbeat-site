#!/usr/bin/env python3
"""
每日汽车新闻日报 JSON 生成器 v2.0 (多源新闻 + MiMo Pro)
用法: python3 generate_daily_auto.py [--output 路径]

改进点：
- 多源新闻抓取（百度新闻、搜狗新闻、36氪、网易、腾讯等）
- 过滤非汽车内容，只保留相关新闻
- 优化 MiMo prompt，提升内容质量
- 来源标注更精确
"""

import json, os, sys, argparse, re, requests, re, time
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

BJ_TZ = timezone(timedelta(hours=8))

SITE_DIR = os.path.expanduser("~/.openclaw/workspace/dragonknightbeat-site")
JSON_PATH = os.path.join(SITE_DIR, "daily-auto.json")

MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "tp-c6irsm5360gu18hd64hlmz47ltg54c5rbszghj45t5z96c31")
MIMO_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
MIMO_MODEL = "xiaomi/mimo-v2.5-pro"  # 升级到旗舰模型

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
HEADERS = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}

# 汽车关键词过滤
AUTO_KEYWORDS = [
    "汽车", "新车", "车企", "电动车", "新能源", "燃油车", "混动", "纯电",
    "特斯拉", "比亚迪", "蔚来", "小鹏", "理想", "华为", "小米汽车", "问界",
    "奔驰", "宝马", "奥迪", "大众", "丰田", "本田", "日产", "福特",
    "吉利", "长城", "长安", "广汽", "上汽", "一汽", "奇瑞",
    "销量", "交付", "上市", "发布", "预售", "补贴", "充电桩", "电池",
    "自动驾驶", "智能驾驶", "智驾", "L2", "L3", "OTA",
    "二手车", "召回", "碰撞", "安全", "碰撞测试",
    "电池", "固态电池", "磷酸铁锂", "三元锂", "续航", "充电",
    "降价", "涨价", "价格战", "补贴", "购置税", "限行", "限购",
    "SUV", "MPV", "轿车", "皮卡", "超跑",
    "宁德时代", "华为", "英伟达", "高通", "地平线",
]


def is_auto_related(text):
    """判断新闻是否与汽车相关"""
    text_lower = text.lower()
    for kw in AUTO_KEYWORDS:
        if kw in text_lower:
            return True
    return False


def clean_html(text):
    """清理HTML标签"""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&[a-zA-Z]+;', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def call_mimo(system_prompt, user_prompt, max_tokens=8000):
    headers = {"Authorization": f"Bearer {MIMO_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": MIMO_MODEL,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        "max_tokens": max_tokens, "temperature": 0.6
    }
    try:
                resp = requests.post(f"{MIMO_BASE_URL}/chat/completions", headers=headers, json=payload, timeout=(15, 180), stream=True)
        resp.raise_for_status()
        import json as _json
        chunks = []
        for chunk in resp.iter_content(chunk_size=None):
            if chunk:
                chunks.append(chunk)
        raw = b"".join(chunks).decode("utf-8")
        data = _json.loads(raw)        usage = data.get("usage", {})
        if usage:
            print(f"📊 Token: 输入 {usage.get('prompt_tokens','?')} | 输出 {usage.get('completion_tokens','?')}")
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"❌ API 调用失败: {e}")
        return None


# ======================== 多源新闻抓取 ========================

def fetch_baidu_auto_news(max_items=20):
    """从百度新闻搜索抓取汽车新闻"""
    print("📰 [百度新闻] 正在抓取汽车新闻...")
    results = []
    queries = ["汽车新闻", "新能源汽车", "电动汽车 最新"]
    for q in queries:
        try:
            url = f"https://www.baidu.com/s?tn=news&rtt=1&bsst=1&cl=2&wd={q}&t={int(time.time()*1000)}"
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.encoding = "utf-8"
            # 提取新闻标题和来源
            pattern = r'<a[^>]*href="[^"]*"[^>]*>(.*?)</a>.*?<span[^>]*class="[^"]*c-color-gray[^"]*"[^>]*>(.*?)</span>'
            matches = re.findall(pattern, r.text, re.DOTALL)
            for title_html, source_html in matches:
                title = clean_html(title_html).strip()
                source = clean_html(source_html).strip()
                if title and len(title) > 8 and is_auto_related(title):
                    results.append({"title": title, "source": source or "百度新闻"})
        except Exception as e:
            print(f"  ⚠️ 百度新闻 [{q}] 失败: {e}")
    # 去重
    seen = set()
    unique = []
    for r in results:
        if r["title"] not in seen:
            seen.add(r["title"])
            unique.append(r)
    print(f"  ✅ 百度新闻获取 {len(unique)} 条")
    return unique[:max_items]


def fetch_sogou_auto_news(max_items=15):
    """从搜狗新闻抓取汽车新闻"""
    print("📰 [搜狗新闻] 正在抓取汽车新闻...")
    results = []
    try:
        url = "https://news.sogou.com/news?query=汽车+新能源&sort=1"
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.encoding = "utf-8"
        # 搜狗新闻标题提取
        titles = re.findall(r'<h3[^>]*>.*?<a[^>]*>(.*?)</a>', r.text, re.DOTALL)
        for t in titles:
            title = clean_html(t).strip()
            if title and len(title) > 8 and is_auto_related(title):
                results.append({"title": title, "source": "搜狗新闻"})
    except Exception as e:
        print(f"  ⚠️ 搜狗新闻失败: {e}")
    seen = set()
    unique = []
    for r in results:
        if r["title"] not in seen:
            seen.add(r["title"])
            unique.append(r)
    print(f"  ✅ 搜狗新闻获取 {len(unique)} 条")
    return unique[:max_items]


def fetch_36kr_auto(max_items=10):
    """从36氪抓取汽车相关新闻"""
    print("📰 [36氪] 正在抓取汽车新闻...")
    results = []
    try:
        url = "https://36kr.com/newsflashes"
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.encoding = "utf-8"
        # 36氪快讯提取
        items = re.findall(r'"title":"(.*?)"', r.text)
        for t in items:
            title = t.encode().decode('unicode_escape', errors='ignore')
            if is_auto_related(title):
                results.append({"title": title, "source": "36氪"})
    except Exception as e:
        print(f"  ⚠️ 36氪失败: {e}")
    print(f"  ✅ 36氪获取 {len(results)} 条")
    return results[:max_items]


def fetch_tencent_auto_news(max_items=10):
    """从腾讯新闻抓取汽车新闻"""
    print("📰 [腾讯新闻] 正在抓取汽车新闻...")
    results = []
    try:
        url = "https://news.qq.com/route/a/list?channel=auto&page=0"
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.encoding = "utf-8"
        titles = re.findall(r'"title":"(.*?)"', r.text)
        for t in titles:
            if is_auto_related(t):
                results.append({"title": t, "source": "腾讯汽车"})
    except Exception as e:
        print(f"  ⚠️ 腾讯新闻失败: {e}")
    print(f"  ✅ 腾讯新闻获取 {len(results)} 条")
    return results[:max_items]


def fetch_163_auto(max_items=10):
    """从网易新闻抓取汽车新闻"""
    print("📰 [网易新闻] 正在抓取汽车新闻...")
    results = []
    try:
        url = "https://auto.163.com/"
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.encoding = "utf-8"
        titles = re.findall(r'<a[^>]*href="[^"]*"[^>]*title="([^"]+)"', r.text)
        for t in titles:
            if is_auto_related(t) and len(t) > 8:
                results.append({"title": t, "source": "网易汽车"})
    except Exception as e:
        print(f"  ⚠️ 网易新闻失败: {e}")
    seen = set()
    unique = []
    for r in results:
        if r["title"] not in seen:
            seen.add(r["title"])
            unique.append(r)
    print(f"  ✅ 网易新闻获取 {len(unique)} 条")
    return unique[:max_items]


def fetch_weibo_auto_hot(max_items=10):
    """从微博热搜抓取汽车相关话题"""
    print("📰 [微博热搜] 正在抓取汽车话题...")
    results = []
    try:
        url = "https://weibo.com/ajax/side/hotSearch"
        r = requests.get(url, headers=HEADERS, timeout=10)
        data = r.json()
        for item in data.get("data", {}).get("realtime", []):
            word = item.get("word", "")
            if is_auto_related(word):
                results.append({"title": word, "source": "微博热搜"})
    except Exception as e:
        print(f"  ⚠️ 微博热搜失败: {e}")
    print(f"  ✅ 微博热搜获取 {len(results)} 条")
    return results[:max_items]


def fetch_baidu_hot():
    """从百度热搜获取汽车相关热点"""
    print("📰 [百度热搜] 正在抓取...")
    results = []
    try:
        r = requests.get(
            "https://top.baidu.com/api/board?tab=realtime",
            headers={"User-Agent": UA, "Accept": "application/json", "Referer": "https://top.baidu.com/"},
            timeout=10
        )
        data = r.json()
        for item in data.get("data", {}).get("cards", [{}])[0].get("content", []):
            word = item.get("word", "") or item.get("query", "")
            if word and is_auto_related(word):
                results.append({"title": word, "source": "百度热搜"})
    except Exception as e:
        print(f"  ⚠️ 百度热搜失败: {e}")
    print(f"  ✅ 百度热搜获取 {len(results)} 条")
    return results


def fetch_all_news():
    """并发抓取所有新闻源"""
    print("🚀 开始多源并发抓取汽车新闻...\n")
    all_news = []

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(fetch_baidu_auto_news): "百度新闻",
            executor.submit(fetch_sogou_auto_news): "搜狗新闻",
            executor.submit(fetch_36kr_auto): "36氪",
            executor.submit(fetch_tencent_auto_news): "腾讯新闻",
            executor.submit(fetch_163_auto): "网易新闻",
            executor.submit(fetch_weibo_auto_hot): "微博热搜",
            executor.submit(fetch_baidu_hot): "百度热搜",
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                result = future.result()
                all_news.extend(result)
            except Exception as e:
                print(f"  ⚠️ {name} 抓取异常: {e}")

    # 最终去重
    seen = set()
    unique = []
    for item in all_news:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique.append(item)

    print(f"\n📊 汇总: 共获取 {len(unique)} 条去重汽车新闻")
    return unique


# ======================== 生成主体 ========================

def repair_articles(data):
    """修复 AI 生成的 JSON 中可能出现的字段名错误"""
    aliases = {"dynamic": "detail", "description": "detail", "content": "detail", "body": "detail"}
    fixed = 0
    for section in data.get("sections", []):
        for article in section.get("articles", []):
            for wrong, correct in aliases.items():
                if wrong in article and correct not in article:
                    article[correct] = article.pop(wrong)
                    fixed += 1
                    break
            for key in ["id", "title", "summary", "detail", "source"]:
                if key not in article:
                    article[key] = ""
    if fixed:
        print(f"🔧 修复了 {fixed} 个字段名错误")
    return data


def generate():
    today = datetime.now(BJ_TZ).strftime("%Y-%m-%d")
    weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][datetime.now(BJ_TZ).weekday()]

    # 多源抓取
    news_list = fetch_all_news()

    if len(news_list) < 5:
        print("⚠️ 新闻数量不足，尝试补充...")
        # 至少保证有一些内容
        news_list.extend([
            {"title": "新能源汽车市场持续增长", "source": "行业趋势"},
            {"title": "智能驾驶技术加速落地", "source": "行业趋势"},
        ])

    # 构建新闻上下文
    news_context = f"【{today} {weekday} 汽车新闻汇总（共{len(news_list)}条）】\n\n"
    for i, item in enumerate(news_list, 1):
        news_context += f"{i}. [{item['source']}] {item['title']}\n"

    system_prompt = f"""你是一位资深汽车新闻编辑，负责为汽车资讯App撰写每日新闻日报。

以下是今日从多个权威渠道（百度新闻、搜狗新闻、36氪、腾讯汽车、网易汽车、微博热搜、百度热搜）实时抓取的汽车相关新闻：

{news_context}

请基于以上真实新闻，撰写 {today}（{weekday}）的汽车新闻日报。

## 严格要求：
1. **只使用上面提供的真实新闻**，不得编造不存在的事件或数据
2. 每篇新闻必须标注具体来源（如"新浪汽车"、"36氪"等），不得写"综合自网络"
3. detail 字段必须有实质内容（150-250字），包含具体数据、公司名称、技术细节
4. summary 字段精炼一句话（20-40字），概括核心信息
5. 语言风格：专业、客观、有信息量，像真正的汽车记者写的
6. 严禁编造具体日期（如"6月1日发布"），如果不确定就写"近期"

## JSON结构：
{{
  "date": "{today}",
  "summary": "一句话概括今日汽车圈最重要的动态",
  "sections": [
    {{
      "id": "headline",
      "title": "今日头条",
      "icon": "📰",
      "articles": [{{"id": "auto-001", "title": "标题", "summary": "摘要", "detail": "详细内容", "impact": "影响分析", "source": "来源"}}]
    }}
  ]
}}

## 5个板块（按此顺序，每个板块的文章数按要求）：
1. **今日头条**（1篇）：当天最重磅的汽车新闻，详细展开
2. **中国汽车市场**（3-4篇）：国内车企动态、新车发布、政策变化、销量数据
3. **国际动态**（2-3篇）：国际车企新闻、海外政策、技术趋势
4. **市场分析**（2篇）：行业趋势分析、投资机会、市场数据解读
5. **明日展望**（1-2篇）：基于今日新闻的未来趋势预判

总共 10-12 篇文章。

## 字段说明：
- title：简洁有力的标题
- summary：一句话摘要
- detail：200-400字详细解读（背景、原因、意义）
- impact：50-100字影响分析（对行业/消费者/市场的具体影响）
- source：信息来源

直接输出JSON，不要任何markdown代码块标记。"""

    result = call_mimo(system_prompt, f"今天是{today}（{weekday}）。请基于以上{len(news_list)}条实时新闻，生成高质量的汽车新闻日报JSON。", max_tokens=10000)

    if not result:
        return None

    # 清理JSON
    clean = result.strip()
    clean = re.sub(r'^```\w*\s*', '', clean)
    clean = re.sub(r'\s*```\s*$', '', clean)
    clean = clean.strip()

    js = clean.find("{")
    je = clean.rfind("}") + 1
    if js >= 0 and je > js:
        try:
            data = json.loads(clean[js:je])
            data = repair_articles(data)
            return data
        except Exception as e:
            print(f"❌ JSON解析失败: {e}")
            print(clean[:500])
            return None
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=JSON_PATH, help=f"输出路径（默认 {JSON_PATH}）")
    args = parser.parse_args()

    today = datetime.now(BJ_TZ).strftime('%Y-%m-%d')
    weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][datetime.now(BJ_TZ).weekday()]
    print(f"🚗 生成 {today}（{weekday}）汽车新闻日报 v2.0（多源 + MiMo Pro）...\n")

    content = generate()
    if content:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(content, f, ensure_ascii=False, indent=2)
        articles = sum(len(s.get("articles", [])) for s in content.get("sections", []))
        print(f"\n✅ 已写入: {args.output}")
        print(f"   板块: {len(content.get('sections', []))} 个 | 文章: {articles} 篇")
        print(f"   摘要: {content.get('summary', 'N/A')}")
    else:
        print("❌ 生成失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
