#!/usr/bin/env python3
"""
每日新闻晨报 JSON 生成器 v3.0 — 真实新闻版
先从百度/必应抓取真实新闻，再让AI基于真实素材总结。
严禁AI编造内容。

用法: python3 generate_daily_news.py [--output 输出路径]
"""

import json, os, sys, subprocess, argparse, time, re
import requests
import traceback
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

BJ_TZ = timezone(timedelta(hours=8))

MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "tp-c6irsm5360gu18hd64hlmz47ltg54c5rbszghj45t5z96c31")
MIMO_BASE_URL = os.environ.get("MIMO_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1")
MIMO_MODEL = "xiaomi/mimo-v2.5-pro"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def fetch_baidu_news():
    """从百度热搜抓取新闻"""
    results = []
    try:
        # 百度热搜
        resp = requests.get("https://top.baidu.com/board?tab=realtime", headers=HEADERS, timeout=15)
        resp.encoding = "utf-8"
        text = resp.text
        # 提取热搜标题
        import re
        titles = re.findall(r'class="title[^\"]*"[^>]*>([^<]+)</', text)
        for t in titles[:30]:
            t = t.strip()
            if len(t) > 4 and "百度" not in t:
                results.append({"title": t, "source": "百度热搜"})
    except Exception as e:
        print(f"  ⚠️ 百度热搜失败: {e}")

    # 百度新闻搜索
    try:
        resp = requests.get("https://news.baidu.com/", headers=HEADERS, timeout=15)
        resp.encoding = "utf-8"
        text = resp.text
        titles = re.findall(r'<a[^>]*href="[^"]*"[^>]*>([^<]{8,60})</a>', text)
        seen = set()
        for t in titles:
            t = t.strip()
            if t not in seen and len(t) > 8 and "百度" not in t and "登录" not in t:
                seen.add(t)
                results.append({"title": t, "source": "百度新闻"})
                if len(results) >= 40:
                    break
    except Exception as e:
        print(f"  ⚠️ 百度新闻失败: {e}")

    return results


def fetch_bing_news():
    """从必应新闻抓取"""
    results = []
    try:
        resp = requests.get("https://cn.bing.com/news/search?q=今日新闻", headers=HEADERS, timeout=15)
        resp.encoding = "utf-8"
        text = resp.text
        import re
        # 必应新闻标题提取
        items = re.findall(r'<a[^>]*href="(https?://[^"]*)"[^>]*><h2[^>]*>([^<]+)</h2>', text)
        for url, title in items[:20]:
            title = title.strip()
            if len(title) > 4:
                results.append({"title": title, "source": "必应新闻", "url": url})
    except Exception as e:
        print(f"  ⚠️ 必应新闻失败: {e}")

    # 备用：必应中国新闻
    try:
        resp = requests.get("https://www.bing.com/news/search?q=%E4%BB%8A%E6%97%A5%E6%96%B0%E9%97%BB&cc=cn", headers=HEADERS, timeout=15)
        resp.encoding = "utf-8"
        text = resp.text
        items = re.findall(r'<a[^>]*href="(https?://[^"]*)"[^>]*><h2[^>]*>([^<]+)</h2>', text)
        for url, title in items[:15]:
            title = title.strip()
            if len(title) > 4:
                results.append({"title": title, "source": "必应国际", "url": url})
    except Exception as e:
        pass

    return results


def fetch_tencent_news():
    """从腾讯新闻抓取"""
    results = []
    try:
        resp = requests.get("https://news.qq.com/", headers=HEADERS, timeout=15)
        resp.encoding = "utf-8"
        text = resp.text
        import re
        titles = re.findall(r'<a[^>]*href="[^"]*"[^>]*title="([^"]{8,})"[^>]*>', text)
        seen = set()
        for t in titles:
            t = t.strip()
            if t not in seen and len(t) > 8:
                seen.add(t)
                results.append({"title": t, "source": "腾讯新闻"})
                if len(results) >= 20:
                    break
    except Exception as e:
        print(f"  ⚠️ 腾讯新闻失败: {e}")
    return results


def fetch_163_news():
    """从网易新闻抓取"""
    results = []
    try:
        resp = requests.get("https://news.163.com/", headers=HEADERS, timeout=15)
        resp.encoding = "utf-8"
        text = resp.text
        import re
        titles = re.findall(r'<a[^>]*href="[^"]*"[^>]*>([^<]{8,60})</a>', text)
        seen = set()
        for t in titles:
            t = t.strip()
            if t not in seen and len(t) > 8 and "网易" not in t:
                seen.add(t)
                results.append({"title": t, "source": "网易新闻"})
                if len(results) >= 20:
                    break
    except Exception as e:
        print(f"  ⚠️ 网易新闻失败: {e}")
    return results


def fetch_weibo_hot():
    """从微博热搜抓取"""
    results = []
    try:
        resp = requests.get("https://weibo.com/ajax/side/hotSearch", headers=HEADERS, timeout=15)
        data = resp.json()
        for item in data.get("data", {}).get("realtime", [])[:20]:
            word = item.get("word", "")
            if word:
                results.append({"title": word, "source": "微博热搜"})
    except Exception as e:
        print(f"  ⚠️ 微博热搜失败: {e}")
    return results


def fetch_all_news():
    """并发抓取所有新闻源"""
    print("🚀 开始多源并发抓取新闻...")
    all_news = []

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(fetch_baidu_news): "百度",
            executor.submit(fetch_bing_news): "必应",
            executor.submit(fetch_tencent_news): "腾讯",
            executor.submit(fetch_163_news): "网易",
            executor.submit(fetch_weibo_hot): "微博",
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                results = future.result()
                print(f"  ✅ {name} 获取 {len(results)} 条")
                all_news.extend(results)
            except Exception as e:
                print(f"  ❌ {name} 失败: {e}")

    # 去重
    seen = set()
    unique = []
    for item in all_news:
        key = item["title"][:15]
        if key not in seen:
            seen.add(key)
            unique.append(item)

    print(f"\n📊 汇总: 共获取 {len(unique)} 条去重新闻")
    return unique


def call_mimo(system_prompt, user_prompt, max_tokens=12000):
    """调用 MiMo API"""
    if not MIMO_API_KEY:
        print("❌ 未设置 MIMO_API_KEY")
        return None

    headers = {
        "Authorization": f"Bearer {MIMO_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MIMO_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "max_tokens": max_tokens,
        "temperature": 0.7
    }

    try:
        resp = requests.post(
            f"{MIMO_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=(15, 300)
        )
        resp.raise_for_status()
        data = resp.json()
        content = data['choices'][0]['message']['content']
        print(f"📝 API 原始输出长度: {len(content)} 字符")
        return content if content else None
    except requests.exceptions.Timeout as e:
        print(f"❌ API 调用超时: {e}")
        traceback.print_exc()
        return None
    except requests.exceptions.ConnectionError as e:
        print(f"❌ API 连接失败: {e}")
        traceback.print_exc()
        return None
    except Exception as e:
        print(f"❌ API 调用失败: {type(e).__name__}: {e}")
        traceback.print_exc()
        return None


def build_news_content():
    """构建当日新闻内容 — 基于真实抓取的新闻"""
    today = datetime.now(BJ_TZ).strftime("%Y-%m-%d")
    weekday_map = {0: "一", 1: "二", 2: "三", 3: "四", 4: "五", 5: "六", 6: "日"}
    weekday = weekday_map[datetime.now(BJ_TZ).weekday()]

    # 第一步：抓取真实新闻
    news_items = fetch_all_news()
    if len(news_items) < 5:
        print("⚠️ 抓取新闻太少，补充备用源...")
        # 备用：直接搜索
        try:
            resp = requests.get("https://top.baidu.com/board?tab=realtime", headers=HEADERS, timeout=15)
            import re
            titles = re.findall(r'class="title[^\"]*"[^>]*>([^<]+)</', resp.text)
            for t in titles[:20]:
                news_items.append({"title": t.strip(), "source": "百度备用"})
        except:
            pass

    # 构造新闻素材字符串
    news_text = "\n".join([f"- [{item['source']}] {item['title']}" for item in news_items[:50]])

    system_prompt = f"""你是一个资深新闻编辑。你的任务是【仅基于提供的真实新闻素材】进行分类和总结。

⚠️ 铁律（违反即失败）：
1. 只能使用下方「今日新闻素材」中提供的新闻，不得添加任何新事件
2. 不得编造具体数字（股指点位、成交额、药名、公司市值等）
3. 不得使用"某市""某公司""某专家"等模糊说法 — 如果原始素材没有具体名称，就不要编
4. summary/detail 必须忠实于原始标题的含义，不得歪曲或添加不存在的细节
5. 如果素材中某条新闻信息不足，summary 可以简短，但不能编造

请将素材分类整理为JSON，结构如下（直接输出JSON，不要代码块）：
{{
  "date": "{today}",
  "weekday": "星期{weekday}",
  "overview": "基于今日素材的一句话总评（20-40字，有洞察力）",
  "trendingTopics": ["从素材中提炼的5-8个热搜关键词"],
  "sections": [
    {{
      "id": "domestic",
      "title": "国内时政",
      "icon": "🇨🇳",
      "articles": [
        {{
          "id": "news-001",
          "title": "基于素材的新闻标题（不超过25字，可适当精炼原标题）",
          "summary": "基于素材的一句话摘要（30-50字），只包含素材中已有的信息",
          "detail": "基于素材的详细解读（2-4句话），只包含素材中已有的信息。信息不足时简短即可，不要编造",
          "impact": "影响分析（1-2句话），基于新闻本身的合理推断，不编造数据",
          "importance": "hot/important/normal",
          "tags": ["关键词1", "关键词2"]
        }}
      ]
    }}
  ]
}}

分类要求（每个分类3-5条，从素材中挑选最重要的）：
1. domestic — 🇨🇳 国内时政（政策、民生、基建、法治）
2. international — 🌍 国际时政（外交、冲突、国际组织）
3. finance — 📈 财经动态（股市、楼市、消费、企业）
4. tech — 💡 科技前沿（AI、芯片、新能源、互联网）
5. other — 📰 其他要闻（体育、文娱、社会、健康）

id格式: news-001 到 news-25，全局唯一
importance: hot=头条级 / important=值得关注 / normal=一般"""

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        print(f"\n📡 API 调用第 {attempt}/{max_retries} 次...")
        result = call_mimo(system_prompt, f"以下是今天抓取的真实新闻素材，请基于此整理：\n\n{news_text}")
        if not result:
            print("❌ API 返回空，重试...")
            continue

        clean = result.strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        if clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        clean = clean.strip()

        json_start = clean.find("{")
        json_end = clean.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            json_str = clean[json_start:json_end]
            try:
                data = json.loads(json_str)
                # 后处理：修复AI可能输出的中文字段名
                field_map = {"标题": "title", "摘要": "summary", "详情": "detail",
                             "影响": "impact", "重要性": "importance", "标签": "tags"}
                for sec in data.get("sections", []):
                    for art in sec.get("articles", []):
                        for cn, en in field_map.items():
                            if cn in art and en not in art:
                                art[en] = art.pop(cn)
                data["date"] = today
                data["weekday"] = f"星期{weekday}"

                sections = data.get("sections", [])
                total = sum(len(s.get("articles", [])) for s in sections)
                if total == 0 or len(sections) < 3:
                    print(f"⚠️ 内容不完整（{total}条/{len(sections)}分类），重试...")
                    time.sleep(2)
                    continue

                if not data.get("overview"):
                    data["overview"] = f"今日共 {total} 条新闻，涵盖国内外时政、财经、科技等领域。"
                if not data.get("trendingTopics"):
                    data["trendingTopics"] = []

                # 检查是否有"某市""某公司"等模糊词
                bad_count = 0
                for s in sections:
                    for a in s.get("articles", []):
                        text = a.get("title", "") + a.get("summary", "") + a.get("detail", "")
                        if "某市" in text or "某公司" in text or "某专家" in text:
                            bad_count += 1
                if bad_count > 0:
                    print(f"⚠️ 发现 {bad_count} 处模糊表述，重试...")
                    time.sleep(2)
                    continue

                print(f"✅ JSON 解析成功: {total} 条新闻 / {len(sections)} 个分类")
                print(f"📝 overview: {data['overview'][:60]}...")
                print(f"🔥 热搜: {', '.join(data['trendingTopics'][:5])}")
                return data
            except json.JSONDecodeError as e:
                print(f"❌ JSON 解析失败 (attempt {attempt}): {e}")
                if attempt < max_retries:
                    print(f"   输出前200字: {json_str[:200]}")
                    time.sleep(2)
                continue

    print("❌ 重试耗尽，新闻内容生成失败")
    return None


def git_push():
    """推送到 GitHub Pages"""
    site_dir = "/opt/dragonknightbeat-site"
    try:
        os.chdir(site_dir)
        subprocess.run(["git", "add", "-A"], capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", f"auto-update daily news v3 {datetime.now(BJ_TZ).strftime('%Y-%m-%d')}"], capture_output=True)
        result = subprocess.run(["git", "push", "origin", "gh-pages"], capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print("✅ 已推送到 GitHub Pages")
        else:
            print(f"⚠️ 推送结果: {result.stderr[:200]}")
    except Exception as e:
        print(f"⚠️ 推送异常: {e}")


def main():
    parser = argparse.ArgumentParser(description="生成每日新闻晨报 JSON v3.0")
    parser.add_argument("--output", default="/var/www/dragonknightbeat.com/daily-news.json")
    args = parser.parse_args()

    print(f"📰 生成 {datetime.now(BJ_TZ).strftime('%Y-%m-%d')} 新闻晨报 v3.0（真实新闻版）...")
    print(f"🔑 API Key: {'已设置' if MIMO_API_KEY else '未设置'}")

    content = build_news_content()
    if content:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(content, f, ensure_ascii=False, indent=2)
        sections = content.get("sections", [])
        total = sum(len(s.get("articles", [])) for s in sections)
        print(f"\n✅ 已写入: {args.output}")
        print(f"   共 {total} 条新闻，{len(sections)} 个分类")
        for s in sections:
            print(f"   {s.get('icon', '')} {s.get('title', '')}: {len(s.get('articles', []))} 条")
        git_push()
    else:
        print("❌ 生成失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
