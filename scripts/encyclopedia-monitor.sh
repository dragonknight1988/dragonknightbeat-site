#!/bin/bash
SRC="/opt/dragonknightbeat-site/encyclopedia"
WEB="/var/www/dragonknightbeat.com/encyclopedia"
STATUS_FILE="/var/log/dragonknightbeat/encyclopedia-status.json"
TARGET=500

RUNNING=$(ps aux | grep "encyclopedia-loop\|gen_encyclopedia_expand" | grep -v grep | wc -l)

python3 -c "
import json, os, glob, time
src = \"$SRC\"
target = $TARGET
cats = {}
total = 0; done = 0
for f in sorted(glob.glob(os.path.join(src, \"*.json\"))):
    name = os.path.basename(f).replace(\".json\", \"\")
    if name == \"index\": continue
    data = json.load(open(f))
    c = len(data)
    cats[name] = {\"count\": c, \"done\": c >= target}
    total += c
    if c >= target: done += 1
remaining = len(cats) - done
status = {\"time\": time.strftime(\"%Y-%m-%d %H:%M\"), \"total\": total, \"done\": done, \"remaining\": remaining, \"running\": $RUNNING > 0, \"cats\": cats}
with open(\"$STATUS_FILE\", \"w\") as f:
    json.dump(status, f, ensure_ascii=False, indent=2)
print(f\"📊 {done}/{len(cats)} 达标 | 总{total}条 | {\"运行中\" if status[\"running\"] else \"已完成\"}\")
for n,i in cats.items():
    m = \"✅\" if i[\"done\"] else \"⏳\"
    print(f\"  {m} {n}: {i[\"count\"]}/{target}\")
" 2>/dev/null
cp "$SRC"/*.json "$WEB"/ 2>/dev/null
