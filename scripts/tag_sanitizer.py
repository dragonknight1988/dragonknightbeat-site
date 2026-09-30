#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tag_sanitizer.py — DK晨报「行业透视」关键词净化器 v1.0 (2026-10-01)

背景:daily-news.json 每条新闻的 tags 与 trendingTopics 会进入 App「行业透视」
     (首页标签 chips → 行业分析、今日行业热度榜、行业风向标)。AI 生成时常把
     人名(含已故明星)、国家名、纪念日、警号/编号、犯罪敏感词(制毒/贩毒等)
     当关键词输出,展示尴尬且有舆论风险。

策略:生成侧提示词约束 + 发布侧本模块确定性过滤,双保险。

规则类别:
  1. 敏感词根(子串命中即弃):毒品/暴力犯罪/司法腐败事件词/死亡讣闻/灾难事故/战争武器/纪念英烈/编号
  2. 国家·地区·组织名(精确匹配):美国/伊朗/欧盟等,主题词如"中东局势"不受影响
  3. 数字类:含3位以上连续数字(警号021544/1500亿件)、裸月份(9月)、纯数字
  4. 人名:知名人物黑名单(子串) + 讣闻标题规则(标题含逝世等→弃标题内实体词)
     + 人物语境标题规则(标题含冠军/演员等→疑似姓氏开头的2-3字短标签弃)
  5. 长度异常(<2 或 >12 字符)、去重
  6. 兜底:某条新闻 tags 全被过滤时,按板块回填默认主题词,保证 UI 不空

用法:
  模块: from tag_sanitizer import sanitize_news_data
        data = sanitize_news_data(data)
  CLI:  python3 tag_sanitizer.py /path/to/daily-news.json   # 就地净化(自动留 .bak)
"""
import json
import re
import sys

# ---------- 白名单(永不拦截) ----------
WHITELIST = {
    "英雄联盟",  # 电竞项目名,防止被"英雄"词根误伤
}

# ---------- 类别1:敏感词根(子串命中即弃) ----------
SENSITIVE_ROOTS = [
    # 毒品
    "制毒", "贩毒", "毒品", "吸毒", "涉毒", "毒贩", "毒枭",
    # 暴力犯罪
    "杀人", "杀害", "凶杀", "凶手", "命案", "凶案", "碎尸", "抛尸", "尸体",
    "强奸", "猥亵", "性侵", "嫖娼", "卖淫", "色情", "裸照", "偷拍",
    "绑架", "劫持", "人质", "走私", "偷渡", "拐卖",
    "枪击", "持刀", "砍人", "行凶", "爆炸", "炸弹", "纵火", "恐怖", "恐袭",
    # 司法腐败/案件事件词(非行业词)
    "贪污", "受贿", "行贿", "贪腐", "腐败", "落马", "双开", "违纪",
    "判刑", "死刑", "枪决", "处决", "逮捕", "拘捕", "越狱", "服刑", "嫌犯", "落网",
    "诈骗", "传销", "洗钱", "非法集资", "赌博", "赌场", "赌球",
    "破案", "案发", "开庭", "庭审", "宣判", "起诉", "索赔", "立案", "侦查",
    # 死亡讣闻
    "逝世", "去世", "离世", "殉职", "病故", "身亡", "遇难", "罹难", "讣告",
    "追悼", "悼念", "自杀", "轻生",
    # 灾难事故
    "坠机", "空难", "沉船", "车祸", "火灾", "塌方", "溃坝", "伤亡", "死伤",
    # 战争武器
    "战争", "开战", "宣战", "空袭", "炮击", "袭击", "导弹", "核武", "核弹", "殖民",
    # 纪念/英烈
    "烈士", "英烈", "英雄", "纪念日", "公祭", "诞辰", "周年",
    # 裸节日词(带主题后缀的如"中秋消费"不受影响)
    "国庆节", "春节", "元旦", "除夕", "元宵节", "清明节", "建党", "建军", "抗战胜利",
    # 编号/仪式类
    "警号", "编号", "证件号", "车牌号", "招待会", "仪式",
]

# ---------- 类别2:国家·地区·组织名(整词精确匹配才弃) ----------
COUNTRIES_REGIONS = {
    "中国", "美国", "日本", "英国", "法国", "德国", "俄罗斯", "乌克兰", "伊朗",
    "以色列", "朝鲜", "韩国", "印度", "巴基斯坦", "阿富汗", "叙利亚", "土耳其",
    "沙特", "阿联酋", "卡塔尔", "埃及", "南非", "巴西", "阿根廷", "加拿大",
    "澳大利亚", "新西兰", "意大利", "西班牙", "葡萄牙", "荷兰", "比利时", "瑞士",
    "瑞典", "挪威", "丹麦", "芬兰", "波兰", "匈牙利", "希腊", "捷克", "奥地利",
    "爱尔兰", "欧盟", "联合国", "北约", "东盟", "非盟", "上合组织", "世卫组织",
    "世贸组织", "国际货币基金组织", "台湾", "香港", "澳门", "加沙", "中东",
    "欧洲", "亚洲", "非洲", "美洲", "拉美", "东南亚", "东北亚",
    "北京", "上海", "广州", "深圳",
}

# ---------- 类别4a:知名人物黑名单(子串命中即弃,可持续扩充) ----------
PERSON_BLACKLIST = [
    # 国际政要
    "特朗普", "普京", "拜登", "泽连斯基", "内塔尼亚胡", "金正恩", "哈梅内伊",
    "高市早苗", "石破茂", "马克龙", "朔尔茨", "斯塔默", "莫迪", "埃尔多安",
    # 科技企业家
    "马斯克", "黄仁勋", "奥特曼", "扎克伯格", "库克", "纳德拉", "皮查伊",
    "雷军", "马云", "马化腾", "张一鸣", "刘强东", "王兴", "李彦宏", "董明珠",
    # 文娱
    "周杰伦", "周星驰", "刘德华", "张学友", "成龙", "李连杰", "章子怡",
    "王一博", "肖战", "迪丽热巴", "杨幂", "赵丽颖", "胡歌", "易烊千玺",
    "王俊凯", "鹿晗", "范冰冰", "赵薇", "郑爽", "游本昌", "六小龄童",
    # 体育
    "梅西", "C罗", "姆巴佩", "内马尔", "哈兰德", "詹姆斯", "库里", "杜兰特",
    "德约科维奇", "纳达尔", "郑钦文", "全红婵", "孙颖莎", "樊振东", "马龙",
    "张雨霏", "潘展乐", "苏炳添", "谷爱凌",
]

# ---------- 类别4b:身份称谓词(整词匹配即弃,如"退休教授""离职高管") ----------
ROLE_WORDS = re.compile(
    r"^(退休|离职|现任|前任|资深|知名|著名|年轻|百岁|落马|涉案)?"
    r"(教授|专家|院士|学者|官员|干部|高管|总裁|董事长|总经理|经理|员工|职工|"
    r"司机|飞行员|机长|警察|民警|辅警|法官|检察官|律师|教师|校长|医生|护士|"
    r"记者|编辑|主播|网红|博主|作家|画家|科学家|研究员|工程师|程序员|"
    r"运动员|教练员|演员|歌手|明星|艺人|导演|编剧|制片人|"
    r"农民|工人|店主|老板|商贩|居民|村民|市民|网友|乘客|旅客|游客|"
    r"学生|考生|留学生|家长|老人|男子|女子|男孩|女孩|少年|儿童|婴儿|产妇|患者|"
    r"球迷|粉丝|歌迷|影迷|受害者|目击者|嫌疑人|被告人)$"
)

# ---------- 类别4c:讣闻标题(触发"标题内实体词"过滤) ----------
DEATH_TITLE = re.compile(r"逝世|去世|离世|殉职|病故|身亡|遇难|讣告|追悼")

# ---------- 类别4d:人物语境标题(触发"疑似人名"启发式) ----------
NAME_CTX = re.compile(
    r"逝世|去世|离世|殉职|冠军|夺冠|金牌|首金|银牌|铜牌|影帝|影后|视帝|视后|"
    r"明星|艺人|演员|歌手|导演|院士|教授|教练|球员|运动员|主帅|获刑|落马|"
    r"任命|履新|就任|辞世|百岁|大寿|"
    r"外长|部长|总统|总理|首相|主席|元首|议员|大使|发言人|书记|"
    r"会见|会谈|会晤|通电话"
)

# ---------- 常见姓氏(用于人物语境下的疑似人名启发式) ----------
SURNAMES = set(
    "王李张刘陈杨赵黄周吴徐孙胡朱高林何郭马罗梁宋郑谢韩唐冯于董萧程曹袁邓许傅沈曾彭吕苏卢蒋蔡贾丁魏薛叶阎余潘杜戴夏钟汪田任姜范方石姚谭廖邹熊金陆郝孔白崔康毛邱秦江史顾侯邵孟龙万段雷钱汤尹黎易常武乔贺赖龚文穆游覃佘麦庄"
)

# ---------- 疑似人名启发式的安全后缀(以这些结尾的短标签视为主题词,不弃) ----------
NAME_SAFE_END = (
    "球", "赛", "剧", "片", "展", "会", "业", "馆", "园", "奖", "秀", "坛",
    "界", "夫", "城", "圈", "热", "风", "潮", "学", "化", "素", "胞", "术",
    "器", "机", "车", "舰", "队", "部", "院", "校", "星", "人", "杯", "经济",
    "产业", "市场", "消费", "技术", "科技", "安全", "卫生", "教育", "文化",
    "体育", "电竞", "影视", "演艺", "音乐", "旅游", "股市", "楼市", "政策",
    "数据", "智能", "能源", "汽车", "芯片", "医药", "医疗", "农业", "环保",
    "食品", "交通", "基建", "物流", "快递", "金融", "投资", "出口", "创新",
    "数字", "网络", "平台", "体系", "制度", "改革", "贸易", "制造", "服务",
    "工程", "项目", "领域", "行业", "动态", "局势", "关系", "问题", "工作",
    "建设", "发展", "转型", "升级", "遗产", "纪录", "积分", "排名", "联赛",
    "奥运", "亚运", "全运", "世乒", "世锦",
)

BARE_MONTH = re.compile(r"^\d{1,2}月$")
LONG_DIGITS = re.compile(r"\d{3,}")

# 板块兜底标签(全被过滤时回填,保证 UI 不空)
DEFAULT_BY_ID = {
    "domestic": "政策民生",
    "international": "国际局势",
    "finance": "宏观经济",
    "tech": "科技创新",
    "other": "社会民生",
}
DEFAULT_BY_TITLE = {
    "国内时政": "政策民生",
    "国际时政": "国际局势",
    "财经动态": "宏观经济",
    "科技前沿": "科技创新",
    "其他要闻": "社会民生",
}


def _drop_reason(tag, title=None):
    """返回拦截原因;None = 放行"""
    t = (tag or "").strip()
    if t in WHITELIST:
        return None
    if len(t) < 2 or len(t) > 12:
        return "长度异常"
    for root in SENSITIVE_ROOTS:
        if root in t:
            return f"敏感词根[{root}]"
    if t in COUNTRIES_REGIONS:
        return "国家/地区/组织名"
    if LONG_DIGITS.search(t):
        return "含3位以上数字(编号/数据)"
    if BARE_MONTH.match(t) or t.isdigit():
        return "裸月份/纯数字"
    for p in PERSON_BLACKLIST:
        if p in t:
            return f"人名黑名单[{p}]"
    if ROLE_WORDS.match(t):
        return "身份称谓词(非行业词)"
    if title:
        if DEATH_TITLE.search(title) and t in title:
            return "讣闻实体词(人名/角色名)"
        if (NAME_CTX.search(title) and 2 <= len(t) <= 3
                and t[0] in SURNAMES and not t.endswith(NAME_SAFE_END)):
            return "疑似人名(人物语境标题)"
    return None


def sanitize_news_data(data, verbose=True):
    """就地净化整份 daily-news JSON 的 tags 与 trendingTopics,返回 (data, dropped)"""
    dropped = []

    # --- trendingTopics ---
    clean_tt, seen = [], set()
    for t in (data.get("trendingTopics") or []):
        if not isinstance(t, str):
            continue
        r = _drop_reason(t)
        if r:
            dropped.append(("trendingTopics", t.strip(), r))
            continue
        ts = t.strip()
        if ts in seen:
            continue
        seen.add(ts)
        clean_tt.append(ts)
    data["trendingTopics"] = clean_tt

    # --- 各板块文章 tags ---
    for sec in (data.get("sections") or []):
        dflt = (DEFAULT_BY_ID.get(str(sec.get("id", "")).strip())
                or DEFAULT_BY_TITLE.get(str(sec.get("title", "")).strip())
                or "时事观察")
        for art in (sec.get("articles") or []):
            title = art.get("title", "") or ""
            clean, seen2 = [], set()
            for t in (art.get("tags") or []):
                if not isinstance(t, str):
                    continue
                r = _drop_reason(t, title)
                if r:
                    dropped.append((f"tags|{title[:14]}", t.strip(), r))
                    continue
                ts = t.strip()
                if ts in seen2:
                    continue
                seen2.add(ts)
                clean.append(ts)
            if not clean:
                clean = [dflt]
                dropped.append((f"tags|{title[:14]}", "(全部被拦截)", f"兜底回填→{dflt}"))
            art["tags"] = clean

    if verbose:
        if dropped:
            print(f"🧹 关键词净化: 共拦截 {len(dropped)} 处")
            for scope, t, r in dropped:
                print(f"   ✂️ [{scope}]「{t}」→ {r}")
        else:
            print("🧹 关键词净化: 未发现违规关键词")
    return data, dropped


def _main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    path = sys.argv[1]
    import shutil
    shutil.copy2(path, path + ".bak")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    data, dropped = sanitize_news_data(data)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 已净化并写回: {path}")
    print(f"   备份: {path}.bak")
    print(f"   净化后 trendingTopics: {data.get('trendingTopics')}")


if __name__ == "__main__":
    _main()
