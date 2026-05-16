import datetime
import json
import re
from ics import Calendar, Event
import pytz
import requests

# ================= 配置区域 =================
# 1. Clist.by 的 API 凭证 (请去 https://clist.by/api/v4/doc/ 注册账号免费获取)
# 如果不填，部分请求可能会受限
CLIST_USERNAME = "yzkadbq"
CLIST_API_KEY = "b7af68a112d7a858a8a0d92b6bb9fcf1da75e092 "

# 2. 生成的 ics 文件保存路径（如果运行可以写绝对路径，如果在服务器可以挂在 Web 服务下）
OUTPUT_ICS_PATH = "oi_competitions.ics"
# ============================================


def get_clist_contests():
    """获取 Codeforces 和 AtCoder 的比赛"""
    url = "https://clist.by/api/v4/contest/"
    # 过滤出未来两个月内的 CF (resource_id=1) 和 AtCoder (resource_id=93)
    now = datetime.datetime.now(datetime.timezone.utc)
    end_time = now + datetime.timedelta(days=60)

    params = {
        "resource_ids": "1,93",  # 1 是 Codeforces, 93 是 AtCoder
        "start__gte": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "start__lte": end_time.strftime("%Y-%m-%dT%H:%M:%S"),
        "order_by": "start",
        "limit": 100,
    }
    headers = {"Authorization": f"ApiKey {CLIST_USERNAME}:{CLIST_API_KEY}"}

    try:
        # 如果没有填写凭证，尝试匿名访问（有频率限制）
        if not CLIST_USERNAME or "你的" in CLIST_USERNAME:
            response = requests.get(url, params=params, timeout=10)
        else:
            response = requests.get(
                url, params=params, headers=headers, timeout=10
            )

        if response.status_code == 200:
            return response.json().get("objects", [])
    except Exception as e:
        print(f"获取 Clist 比赛失败: {e}")
    return []


def get_luogu_contests():
    """获取洛谷比赛"""
    # 洛谷有反爬，需要带上通用的 User-Agent
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "x-requested-with": "XMLHttpRequest",
    }
    url = "https://www.luogu.com.cn/contest/list?_contentOnly=1"

    contests = []
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            # 洛谷返回的比赛列表
            raw_contests = data.get("currentData", {}).get(
                "contests", {}
            ).get("result", [])

            for c in raw_contests:
                # 状态 0 或 1 通常代表未开始/进行中，这里只拿未开始的
                # 洛谷的时间戳是秒
                start_ts = c.get("startTime")
                end_ts = c.get("endTime")
                now_ts = int(datetime.datetime.now().timestamp())

                if start_ts > now_ts:
                    contests.append(
                        {
                            "event": f"[洛谷] {c.get('name')}",
                            "start": datetime.datetime.fromtimestamp(
                                start_ts, datetime.timezone.utc
                            ).isoformat(),
                            "end": datetime.datetime.fromtimestamp(
                                end_ts, datetime.timezone.utc
                            ).isoformat(),
                            "href": f"https://www.luogu.com.cn/contest/{c.get('id')}",
                        }
                    )
    except Exception as e:
        print(f"获取洛谷比赛失败: {e}")
    return contests


def main():
    c = Calendar()

    # 1. 抓取数据
    print("正在获取 Codeforces & AtCoder 比赛...")
    clist_data = get_clist_contests()
    print(f"成功获取 {len(clist_data)} 场 CF/AtCoder 比赛")

    print("正在获取洛谷比赛...")
    luogu_data = get_luogu_contests()
    print(f"成功获取 {len(luogu_data)} 场洛谷比赛")

    # 2. 解析并解析并写入 iCalendar
    # 写入 CF 和 AtCoder
    for item in clist_data:
        e = Event()
        # 润色标题，美化显示
        platform = "CF" if "codeforces" in item["host"] else "AtCoder"
        e.name = f"[{platform}] {item['event']}"

        # Clist 返回的时间已经是 UTC 字符串
        e.begin = item["start"]
        e.end = item["end"]
        e.url = item["href"]
        e.description = f"比赛链接: {item['href']}\n数据来源: Clist.by"
        c.events.add(e)

    # 写入洛谷
    for item in luogu_data:
        e = Event()
        e.name = item["event"]
        e.begin = item["start"]
        e.end = item["end"]
        e.url = item["href"]
        e.description = f"比赛链接: {item['href']}\n数据来源: 洛谷"
        c.events.add(e)

    # 3. 保存文件
    with open(OUTPUT_ICS_PATH, "w", encoding="utf-8") as f:
        f.writelines(c.serialize_iter())
    print(f"日历文件已成功生成: {OUTPUT_ICS_PATH}")


if __name__ == "__main__":
    main()
