#!/usr/bin/env python3
"""
每日汽车新闻日报 JSON 生成器 (DeepSeek V4)
用法: python3 generate_daily_auto.py [--output 路径]
"""

import json, os, sys, subprocess, argparse, requests
from datetime import datetime

SITE_DIR = os.path.expanduser("~/.openclaw/workspace/dragonknightbeat-site")
JSON_PATH = os.path.join(SITE_DIR, "daily-auto.json")

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "sk-e08c986a456f4fed99d8250596e7f9e8")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-flash"


def call_deepseek(system_prompt, user_prompt, max_tokens=8000):
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        "max_tokens": max_tokens, "temperature": 0.7
    }
    try:
        resp = requests.post(f"{DEEPSEEK_BASE_URL}/chat/completions", headers=headers, json=payload, timeout=300)
        resp.raise_for_status()
        data = resp.json()
        print(f"📊 Token: 输入 {data['usage']['prompt_tokens']} | 输出 {data['usage']['completion_tokens']}")
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"❌ API 调用失败: {e}")
        return None


def generate():
    today = datetime.now().strftime("%Y-%m-%d")

    system_prompt = f"""你是一位专业的汽车新闻编辑。请生成今日汽车新闻日报，输出JSON格式。

严格输出JSON，结构如下：
{{
  "date": "{today}",
  "summary": "一句话概括今日汽车圈重点",
  "sections": [
    {{
      "id": "headline",
      "title": "今日头条",
      "icon": "📰",
      "articles": [
        {{
          "id": "auto-xxx",
          "title": "标题",
          "summary": "一句话摘要30-50字",
          "detail": "详细内容100-200字",
          "source": "来源"
        }}
      ]
    }}
  ]
}}

必须包含5个板块（按此顺序）：
1. 今日头条：当天最重磅的汽车新闻
2. 中国汽车市场：新车发布、政策动态（3篇）
3. 国际动态：国际车企、技术趋势（3篇）
4. 市场分析：销量数据、投资机会（2篇）
5. 明日展望：未来趋势预测（2篇）

要求：
- 所有内容基于最新真实汽车行业动态
- 每个板块 2-3 篇文章
- 语句专业、数据详实
- 来源标注真实媒体名称"""

    result = call_deepseek(system_prompt, f"请生成 {today} 的汽车新闻日报，共5个板块，12-15篇文章。", max_tokens=8000)
    if not result:
        return None

    clean = result.strip()
    if clean.startswith("```json"): clean = clean[7:]
    elif clean.startswith("```"): clean = clean[3:]
    if clean.endswith("```"): clean = clean[:-3]
    clean = clean.strip()

    js = clean.find("{")
    je = clean.rfind("}") + 1
    if js >= 0 and je > js:
        try:
            return json.loads(clean[js:je])
        except Exception as e:
            print(f"❌ JSON解析失败: {e}")
            print(clean[:500])
            return None
    return None


def git_push():
    try:
        os.chdir(SITE_DIR)
        subprocess.run(["git", "add", "-A"], capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", f"auto-update daily auto {datetime.now().strftime('%Y-%m-%d')}"], capture_output=True)
        r = subprocess.run(["git", "push", "origin", "gh-pages"], capture_output=True, text=True, timeout=30)
        if r.returncode == 0: print("✅ 已推送到 GitHub Pages")
        else: print(f"⚠️ {r.stderr[:200]}")
    except Exception as e: print(f"⚠️ {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=JSON_PATH, help=f"输出路径（默认 {JSON_PATH}）")
    args = parser.parse_args()

    print(f"🚗 生成 {datetime.now().strftime('%Y-%m-%d')} 汽车新闻日报（DeepSeek V4）...")
    content = generate()
    if content:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(content, f, ensure_ascii=False, indent=2)
        articles = sum(len(s.get("articles", [])) for s in content.get("sections", []))
        print(f"✅ 已写入: {args.output}")
        print(f"   板块: {len(content.get('sections', []))} 个 | 文章: {articles} 篇")
        git_push()
    else:
        print("❌ 生成失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
