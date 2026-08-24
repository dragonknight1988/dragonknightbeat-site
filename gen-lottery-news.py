#!/usr/bin/env python3
"""
彩票新闻生成脚本
部署位置: /opt/dragonknightbeat-site/gen-lottery-news.py
输出: /var/www/dragonknightbeat.com/daily-lottery-news.json
"""

import json
import random
from datetime import datetime, timedelta
import os

# 新闻模板库
NEWS_TEMPLATES = {
    "winning": [
        {
            "title": "双色球开出{amount}大奖！{city}彩民守号{years}年终圆梦",
            "content": "昨晚双色球第{issue}期开奖，一等奖开出{count}注，单注奖金{amount}万元。其中一位来自{city}的彩民凭借一张{price}元单式票，成功收获{amount}万元大奖。据了解，这位彩民坚持守号{years}年，终于梦想成真。",
            "image": "trophy.fill"
        },
        {
            "title": "大乐透{count}注一等奖花落{count2}地，奖池累计超{pool}亿",
            "content": "超级大乐透第{issue}期开奖，前区开出{front}，后区开出{back}。本期一等奖开出{count}注，单注奖金{amount}万元，分别花落{cities}。奖池金额累计超过{pool}亿元。",
            "image": "star.fill"
        },
        {
            "title": "{age}后小伙中双色球{amount}万：准备{plan}",
            "content": "一位{age}后小伙在双色球第{issue}期中得一等奖{amount}万元。领奖时他激动表示，这笔钱将用于{plan}。他说买彩票只是娱乐，没想到真的中了大奖。",
            "image": "person.fill"
        }
    ],
    "analysis": [
        {
            "title": "双色球近期走势分析：红球{nums}值得关注",
            "content": "近{days}期双色球开奖数据显示，红球{nums}出现频率较高，分别出现{freq}次。蓝球方面，{blue}表现活跃。建议关注这些号码的后续表现。",
            "image": "chart.line.uptrend.xyaxis"
        },
        {
            "title": "大乐透冷号回补：前区{nums}已遗漏{days}期",
            "content": "根据大乐透近{days2}期开奖数据，前区号码{nums}已连续遗漏{days}期，达到历史平均遗漏值。从概率角度看，这两个号码近期回补的可能性较大。",
            "image": "clock.fill"
        }
    ],
    "tips": [
        {
            "title": "选号技巧：如何利用{method}选号",
            "content": "很多彩民喜欢用{method}选号，但直接使用可能范围太窄。建议将{method}与其他幸运数字组合，或者将{method}拆分成多个数字使用。{example}",
            "image": "lightbulb.fill"
        },
        {
            "title": "选号技巧：{topic}的黄金比例",
            "content": "根据历史数据分析，中奖号码中{topic}比例约为{ratio}较为理想。建议在选号时，选择{advice}的组合。",
            "image": "flame.fill"
        }
    ],
    "fun": [
        {
            "title": "趣闻：彩民用{source}买彩票中了{amount}万",
            "content": "一位彩民偶然看到{source}，觉得这个号码很吉利，就用这个号码买了一张彩票。没想到竟然中了{amount}万元大奖！他说以后要多留意身边的数字。",
            "image": "car.fill"
        },
        {
            "title": "趣闻：做梦梦到号码中了{amount}万",
            "content": "一位彩民在梦中梦到一组数字，醒来后赶紧记下来去买彩票。结果真的中了{amount}万元！他说这是他人生中最神奇的经历。",
            "image": "moon.fill"
        }
    ],
    "policy": [
        {
            "title": "双色球游戏规则调整公告",
            "content": "中国福利彩票发行管理中心发布公告，自{date}起，双色球游戏规则将进行微调。一等奖奖金分配比例有所调整，具体详情请关注官方公告。",
            "image": "doc.text.fill"
        },
        {
            "title": "{type}派奖活动即将开始",
            "content": "{type}派奖活动将于下月启动，预计持续{days}天。活动期间，一等奖奖金将有所提升，并增加二等奖派奖。详情请关注{org}官方公告。",
            "image": "megaphone.fill"
        }
    ]
}

# 数据池
CITIES = ["广东", "浙江", "四川", "江苏", "山东", "北京", "上海", "湖北", "湖南", "福建", "河南", "河北", "安徽", "陕西", "重庆"]
AGES = ["80", "90", "00"]
PLANS = ["创业开公司", "买房安家", "投资理财", "孝敬父母", "环游世界", "继续深造"]
METHODS = ["生日数字", "车牌号", "手机号", "纪念日", "幸运数字", "梦境数字"]
SOURCES = ["一辆车牌号很特别的车", "一张老照片上的日期", "一个陌生电话号码", "孩子的成绩单编号", "超市小票上的号码"]

def generate_issue():
    """生成期号"""
    now = datetime.now()
    year = now.strftime("%Y")
    day_of_year = now.timetuple().tm_yday
    return f"{year}{day_of_year:03d}"

def generate_random_numbers(count, min_val, max_val):
    """生成随机号码"""
    return sorted(random.sample(range(min_val, max_val + 1), count))

def fill_winning_template(template):
    """填充中奖新闻模板"""
    issue = generate_issue()
    amount = random.choice([500, 600, 700, 800, 1000, 1500, 2000])
    city = random.choice(CITIES)
    years = random.randint(1, 10)
    age = random.choice(AGES)
    plan = random.choice(PLANS)
    count = random.randint(1, 5)
    pool = random.randint(5, 15)
    price = random.choice([10, 20, 50])
    
    front_nums = generate_random_numbers(5, 1, 35)
    back_nums = generate_random_numbers(2, 1, 12)
    
    title = template["title"].format(
        amount=amount, city=city, years=years, age=age,
        issue=issue, count=count, pool=pool, plan=plan,
        count2=random.randint(2, 3), cities="、".join(random.sample(CITIES, 2)),
        price=price
    )
    
    content = template["content"].format(
        amount=amount, city=city, years=years, age=age,
        issue=issue, count=count, pool=pool, plan=plan,
        front=" ".join([f"{n:02d}" for n in front_nums]),
        back=" ".join([f"{n:02d}" for n in back_nums]),
        cities="、".join(random.sample(CITIES, 2)),
        price=price
    )
    
    return {"title": title, "content": content, "image": template["image"]}

def fill_analysis_template(template):
    """填充分析新闻模板"""
    nums = generate_random_numbers(3, 1, 33)
    blue = generate_random_numbers(1, 1, 16)[0]
    days = random.randint(10, 30)
    freq = [random.randint(2, 5) for _ in range(3)]
    
    title = template["title"].format(
        nums="、".join([f"{n:02d}" for n in nums]),
        days=days
    )
    
    content = template["content"].format(
        nums="、".join([f"{n:02d}" for n in nums]),
        blue=f"{blue:02d}",
        days=days,
        days2=random.randint(20, 50),
        freq=freq
    )
    
    return {"title": title, "content": content, "image": template["image"]}

def fill_tips_template(template):
    """填充技巧新闻模板"""
    method = random.choice(METHODS)
    topic = random.choice(["冷热号搭配", "奇偶比", "连号出现", "和值范围"])
    ratio = random.choice(["3:3", "4:2", "2:4"])
    
    examples = {
        "生日数字": "例如1990年3月15日，可以拆分成1、9、9、0、3、1、5等数字",
        "车牌号": "例如京A12345，可以使用1、2、3、4、5这组数字",
        "手机号": "例如138****5678，可以使用尾号5、6、7、8",
        "纪念日": "例如结婚纪念日2020年10月1日，可以使用2、0、1、0、1",
        "幸运数字": "每个人都有自己的幸运数字，可以结合其他数字使用",
        "梦境数字": "梦中出现的数字往往有特殊含义，值得尝试"
    }
    
    advice_map = {
        "冷热号搭配": "3个热号+3个温号",
        "奇偶比": "奇偶比例3:3或4:2",
        "连号出现": "1-2组连号组合",
        "和值范围": "和值控制在80-130区间"
    }
    
    title = template["title"].format(method=method, topic=topic)
    content = template["content"].format(
        method=method, topic=topic, ratio=ratio,
        example=examples.get(method, ""),
        advice=advice_map.get(topic, "合理搭配")
    )
    
    return {"title": title, "content": content, "image": template["image"]}

def fill_fun_template(template):
    """填充趣味新闻模板"""
    source = random.choice(SOURCES)
    amount = random.choice([300, 500, 800, 1000])
    
    title = template["title"].format(source=source, amount=amount)
    content = template["content"].format(source=source, amount=amount)
    
    return {"title": title, "content": content, "image": template["image"]}

def fill_policy_template(template):
    """填充公告新闻模板"""
    now = datetime.now()
    next_month = now + timedelta(days=30)
    date_str = next_month.strftime("%Y年%m月%d日")
    
    lottery_types = ["双色球", "大乐透", "福彩3D", "排列三"]
    orgs = ["中国福利彩票", "中国体育彩票"]
    
    title = template["title"].format(
        type=random.choice(lottery_types),
        date=date_str
    )
    content = template["content"].format(
        type=random.choice(lottery_types),
        days=random.randint(20, 40),
        org=random.choice(orgs),
        date=date_str
    )
    
    return {"title": title, "content": content, "image": template["image"]}

def generate_news():
    """生成新闻列表"""
    news_list = []
    news_id = 1
    
    # 为每个分类生成新闻
    for category, templates in NEWS_TEMPLATES.items():
        for template in templates:
            # 根据分类选择填充函数
            if category == "winning":
                filled = fill_winning_template(template)
            elif category == "analysis":
                filled = fill_analysis_template(template)
            elif category == "tips":
                filled = fill_tips_template(template)
            elif category == "fun":
                filled = fill_fun_template(template)
            elif category == "policy":
                filled = fill_policy_template(template)
            else:
                continue
            
            news_item = {
                "id": f"{category[0]}{news_id:03d}",
                "title": filled["title"],
                "content": filled["content"],
                "category": category,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "image": filled["image"]
            }
            news_list.append(news_item)
            news_id += 1
    
    # 随机打乱顺序
    random.shuffle(news_list)
    
    return news_list

def main():
    """主函数"""
    # 生成新闻
    news = generate_news()
    
    # 构建输出数据
    output = {
        "version": "1.0",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(news),
        "news": news
    }
    
    # 输出到标准输出（用于 cron 任务）
    print(json.dumps(output, ensure_ascii=False, indent=2))
    
    # 同时写入文件
    output_path = "/var/www/dragonknightbeat.com/daily-lottery-news.json"
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 已写入: {output_path}")
    except Exception as e:
        print(f"\n❌ 写入失败: {e}")

if __name__ == "__main__":
    main()
