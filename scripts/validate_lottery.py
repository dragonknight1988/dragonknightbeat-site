#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_lottery.py — 严格对照三个 iOS App 的 Codable 解码模型校验 draws.json

- DKLotoJP  DrawsPayload:  date?/locale?/games?[GamePayload{key,name?,latestDraw?,recentDraws?}]
            DrawEntry: {date:String, numbers:[Int], bonus:[Int]?}
            GameKey: roto6|roto7|mini_loto|numbers3|numbers4
- DKLotoKR  DrawsResponse: date/locale/games 非可空；DrawItem.bonus 非可空 [Int]
            key: lotto645
- DKLotoUS  DrawsResponse: date?/locale?；DrawEntry.bonus 非可空 [Int]
            key: powerball|mega-millions

用法: python3 validate_lottery.py [base_url]
  默认校验本机文件；传 URL 则校验线上端点。
退出码 0 = 全部通过。
"""
import json
import re
import sys
import urllib.request
from datetime import datetime

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

SPECS = {
    "ja": {
        "keys": {"roto6", "roto7", "mini_loto", "numbers3", "numbers4"},
        "date_required": False, "locale_required": False,
        "name_required": False, "bonus_required": False,
        "rules": {
            "roto6": (6, 1, 43, 1, 1, 43),
            "roto7": (7, 1, 37, 2, 1, 37),
            "mini_loto": (5, 1, 31, 1, 1, 31),
            "numbers3": (3, 0, 9, 0, 0, 9),
            "numbers4": (4, 0, 9, 0, 0, 9),
        },
    },
    "kr": {
        "keys": {"lotto645"},
        "date_required": True, "locale_required": True,
        "name_required": True, "bonus_required": True,
        "rules": {"lotto645": (6, 1, 45, 1, 1, 45)},
    },
    "us": {
        "keys": {"powerball", "mega-millions"},
        "date_required": False, "locale_required": False,
        "name_required": False, "bonus_required": True,
        "rules": {
            "powerball": (5, 1, 69, 1, 1, 26),
            "mega-millions": (5, 1, 70, 1, 1, 25),
        },
    },
}


def is_date(s):
    if not isinstance(s, str) or not DATE_RE.match(s):
        return False
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def check(locale, payload):
    errs = []
    spec = SPECS[locale]

    if spec["date_required"] and not is_date(payload.get("date")):
        errs.append("date missing/invalid (required non-null)")
    elif payload.get("date") is not None and not is_date(payload.get("date")):
        errs.append("date present but invalid")

    if spec["locale_required"] and payload.get("locale") != locale:
        errs.append("locale missing/mismatch (required non-null)")
    elif payload.get("locale") is not None and payload["locale"] != locale:
        errs.append("locale mismatch")

    games = payload.get("games")
    if not isinstance(games, list) or not games:
        errs.append("games missing/not array")
        return errs

    for g in games:
        key = g.get("key")
        if key not in spec["keys"]:
            errs.append("unknown game key: %r" % key)
            continue
        if spec["name_required"] and (not isinstance(g.get("name"), str) or not g["name"]):
            errs.append("%s: name missing (required non-null)" % key)

        draws = g.get("recentDraws")
        if draws is None:
            draws = []
        if not isinstance(draws, list):
            errs.append("%s: recentDraws not array" % key)
            continue

        mc, mn, mx, bc, bmin, bmax = spec["rules"][key]
        all_draws = list(draws)
        if g.get("latestDraw") is not None:
            all_draws.append(g["latestDraw"])
        for i, d in enumerate(all_draws):
            where = "%s[%d]" % (key, i)
            if not isinstance(d, dict):
                errs.append("%s: not object" % where)
                continue
            if not is_date(d.get("date")):
                errs.append("%s: bad date %r" % (where, d.get("date")))
            nums = d.get("numbers")
            if not isinstance(nums, list) or len(nums) != mc:
                errs.append("%s: numbers %r (want %d ints)" % (where, nums, mc))
            elif any((not isinstance(n, int)) or n < mn or n > mx for n in nums):
                errs.append("%s: numbers out of range %r" % (where, nums))
            bonus = d.get("bonus")
            if bonus is None:
                if spec["bonus_required"]:
                    errs.append("%s: bonus missing (required non-null [])" % where)
            elif not isinstance(bonus, list) or len(bonus) != bc:
                errs.append("%s: bonus %r (want %d ints)" % (where, bonus, bc))
            elif any((not isinstance(b, int)) or b < bmin or b > bmax for b in bonus):
                errs.append("%s: bonus out of range %r" % (where, bonus))

        ld = g.get("latestDraw")
        if ld is not None and draws and ld.get("date") != draws[0].get("date"):
            errs.append("%s: latestDraw not equal to newest recentDraws" % key)

    return errs


def load(locale, base):
    if base:
        url = "%s/lottery/%s/draws.json" % (base.rstrip("/"), locale)
        with urllib.request.urlopen(url, timeout=20) as r:
            return json.loads(r.read().decode("utf-8")), url
    path = "/var/www/dragonknightbeat.com/lottery/%s/draws.json" % locale
    with open(path, encoding="utf-8") as f:
        return json.load(f), path


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else ""
    failed = False
    for locale in ("ja", "kr", "us"):
        try:
            payload, src = load(locale, base)
        except Exception as e:  # noqa: BLE001
            print("[FAIL] %s: cannot load: %s" % (locale, e))
            failed = True
            continue
        errs = check(locale, payload)
        games = payload.get("games") or []
        summary = "games=%d draws=%s" % (
            len(games),
            ",".join("%s:%d" % (g.get("key"), len(g.get("recentDraws") or [])) for g in games),
        )
        if errs:
            failed = True
            print("[FAIL] %s (%s) %s" % (locale, src, summary))
            for e in errs[:10]:
                print("       -", e)
        else:
            print("[PASS] %s (%s) %s" % (locale, src, summary))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
