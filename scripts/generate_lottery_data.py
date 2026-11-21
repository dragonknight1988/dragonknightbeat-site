#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_lottery_data.py — DK 幸运号码系列（DKLotoJP / DKLotoKR / DKLotoUS）后端数据生成
生成 /var/www/dragonknightbeat.com/lottery/{ja,kr,us}/draws.json

Schema（与三端 App Codable 模型一致）：
{
  "date": "yyyy-MM-dd",          # 代码按各彩种时区强制写入当天真实值
  "locale": "ja|kr|us",
  "games": [
    {"key": "...", "name": "...",
     "latestDraw":  {"date": "yyyy-MM-dd", "numbers": [int], "bonus": [int]},
     "recentDraws": [{"date", "numbers", "bonus"}, ...]}   # 新→旧
  ]
}

数据源（均经 ECS 实测可达）：
- 日本: jsdelivr 镜像 tk030-lotto/lotto-data-hub（备源 zero-dev.jp）
- 韩国: Naver 搜索开奖组件（最新一期）+ jsdelivr 镜像 Frogbornwater/korea-lotto645-analyzer（历史）
        期号→日期公式：第 n 期 = 2002-12-07 + 7*(n-1) 天（与 App 端 LottoRound 完全一致）
- 美国: jsdelivr 镜像 jbaranski/jeffs-lottery-utils（每次开奖后自动更新的数据集）
        + lotteryusa.com 最新一期 SSR 叠加，备源 powerball.com/previous-results

兜底策略：任一彩种抓取失败 → 沿用上一次成功数据；校验不过的记录直接丢弃；
写盘前整体 schema 自检，失败不覆盖旧文件。
"""

import csv
import io
import json
import os
import re
import sys
import tempfile
import urllib.request
import urllib.error
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

WEBROOT = "/var/www/dragonknightbeat.com"
OUT_DIR = os.path.join(WEBROOT, "lottery")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

MAX_DRAWS = 100

LOG_PREFIX = "[lottery-gen]"


def log(*args):
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), LOG_PREFIX, *args, flush=True)


def fetch(url, timeout=25, retries=2):
    """HTTP GET，返回 str。失败抛异常（由调用方兜底）。"""
    last_err = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9,ja;q=0.8,ko;q=0.8",
            })
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            for enc in ("utf-8", "euc-kr", "cp949", "shift_jis"):
                try:
                    return raw.decode(enc)
                except UnicodeDecodeError:
                    continue
            return raw.decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            last_err = e
            log("fetch fail(%d) %s -> %s" % (i, url, e))
    raise RuntimeError("fetch failed: %s (%s)" % (url, last_err))


# ---------------------------------------------------------------- 校验规则

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# key -> (main_count, main_min, main_max, bonus_count, bonus_min, bonus_max, unique_main)
GAME_RULES = {
    "roto6":       (6, 1, 43, 1, 1, 43, True),
    "roto7":       (7, 1, 37, 2, 1, 37, True),
    "mini_loto":   (5, 1, 31, 1, 1, 31, True),
    "numbers3":    (3, 0, 9, 0, 0, 9, False),
    "numbers4":    (4, 0, 9, 0, 0, 9, False),
    "lotto645":    (6, 1, 45, 1, 1, 45, True),
    "powerball":   (5, 1, 69, 1, 1, 26, True),
    "mega-millions": (5, 1, 70, 1, 1, 25, True),
}


def valid_date(s):
    if not isinstance(s, str) or not DATE_RE.match(s):
        return False
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def valid_draw(key, d):
    """按 App 解码模型 + 玩法规则校验单条开奖记录。"""
    if not isinstance(d, dict):
        return False
    if not valid_date(d.get("date")):
        return False
    nums, bonus = d.get("numbers"), d.get("bonus")
    if not isinstance(nums, list) or not isinstance(bonus, list):
        return False
    rule = GAME_RULES.get(key)
    if rule is None:
        return False
    mc, mn, mx, bc, bmin, bmax, uniq = rule
    if len(nums) != mc or len(bonus) != bc:
        return False
    if any((not isinstance(n, int)) or n < mn or n > mx for n in nums):
        return False
    if uniq and len(set(nums)) != len(nums):
        return False
    if any((not isinstance(b, int)) or b < bmin or b > bmax for b in bonus):
        return False
    return True


def sanitize(key, draws):
    out, seen = [], set()
    for d in draws:
        if valid_draw(key, d) and d["date"] not in seen:
            seen.add(d["date"])
            out.append({
                "date": d["date"],
                "numbers": [int(n) for n in d["numbers"]],
                "bonus": [int(b) for b in d["bonus"]],
            })
    out.sort(key=lambda x: x["date"], reverse=True)
    return out[:MAX_DRAWS]


# ---------------------------------------------------------------- 日本

JP_GAMES = [
    ("roto6",     "ロト6",        "loto6"),
    ("roto7",     "ロト7",        "loto7"),
    ("mini_loto", "ミニロト",      "miniloto"),
    ("numbers3",  "ナンバーズ3",   "numbers3"),
    ("numbers4",  "ナンバーズ4",   "numbers4"),
]

JP_URLS = [
    "https://cdn.jsdelivr.net/gh/tk030-lotto/lotto-data-hub@main/data/%s.json",
    "https://zero-dev.jp/lotto-data-hub/data/%s.json",
    "https://raw.githubusercontent.com/tk030-lotto/lotto-data-hub/main/data/%s.json",
]


def fetch_jp_game(fname):
    """tk030-lotto/lotto-data-hub: [{round, date, numbers, bonus}] 新→旧"""
    for tpl in JP_URLS:
        try:
            text = fetch(tpl % fname)
            rows = json.loads(text)
            draws = [{
                "date": r.get("date", ""),
                "numbers": r.get("numbers", []),
                "bonus": r.get("bonus", []),
            } for r in rows if isinstance(r, dict)]
            log("jp/%s ok via %s (%d rows)" % (fname, tpl % fname, len(draws)))
            return draws
        except Exception as e:  # noqa: BLE001
            log("jp/%s source failed %s: %s" % (fname, tpl % fname, e))
    return None


def build_ja(prev_games):
    games = []
    for key, name, fname in JP_GAMES:
        draws = fetch_jp_game(fname)
        if draws is None:
            draws = prev_games.get(key, [])
            log("jp/%s FALLBACK to previous data" % key)
        merged = sanitize(key, draws + prev_games.get(key, []))
        entry = {"key": key, "name": name, "latestDraw": None, "recentDraws": merged}
        if merged:
            entry["latestDraw"] = merged[0]
        games.append(entry)
    return games


# ---------------------------------------------------------------- 韩国

KR_CSV_URLS = [
    "https://cdn.jsdelivr.net/gh/Frogbornwater/korea-lotto645-analyzer@main/data/lotto645.csv",
    "https://raw.githubusercontent.com/Frogbornwater/korea-lotto645-analyzer/main/data/lotto645.csv",
]
NAVER_URL = "https://search.naver.com/search.naver?query=%EB%A1%9C%EB%98%90%EB%8B%B9%EC%B2%A9%EB%B2%88%ED%98%B8"
KR_BASE_DATE = date(2002, 12, 7)  # 로또 6/45 第 1 期（与 App LottoRound 一致）


def kr_round_to_date(round_no):
    return (KR_BASE_DATE + timedelta(days=7 * (round_no - 1))).strftime("%Y-%m-%d")


def fetch_kr_csv():
    """历史数据：draw_no,date,n1..n6,bonus（date 通常为空 → 用期号公式）"""
    for url in KR_CSV_URLS:
        try:
            text = fetch(url).lstrip("\ufeff")  # 防 BOM 弄坏首列名
            draws = []
            for row in csv.DictReader(io.StringIO(text)):
                try:
                    no = int(row["draw_no"])
                    nums = [int(row["n%d" % i]) for i in range(1, 7)]
                    bonus = [int(row["bonus"])]
                except (KeyError, TypeError, ValueError):
                    continue
                dt = (row.get("date") or "").strip()
                if not valid_date(dt):
                    dt = kr_round_to_date(no)
                draws.append({"date": dt, "numbers": nums, "bonus": bonus})
            log("kr csv ok via %s (%d rows)" % (url, len(draws)))
            return draws
        except Exception as e:  # noqa: BLE001
            log("kr csv source failed %s: %s" % (url, e))
    return None


def fetch_kr_naver():
    """Naver 开奖组件（SSR）：最新一期，含期号/日期/号码/보너스。"""
    try:
        html = fetch(NAVER_URL)
        m = re.search(r"class=\"winning_number\">(.*?)</div>", html, re.S)
        b = re.search(r"class=\"bonus_number\">(.*?)</div>", html, re.S)
        d = re.search(r"(\d+)회차\s*\((\d{4})\.(\d{2})\.(\d{2})\.\)", html)
        if not (m and b and d):
            log("kr naver: pattern not found")
            return None
        nums = [int(x) for x in re.findall(r">(\d+)</span>", m.group(1))]
        bonus = [int(x) for x in re.findall(r">(\d+)</span>", b.group(1))]
        dt = "%s-%s-%s" % (d.group(2), d.group(3), d.group(4))
        draw = {"date": dt, "numbers": nums, "bonus": bonus}
        # 与期号公式交叉校验（防止解析错位）
        expected = kr_round_to_date(int(d.group(1)))
        if expected != dt:
            log("kr naver: date mismatch round=%s widget=%s formula=%s (use widget)"
                % (d.group(1), dt, expected))
        log("kr naver ok: round %s %s %s+%s" % (d.group(1), dt, nums, bonus))
        return [draw]
    except Exception as e:  # noqa: BLE001
        log("kr naver failed: %s" % e)
        return None


def build_kr(prev_games):
    draws = []
    src_csv = fetch_kr_csv()
    if src_csv is not None:
        draws += src_csv
    src_naver = fetch_kr_naver()
    if src_naver is not None:
        draws += src_naver
    if not draws:
        draws = prev_games.get("lotto645", [])
        log("kr FALLBACK to previous data")
    merged = sanitize("lotto645", draws + prev_games.get("lotto645", []))
    entry = {"key": "lotto645", "name": "로또 6/45", "latestDraw": None, "recentDraws": merged}
    if merged:
        entry["latestDraw"] = merged[0]
    return [entry]


# ---------------------------------------------------------------- 美国

LU_URLS = {
    "powerball": "https://www.lotteryusa.com/powerball/",
    "mega-millions": "https://www.lotteryusa.com/mega-millions/",
}
PB_FALLBACK_URL = "https://www.powerball.com/previous-results?gc=powerball"
US_NAMES = {"powerball": "Powerball", "mega-millions": "Mega Millions"}

# jbaranski/jeffs-lottery-utils：每次开奖后自动更新的完整数据集
US_DATA_URLS = {
    "powerball": [
        "https://cdn.jsdelivr.net/gh/jbaranski/jeffs-lottery-utils@main/numbers/powerball.json",
        "https://raw.githubusercontent.com/jbaranski/jeffs-lottery-utils/main/numbers/powerball.json",
    ],
    "mega-millions": [
        "https://cdn.jsdelivr.net/gh/jbaranski/jeffs-lottery-utils@main/numbers/megamillions.json",
        "https://raw.githubusercontent.com/jbaranski/jeffs-lottery-utils/main/numbers/megamillions.json",
    ],
}
US_BONUS_FIELD = {"powerball": "red_ball", "mega-millions": "yellow_ball"}


def fetch_us_dataset(key):
    """数据集格式：[{date:"MM/DD/YYYY", white_balls:[5], red_ball|yellow_ball:int}] 升序"""
    for url in US_DATA_URLS[key]:
        try:
            rows = json.loads(fetch(url))
            draws = []
            for r in rows:
                if not isinstance(r, dict):
                    continue
                try:
                    dt = datetime.strptime(str(r.get("date", "")), "%m/%d/%Y").strftime("%Y-%m-%d")
                except ValueError:
                    continue
                bonus = r.get(US_BONUS_FIELD[key])
                draws.append({
                    "date": dt,
                    "numbers": r.get("white_balls") or [],
                    "bonus": [bonus] if isinstance(bonus, int) else [],
                })
            log("us/%s dataset ok via %s (%d rows)" % (key, url, len(draws)))
            return draws
        except Exception as e:  # noqa: BLE001
            log("us/%s dataset source failed %s: %s" % (key, url, e))
    return None


def parse_lotteryusa(html):
    """lotteryusa.com 开奖卡片（SSR）：日期 + 5 主球 + 1 特别球。"""
    draws = []
    # 按卡片切块
    starts = [m.start() for m in re.finditer(r'<div class="c-draw-card"', html)]
    starts.append(len(html))
    for i in range(len(starts) - 1):
        chunk = html[starts[i]:starts[i + 1]]
        dm = re.search(
            r'c-draw-card__draw-date-dow">\s*([A-Za-z]+),\s*</span>\s*'
            r'<span class="c-draw-card__draw-date-sub">\s*([A-Za-z]{3} \d{1,2}, \d{4})',
            chunk, re.S)
        if not dm:
            continue
        try:
            dt = datetime.strptime(dm.group(2), "%b %d, %Y").strftime("%Y-%m-%d")
        except ValueError:
            continue
        # 只取卡片内第一个号码组（Powerball 页可能带 Double Play）
        box = re.search(r'c-draw-card__ball-box(.*?)(?:c-draw-card__ball-box|</ul>\s*</div>\s*</div>)',
                        chunk, re.S)
        region = box.group(1) if box else chunk
        nums = [int(x) for x in re.findall(r'<li class="c-ball c-ball--sm"[^>]*>\s*(\d+)\s*<', region)]
        bm = re.search(r'c-result__bonus.*?<span class="c-ball[^"]*">(\d+)</span>', region, re.S)
        bonus = [int(bm.group(1))] if bm else []
        if nums:
            draws.append({"date": dt, "numbers": nums, "bonus": bonus})
    return draws


def parse_powerball_com(html):
    """powerball.com/previous-results 备源。"""
    draws = []
    starts = [m.start() for m in re.finditer(r'card-title">', html)]
    starts.append(len(html))
    for i in range(len(starts) - 1):
        chunk = html[starts[i]:starts[i + 1]]
        dm = re.search(r'card-title">([A-Za-z]{3}, [A-Za-z]{3} \d{1,2}, \d{4})<', chunk)
        if not dm:
            continue
        try:
            dt = datetime.strptime(dm.group(1), "%a, %b %d, %Y").strftime("%Y-%m-%d")
        except ValueError:
            continue
        nums = [int(x) for x in re.findall(
            r'white-balls[^"]*">\s*<div>\s*(\d+)\s*</div>', chunk)]
        bm = re.search(r'powerball item-powerball">\s*<div>\s*(\d+)\s*</div>', chunk)
        bonus = [int(bm.group(1))] if bm else []
        if nums:
            draws.append({"date": dt, "numbers": nums, "bonus": bonus})
    return draws


def build_us_game(key, prev_draws):
    """历史 = jbaranski 数据集；最新一期 = lotteryusa（防止数据集滞后）；再叠旧数据兜底。"""
    draws = fetch_us_dataset(key)
    if draws is None:
        draws = []
    try:
        html = fetch(LU_URLS[key])
        got = parse_lotteryusa(html)
        if got:
            log("us/%s lotteryusa latest ok: %s" % (key, got[0]))
            draws = got + draws
        else:
            log("us/%s lotteryusa: 0 draws parsed" % key)
    except Exception as e:  # noqa: BLE001
        log("us/%s lotteryusa failed: %s" % (key, e))
    if not draws and key == "powerball":
        try:
            html = fetch(PB_FALLBACK_URL)
            got = parse_powerball_com(html)
            if got:
                draws = got
                log("us/%s powerball.com fallback ok (%d draws)" % (key, len(got)))
        except Exception as e:  # noqa: BLE001
            log("us/%s powerball.com fallback failed: %s" % (key, e))
    if not draws:
        draws = prev_draws
        log("us/%s FALLBACK to previous data" % key)
    return sanitize(key, draws + prev_draws)


def build_us(prev_games):
    games = []
    for key in ("powerball", "mega-millions"):
        merged = build_us_game(key, prev_games.get(key, []))
        entry = {"key": key, "name": US_NAMES[key], "latestDraw": None, "recentDraws": merged}
        if merged:
            entry["latestDraw"] = merged[0]
        games.append(entry)
    return games


# ---------------------------------------------------------------- 组装 / 落盘

LOCALE_TZ = {"ja": "Asia/Tokyo", "kr": "Asia/Seoul", "us": "America/New_York"}
LOCALE_KEYS = {
    "ja": ["roto6", "roto7", "mini_loto", "numbers3", "numbers4"],
    "kr": ["lotto645"],
    "us": ["powerball", "mega-millions"],
}


def load_prev(locale):
    """读取上一次成功的 draws.json，抽出各彩种历史（兜底用）。"""
    path = os.path.join(OUT_DIR, locale, "draws.json")
    try:
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
        out = {}
        for g in payload.get("games", []):
            key = g.get("key")
            if key in LOCALE_KEYS[locale]:
                out[key] = (g.get("recentDraws") or []) + ([g["latestDraw"]] if g.get("latestDraw") else [])
        return out
    except Exception:  # noqa: BLE001
        return {}


def schema_check(locale, payload):
    """写盘前整体自检（对应 App 解码模型）。"""
    if not valid_date(payload.get("date")):
        return False
    if payload.get("locale") != locale:
        return False
    games = payload.get("games")
    if not isinstance(games, list):
        return False
    for g in games:
        if g.get("key") not in LOCALE_KEYS[locale]:
            return False
        if not isinstance(g.get("name"), str) or not g["name"]:
            return False
        for d in (g.get("recentDraws") or []):
            if not valid_draw(g["key"], d):
                return False
        ld = g.get("latestDraw")
        if ld is not None and not valid_draw(g["key"], ld):
            return False
    return True


def write_payload(locale, payload):
    outdir = os.path.join(OUT_DIR, locale)
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "draws.json")
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    fd, tmp = tempfile.mkstemp(dir=outdir, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.chmod(tmp, 0o644)  # 确保 nginx 可读
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    log("wrote %s (%d bytes)" % (path, len(data)))


def main():
    builders = {"ja": build_ja, "kr": build_kr, "us": build_us}
    ok, fail = [], []
    for locale in ("ja", "kr", "us"):
        try:
            prev = load_prev(locale)
            games = builders[locale](prev)
            tz = ZoneInfo(LOCALE_TZ[locale])
            payload = {
                "date": datetime.now(tz).strftime("%Y-%m-%d"),  # 代码强制当天真实值
                "locale": locale,
                "games": games,
            }
            if not schema_check(locale, payload):
                raise RuntimeError("schema self-check failed, keep previous file")
            write_payload(locale, payload)
            ok.append(locale)
        except Exception as e:  # noqa: BLE001
            log("!! %s FAILED: %s (previous data kept)" % (locale, e))
            fail.append(locale)
    log("done. ok=%s fail=%s" % (ok, fail))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
