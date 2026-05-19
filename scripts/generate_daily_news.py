#!/usr/bin/env python3
"""
每日新闻晨报 JSON 生成器
用法: python3 generate_daily_news.py [--output 输出路径]
默认输出到当前目录的 daily-news.json

适配 GitHub Actions 运行，API Key 从环境变量读取。
"""

import json, os, sys, argparse, time, requests
from datetime import datetime

# DeepSeek API 配置（API Key 从环境变量读取）
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = "deepseek-reasoner"


def call_deepseek(system_prompt, user_prompt, max_tokens=8192):
    """调用 DeepSeek API 生成内容"""
    if not DEEPSEEK_API_KEY:
        print("❌ 未设置 DEEPSEEK_API_KEY 环境变量")
        return None

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "max_tokens": max_tokens,
        "temperature": 0.7
    }

    try:
        resp = requests.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=300  # reasoner 可能较慢
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        print(f"📝 API 原始输出长度: {len(content)} 字符")
        # 打印 token 用量
        usage = data.get("usage", {})
        if usage:
            print(f"📊 Token: 输入 {usage.get('prompt_tokens', '?')} | 输出 {usage.get('completion_tokens', '?')} | 总计 {usage.get('total_tokens', '?')}")
        return content
    except Exception as e:
        print(f"❌ API 调用失败: {e}")
        return None


def build_news_content():
    """构建当日新闻内容，带重试机制"""
    today = datetime.now().strftime("%Y-%m-%d")

    system_prompt = """你是一个专业的新闻编辑。根据你的知识，生成 5 个分类的今日新闻摘要。
要求：
- 每个分类 3-5 条新闻
- 每条新闻包含标题和 1-2 句简短描述
- 语言简洁、客观、新闻用语规范
- 输出格式为 JSON，严格符合以下结构，不要使用markdown代码块包裹，直接输出JSON：
{
  "date": "2026-05-17",
  "sections": [
    {
      "id": "domestic",
      "title": "国内时政",
      "icon": "🇨🇳",
      "articles": [
        {
          "id": "news-001",
          "title": "...",
          "summary": "..."
        }
      ]
    }
  ]
}

分类：domestic(国内时政), international(国际时政), finance(财经动态), tech(科技前沿), other(其他要闻)
注意：id 需全局唯一，articles不能为空"""

    # 重试最多 3 次
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        print(f"\n📡 API 调用第 {attempt}/{max_retries} 次...")
        result = call_deepseek(
            system_prompt,
            f"今天是{today}。请根据你的知识生成今日新闻简报JSON，确保完整输出，不要截断。"
        )
        if not result:
            print("❌ API 返回空，重试...")
            continue

        # 提取 JSON：先尝试去掉 markdown 代码块标记
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
                data["date"] = today
                # 校验 sections
                sections = data.get("sections", [])
                total = sum(len(s.get("articles", [])) for s in sections)
                if total == 0 or len(sections) < 3:
                    print(f"⚠️  新闻内容不完整（{total}条/{len(sections)}分类），重试...")
                    time.sleep(2)
                    continue
                print(f"✅ JSON 解析成功: {total} 条新闻 / {len(sections)} 个分类")
                return data
            except json.JSONDecodeError as e:
                print(f"❌ JSON 解析失败 (attempt {attempt}): {e}")
                if attempt < max_retries:
                    print(f"   输出前200字: {json_str[:200]}")
                    time.sleep(2)
                continue
        else:
            print(f"❌ 未找到 JSON (attempt {attempt})")
            if attempt < max_retries:
                print(f"   输出前200字: {result[:200]}")
                time.sleep(2)
            continue

    print("❌ 重试耗尽，新闻内容生成失败")
    return None


def main():
    parser = argparse.ArgumentParser(description="生成每日新闻晨报 JSON")
    parser.add_argument("--output", default="daily-news.json",
                        help="输出文件路径（默认 daily-news.json）")
    args = parser.parse_args()

    print(f"📰 生成 {datetime.now().strftime('%Y-%m-%d')} 新闻晨报（DeepSeek）...")
    print(f"🔑 API Key: {'已设置' if DEEPSEEK_API_KEY else '未设置'}")

    content = build_news_content()
    if content:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(content, f, ensure_ascii=False, indent=2)
        sections = content.get("sections", [])
        total = sum(len(s.get("articles", [])) for s in sections)
        print(f"✅ 已写入: {args.output}")
        print(f"   共 {total} 条新闻，{len(sections)} 个分类")
        for s in sections:
            print(f"   {s.get('icon', '')} {s.get('title', '')}: {len(s.get('articles', []))} 条")
    else:
        print("❌ 生成失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
