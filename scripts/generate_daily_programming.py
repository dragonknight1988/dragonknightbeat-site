#!/usr/bin/env python3
"""每日编程学习 JSON 生成器 — GitHub Actions 版"""
import json, os, sys, re, requests
from datetime import datetime, timezone, timedelta

BJ_TZ = timezone(timedelta(hours=8))
today = datetime.now(BJ_TZ).strftime("%Y-%m-%d")
OUTPUT = os.environ.get("OUTPUT_DIR", ".") + "/daily-programming.json"
API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not API_KEY:
    print("❌ 未设置 DEEPSEEK_API_KEY"); sys.exit(1)

TECH_STACKS = ["Swift / SwiftUI", "Python", "JavaScript / TypeScript",
    "React / Next.js", "Node.js / Deno", "Go", "Rust",
    "Kotlin", "Flutter / Dart", "Git / DevOps"]
DIFFICULTIES = ["初级", "中级", "中级", "高级"]

def main():
    day_of_year = datetime.now().timetuple().tm_yday
    chosen = TECH_STACKS[day_of_year % len(TECH_STACKS)]
    diff = DIFFICULTIES[day_of_year % len(DIFFICULTIES)]
    print(f"💻 {chosen} | 难度: {diff}")

    sp = f"""你是一位经验丰富的编程导师。生成每日编程学习内容，专注：{chosen}，难度：{diff}
输出JSON（不要markdown代码块）：
{{"date":"{today}","contents":[{{"id":"prog-{today}","date":"{today}","title":"主题","summary":"概括","difficulty":"{diff}","concept":"核心概念详解3-6段","codeExample":{{"language":"语言","code":"可运行代码含注释","explanation":"解释"}},"keyPoints":["要点1","要点2","要点3","要点4","要点5"],"exercise":{{"description":"练习描述","hint":"提示","challenges":[{{"id":"ch-1","type":"fillBlank","question":"填空","codeContext":"...","segments":[{{"type":"text","content":"","placeholder":null,"options":null,"correctAnswer":null}},{{"type":"blank","content":null,"placeholder":"[选择]","options":["A","B"],"correctAnswer":"A"}}],"correctAnswer":"A","explanation":"解析"}},{{"id":"ch-2","type":"multipleChoice","question":"选择题","options":["A","B","C"],"correctAnswer":"A","explanation":"解析"}},{{"id":"ch-3","type":"codePrediction","question":"输出什么？","codeContext":"代码","options":["A","B"],"correctAnswer":"A","explanation":"解析"}}]}}]}}}}
要求：concept 有深度含工程经验，代码可直接运行，初级讲基础、中级讲应用、高级讲优化"""

    resp = requests.post("https://api.deepseek.com/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={"model": "deepseek-chat", "messages": [
            {"role": "system", "content": sp},
            {"role": "user", "content": f"生成以{chosen}为主题、难度{diff}的今日编程内容，日期：{today}"}
        ], "max_tokens": 6000, "temperature": 0.8}, timeout=300)
    resp.raise_for_status()
    result = resp.json()["choices"][0]["message"]["content"]

    clean = result.strip()
    for p in ["```json", "```"]:
        if clean.startswith(p): clean = clean[len(p):]
    if clean.endswith("```"): clean = clean[:-3]
    js = clean.find("{"); je = clean.rfind("}") + 1
    text = clean[js:je] if js >= 0 and je > js else clean

    for _ in range(3):
        try: data = json.loads(text); break
        except json.JSONDecodeError:
            text = re.sub(r',\s*\]', ']', text)
            text = re.sub(r',\s*\}', '}', text)
            text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
            try: data = json.loads(text); break
            except: print("❌ JSON解析失败"); sys.exit(1)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    title = data.get("contents", [{}])[0].get("title", "")
    print(f"✅ {OUTPUT} — {title}")

if __name__ == "__main__":
    main()
