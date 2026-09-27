#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ENSOWatch 数据管线
- NOAA ENSO 指数（周度 Niño 区海温距平 + ONI）
- 新浪国内期货行情快照
- 厄尔尼诺×商品影响评分引擎
输出: enso-status.json / enso-history.json / enso-futures.json
用法: python3 gen_enso.py [输出目录, 默认当前目录]
"""
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
UA = {"User-Agent": "Mozilla/5.0 (ENSOWatch/1.0)"}
SINA_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://finance.sina.com.cn",
}

# wksst8110.for 镜像停更于2021年，改用 1991-2020 基准的活数据源
WEEKLY_URL = "https://www.cpc.ncep.noaa.gov/data/indices/wksst9120.for"
ONI_URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
# 新浪 hq.sinajs.cn 封禁阿里云 IP；push2 系列对 ECS 频率风控。
# futsseapi 列表接口 + token 经 ECS 验证稳定可用，且价格直接为浮点（无需小数缩放）
EM_LIST_URL = "https://futsseapi.eastmoney.com/list/113,114,115,142"
EM_TOKEN = "58b2fa8f54638b60b87d69b31969089c"

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def http_get(url, headers=None, timeout=20, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers or UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:
            if i == retries - 1:
                raise
            time.sleep(2)


# ---------------------------------------------------------------- NOAA 数据

def fetch_weekly_sst():
    """解析 CPC 周度海温文件 → [{week, nino34_sst, nino34_ssta, nino3_ssta, nino4_ssta, nino12_ssta}]"""
    text = http_get(WEEKLY_URL)
    rows = []
    for line in text.splitlines():
        m = re.match(r"\s*(\d{2})([A-Z]{3})(\d{4})(.+)", line)
        if not m:
            continue
        day, mon, year, rest = m.groups()
        # SST 与距平之间可能有空格（正距平）或紧贴（负距平），如 "23.4-0.4" / "28.6 0.3"
        pairs = re.findall(r"(\d+\.\d)\s*(-?\d+\.\d)", rest)
        if len(pairs) < 4:
            continue
        try:
            mi = MONTHS.index(mon.title()) + 1
        except ValueError:
            continue
        week = f"{year}-{mi:02d}-{int(day):02d}"
        rows.append({
            "week": week,
            "nino12_ssta": float(pairs[0][1]),
            "nino3_ssta": float(pairs[1][1]),
            "nino34_sst": float(pairs[2][0]),
            "nino34_ssta": float(pairs[2][1]),
            "nino4_ssta": float(pairs[3][1]),
        })
    return rows


def fetch_oni():
    """解析 ONI 文件 → [{season, year, total, anom}]"""
    text = http_get(ONI_URL)
    rows = []
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) != 4:
            continue
        try:
            rows.append({
                "season": parts[0],
                "year": int(parts[1]),
                "total": float(parts[2]),
                "anom": float(parts[3]),
            })
        except ValueError:
            continue
    return rows


# ------------------------------------------------------------- 状态判定

def classify(anom):
    """海温距平 → (phase, intensity)"""
    if anom >= 2.0:
        return "ElNino", "super"
    if anom >= 1.5:
        return "ElNino", "strong"
    if anom >= 1.0:
        return "ElNino", "moderate"
    if anom >= 0.5:
        return "ElNino", "weak"
    if anom <= -2.0:
        return "LaNina", "super"
    if anom <= -1.5:
        return "LaNina", "strong"
    if anom <= -1.0:
        return "LaNina", "moderate"
    if anom <= -0.5:
        return "LaNina", "weak"
    return "Neutral", "neutral"


PHASE_CN = {"ElNino": "厄尔尼诺", "LaNina": "拉尼娜", "Neutral": "中性"}
INTENSITY_CN = {"super": "超强", "strong": "强", "moderate": "中等",
                "weak": "弱", "neutral": ""}


# ------------------------------------------------------- 影响评分引擎
# dir_el: 厄尔尼诺方向 (+利多 / -利空)  dir_la: 拉尼娜方向
# peak: 影响敏感月份(1-12)  confidence: high/medium/low
# secid: 东方财富主连代码  decimals: 价格小数位（EM 返回整数需缩放）
IMPACT_RULES = [
    {"code": "pm", "name": "棕榈油", "secid": "114.pm", "decimals": 0, "dir_el": 1.0, "dir_la": -0.8,
     "peak": [9, 10, 11, 12, 1, 2], "confidence": "high",
     "logic": "厄尔尼诺→印尼/马来西亚干旱→棕榈油减产→利多；拉尼娜→东南亚多雨利于增产→利空",
     "history": "1997/98、2015/16 强厄尔尼诺期间马棕油价格大幅上行"},
    {"code": "SR0", "name": "白糖", "secid": "115.SRM", "decimals": 0, "dir_el": 0.9, "dir_la": -0.6,
     "peak": [10, 11, 12, 1, 2, 3], "confidence": "high",
     "logic": "厄尔尼诺→印度/泰国季风偏弱→甘蔗减产→利多；拉尼娜→东南亚降水偏多→利空",
     "history": "2015/16 厄尔尼诺年国际原糖价格显著上涨"},
    {"code": "RU0", "name": "天然橡胶", "secid": "113.rum", "decimals": 0, "dir_el": 0.7, "dir_la": -0.5,
     "peak": [11, 12, 1, 2], "confidence": "medium",
     "logic": "厄尔尼诺→东南亚偏干→割胶受阻、产出下降→利多",
     "history": "强厄尔尼诺年东南亚产区旱情常推升胶价"},
    {"code": "CF0", "name": "棉花", "secid": "115.CFM", "decimals": 0, "dir_el": 0.6, "dir_la": -0.4,
     "peak": [7, 8, 9, 10], "confidence": "medium",
     "logic": "厄尔尼诺→印度/巴基斯坦主产区偏干→棉花减产→利多",
     "history": "1997 年印度棉花因干旱明显减产"},
    {"code": "M0", "name": "豆粕", "secid": "114.mm", "decimals": 0, "dir_el": 0.5, "dir_la": -0.4,
     "peak": [11, 12, 1, 2, 3], "confidence": "low",
     "logic": "厄尔尼诺→阿根廷偏干→大豆减产→豆粕利多（巴西增产常部分抵消）",
     "history": "2015/16 阿根廷洪涝减产，豆类价格阶段走强"},
    {"code": "Y0", "name": "豆油", "secid": "114.ym", "decimals": 0, "dir_el": 0.5, "dir_la": -0.4,
     "peak": [9, 10, 11, 12, 1], "confidence": "low",
     "logic": "跟随油脂板块：棕榈油减产预期+大豆产区天气扰动→偏多",
     "history": "油脂板块在强厄尔尼诺年整体偏强"},
    {"code": "OI0", "name": "菜油", "secid": "115.OIM", "decimals": 0, "dir_el": 0.4, "dir_la": -0.3,
     "peak": [9, 10, 11, 12, 1], "confidence": "low",
     "logic": "跟随棕榈油/豆油联动，厄尔尼诺减产预期传导→偏多",
     "history": "油脂联动性强，菜油常跟随棕榈油走势"},
    {"code": "C0", "name": "玉米", "secid": "114.cm", "decimals": 0, "dir_el": -0.2, "dir_la": 0.2,
     "peak": [6, 7, 8], "confidence": "low",
     "logic": "厄尔尼诺对中国北方/美国中西部降水影响复杂，总体影响有限→中性",
     "history": "历史厄尔尼诺年玉米价格无明显一致规律"},
    {"code": "SC0", "name": "原油", "secid": "142.scm", "decimals": 1, "dir_el": -0.5, "dir_la": 0.5,
     "peak": [11, 12, 1, 2], "confidence": "medium",
     "logic": "厄尔尼诺→北半球暖冬→取暖油需求下降→利空；拉尼娜→冷冬需求↑→利多",
     "history": "1997/98 暖冬曾压制北美能源需求"},
    {"code": "FU0", "name": "燃料油", "secid": "113.fum", "decimals": 0, "dir_el": -0.5, "dir_la": 0.5,
     "peak": [11, 12, 1, 2], "confidence": "medium",
     "logic": "跟随原油：暖冬压制取暖需求→利空；拉尼娜冷冬→利多",
     "history": "与原油联动，暖冬年炼厂取暖油库存常累积"},
    {"code": "CU0", "name": "沪铜", "secid": "113.cum", "decimals": 0, "dir_el": 0.1, "dir_la": -0.1,
     "peak": [1, 2, 3], "confidence": "low",
     "logic": "智利/秘鲁矿区天气扰动有限，供需主线在宏观与矿端→中性",
     "history": "厄尔尼诺对铜价无稳定统计规律"},
    {"code": "A0", "name": "豆一", "secid": "114.am", "decimals": 0, "dir_el": -0.3, "dir_la": 0.3,
     "peak": [5, 6, 7, 8], "confidence": "low",
     "logic": "厄尔尼诺年中国东北易偏干，国产大豆单产承压但影响幅度有限→中性偏空",
     "history": "统计规律弱，仅供参考"},
]


def score_impact(anom, month):
    """当前海温距平 + 月份 → 每品种评分(-2.0~+2.0)"""
    out = []
    for rule in IMPACT_RULES:
        if anom >= 0:
            base = min(anom, 2.5) / 2.5 * rule["dir_el"]
        else:
            base = min(-anom, 2.5) / 2.5 * rule["dir_la"]
        season = 1.0 if month in rule["peak"] else 0.7
        score = max(-2.0, min(2.0, round(base * 2.0 * season, 1)))
        if score >= 0.5:
            label = "利多"
        elif score <= -0.5:
            label = "利空"
        else:
            label = "中性"
        out.append({
            "code": rule["code"],
            "name": rule["name"],
            "score": score,
            "label": label,
            "confidence": rule["confidence"],
            "logic": rule["logic"],
            "history": rule["history"],
        })
    return out


# ------------------------------------------------------- 新浪期货行情

def fetch_futures_quotes(rules):
    """东方财富 futsseapi 主连行情列表 → {code: quote}
    返回字段: p最新 o今开 h最高 l最低 zde涨跌 zdf涨跌% vol成交量 ccl持仓量
    """
    want = {r["secid"].split(".", 1)[1]: r for r in rules}  # secid=交易所id.主连代码
    quotes = {}
    for page in range(0, 10):
        url = (f"{EM_LIST_URL}?orderBy=dm&sort=asc&pageSize=100&pageIndex={page}"
               f"&token={EM_TOKEN}"
               f"&field=dm,name,p,zde,zdf,o,h,l,vol,ccl&blockName=callback")
        try:
            raw = http_get(url).strip()
            if not raw.startswith("{"):
                raw = raw[raw.index("(") + 1: raw.rindex(")")]
            data = json.loads(raw)
        except Exception as e:
            print(f"   ⚠️ 行情页 {page} 获取失败: {e}")
            continue
        for d in data.get("list", []):
            dm = d.get("dm")
            if dm in want and d.get("p"):
                rule = want[dm]
                quotes[rule["code"]] = {
                    "price": d["p"],
                    "open": d.get("o"),
                    "high": d.get("h"),
                    "low": d.get("l"),
                    "change": d.get("zde"),
                    "changePct": d.get("zdf"),
                    "volume": d.get("vol"),
                    "position": d.get("ccl"),
                    "name": d.get("name") or rule["name"],
                    "secid": rule["secid"],
                }
        if len(quotes) >= len(want):
            break
    return quotes


# ------------------------------------------------------------------ 主流程

def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out_dir, exist_ok=True)
    now = datetime.now(CST)
    updated = now.strftime("%Y-%m-%d %H:%M:%S")

    print("[1/4] 抓取 NOAA 周度海温…")
    weekly = fetch_weekly_sst()
    latest = weekly[-1]

    print("[2/4] 抓取 ONI 指数…")
    oni_rows = fetch_oni()
    latest_oni = oni_rows[-1]

    # 综合距平：周度为最新信号，ONI 为平滑裁决
    anom = latest["nino34_ssta"]
    phase, intensity = classify(anom)
    oni_phase, oni_intensity = classify(latest_oni["anom"])

    # 交叉校验：周度距平与 ONI 应大致同向，差异过大时告警
    if abs(anom - latest_oni["anom"]) > 1.2:
        print(f"⚠️ 警告: 周度距平 {anom:+.2f} 与 ONI {latest_oni['anom']:+.2f} 差异较大，请检查数据源")

    status = {
        "updatedAt": updated,
        "dataSource": "NOAA CPC (美国国家海洋和大气管理局气候预测中心)",
        "current": {
            "week": latest["week"],
            "nino34Sst": latest["nino34_sst"],
            "nino34Ssta": latest["nino34_ssta"],
            "phase": phase,
            "phaseCn": PHASE_CN[phase],
            "intensity": intensity,
            "intensityCn": INTENSITY_CN[intensity],
        },
        "oni": {
            "season": latest_oni["season"],
            "year": latest_oni["year"],
            "total": latest_oni["total"],
            "anom": latest_oni["anom"],
            "phase": oni_phase,
            "phaseCn": PHASE_CN[oni_phase],
        },
        "weeklySsta": [
            {"week": r["week"], "nino34Ssta": r["nino34_ssta"],
             "nino3Ssta": r["nino3_ssta"], "nino4Ssta": r["nino4_ssta"]}
            for r in weekly[-260:]  # 近5年
        ],
    }

    history = {
        "updatedAt": updated,
        "dataSource": "NOAA CPC ONI (Oceanic Nino Index)",
        "description": "ONI 为 Niño3.4 区海温距平的3个月滚动平均值，ENSO 事件判定的国际通用标准",
        "oni": [
            {"season": r["season"], "year": r["year"],
             "total": r["total"], "anom": r["anom"]}
            for r in oni_rows
        ],
        "notableEvents": [
            {"name": "1997-98 超强厄尔尼诺", "peakAnom": 2.4, "year": 1997,
             "desc": "20世纪最强事件之一，秘鲁沿岸暴雨洪涝，东南亚严重干旱，全球平均气温创新高"},
            {"name": "2015-16 超强厄尔尼诺", "peakAnom": 2.6, "year": 2015,
             "desc": "有记录以来最强，印尼森林大火，印度季风偏弱，2016 年成当时史上最热年"},
            {"name": "1982-83 超强厄尔尼诺", "peakAnom": 2.2, "year": 1982,
             "desc": "与1997年并列的超级事件，澳大利亚大旱，秘鲁渔业损失惨重"},
            {"name": "2023-24 强厄尔尼诺", "peakAnom": 2.0, "year": 2023,
             "desc": "2023 年全球海温创新纪录，2024 年转为拉尼娜"},
            {"name": "2010-11 强拉尼娜", "peakAnom": -1.6, "year": 2010,
             "desc": "澳大利亚昆士兰世纪洪灾，东南亚棕榈油产区多雨"},
        ],
    }

    print("[3/4] 影响评分引擎…")
    month = now.month
    impacts = score_impact(anom, month)

    print("[4/4] 抓取期货行情…")
    quotes = fetch_futures_quotes(IMPACT_RULES)

    futures_items = []
    for imp in impacts:
        q = quotes.get(imp["code"])
        item = dict(imp)
        item["quote"] = q
        futures_items.append(item)

    futures = {
        "updatedAt": updated,
        "ensoAnom": anom,
        "ensoPhaseCn": PHASE_CN[phase],
        "ensoIntensityCn": INTENSITY_CN[intensity],
        "disclaimer": "以上为气候影响科普与统计分析，不构成投资建议。期市有风险，决策需谨慎。",
        "items": futures_items,
    }

    with open(f"{out_dir}/enso-status.json", "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, separators=(",", ":"))
    with open(f"{out_dir}/enso-history.json", "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, separators=(",", ":"))
    with open(f"{out_dir}/enso-futures.json", "w", encoding="utf-8") as f:
        json.dump(futures, f, ensure_ascii=False, separators=(",", ":"))

    print(f"✅ 完成: enso-status.json / enso-history.json / enso-futures.json → {out_dir}")
    print(f"   当前: {PHASE_CN[phase]}{INTENSITY_CN[intensity]} Niño3.4距平 {anom:+.2f}℃")
    print(f"   行情: {len(quotes)}/{len(IMPACT_RULES)} 个品种获取成功")


if __name__ == "__main__":
    main()
