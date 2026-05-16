import datetime
import json
import os
import re
from ics import Calendar, Event
import pytz
import requests

# ================= 配置区域 =================
CLIST_USERNAME = os.environ.get("CLIST_USERNAME", "你的_CLIST_用户名")
CLIST_API_KEY = os.environ.get("CLIST_API_KEY", "你的_CLIST_API_KEY")
OUTPUT_ICS_PATH = "oi_competitions.ics"
# ============================================


def get_clist_contests():
    """获取 Codeforces 和 AtCoder 的比赛并按规则高强度过滤"""
    url = "https://clist.by/api/v4/contest/"
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
    """多源轮询获取洛谷比赛，完美对齐洛谷原生时间戳，过滤不属于洛谷的杂讯"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "x-requested-with": "XMLHttpRequest"
    }
    contests = []
    now_ts = int(datetime.datetime.now().timestamp())

    # 优先方案：直接死磕洛谷官方 API（只要有一次成功就能拿到 100% 正确的近期比赛）
    try:
        url = "https://www.luogu.com.cn/contest/list?_contentOnly=1"
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            raw_contests = res.json().get("currentData", {}).get("contests", {}).get("result", [])
            for c in raw_contests:
                start_ts = int(c.get("startTime"))
                end_ts = int(c.get("endTime"))
                
                if start_ts > now_ts:
                    contests.append({
                        "event": f"[洛谷] {c.get('name')}",
                        "start": datetime.datetime.fromtimestamp(start_ts, datetime.timezone.utc).isoformat(),
                        "end": datetime.datetime.fromtimestamp(end_ts, datetime.timezone.utc).isoformat(),
                        "href": f"https://www.luogu.com.cn/contest/{c.get('id')}"
                    })
            if contests:
                print("【成功】通过官方 API 成功获取到近期洛谷比赛")
                return contests
    except Exception as e:
        print(f"官方 API 尝试失败（Actions 环境正常现象）: {e}")

    # 保底方案：通过你的合法的 Clist 凭证去捞，但高强度过滤掉非洛谷的域名的垃圾数据
    try:
        url_clist = "https://clist.by/api/v4/contest/"
        utc_now = datetime.datetime.now(datetime.timezone.utc)
        params = {
            "resource_ids": "1317",  # 洛谷资源 ID
            "start__gte": utc_now.strftime("%Y-%m-%dT%H:%M:%S"),
            "order_by": "start",
            "limit": 50
        }
        headers_clist = {"Authorization": f"ApiKey {CLIST_USERNAME}:{CLIST_API_KEY}"}
        res = requests.get(url_clist, params=params, headers=headers_clist, timeout=10)
        
        if res.status_code == 200:
            objects = res.json().get("objects", [])
            for item in objects:
                # 核心过滤：比赛的链接必须包含 luogu.com 才是真正的洛谷赛，剔除俄罗斯网站垃圾数据
                if "luogu.com" in item.get("href", "") or "luogu.com" in item.get("url",个人： ""):
                    contests.append({
                        "event": f"[洛谷] {item['event']}",
                        "start": item["start"],
                        "end": item["end"],
                        "href": item["href"]
                    })
            if contests:
                print(f"【成功】通过 Clist 保底源成功提取到 {len(contests)} 场洛谷原生比赛")
                return contests
    except Exception as e:
        print(f"Clist 捞取洛谷失败: {e}")

    return contests
def main():
    c = Calendar()

    clist_data = get_clist_contests()
    luogu_data = get_luogu_contests()

    # 处理 CF 和 AtCoder
    for item in clist_data:
        title = item["event"]
        title_lower = title.lower()
        is_cf = "codeforces" in item["host"]

        final_title = ""

        if is_cf:
            # CF 过滤：只保留包含 div.1, div.2 或 div. 1+2 的比赛
            # 使用正则兼容 "div. 1", "div.2", "div.1+div.2" 等写法
            if re.search(r"div\.\s*[12]", title_lower):
                # 提取出具体的 Div 信息让标题更短，比如 "[CF] Codeforces Round 900 (Div. 2)" -> "[CF] Round 900 (Div. 2)"
                short_title = title.replace(
                    "Codeforces ", ""
                )  # 去掉冗余的 Codeforces 字样
                final_title = f"[CF] {short_title}"
            else:
                continue  # 过滤掉 div3, div4, edu 等
        else:
            # AtCoder 过滤：只保留 ABC, ARC, AGC
            # 使用正则匹配独立的 abc, arc, agc 单词
            match = re.search(r"\b(abc|arc|agc)\d+\b", title_lower)
            if match:
                # 缩写为大写的 ABC/ARC/AGC + 期数，例如 "AtCoder Beginner Contest 350" -> "[AT] ABC350"
                final_title = f"[AT] {match.group(0).upper()}"
            else:
                # 兼容部分直接写了全称但没连着写数字的情况
                if "beginner" in title_lower:
                    final_title = f"[AT] ABC"
                elif "regular" in title_lower:
                    final_title = f"[AT] ARC"
                elif "grand" in title_lower:
                    final_title = f"[AT] AGC"
                else:
                    continue  # 其余比赛不要

        # 处理时间跨天问题
        start_dt = datetime.datetime.fromisoformat(item["start"])
        end_dt = datetime.datetime.fromisoformat(item["end"])

        # 如果结束日期和开始日期不在同一天，强行把结束时间改成和开始时间同一天（只改日期，保留小时分钟，或者直接设为比赛开始后2小时）
        if start_dt.date() != end_dt.date():
            end_dt = start_dt + datetime.timedelta(hours=2)

        e = Event()
        e.name = final_title
        e.begin = start_dt.isoformat()
        e.end = end_dt.isoformat()
        e.url = item["href"]
        c.events.add(e)

    # 处理洛谷（保持原样，如果有跨天比赛也过滤一下）
    for item in luogu_data:
        start_dt = datetime.datetime.fromisoformat(item["start"])
        end_dt = datetime.datetime.fromisoformat(item["end"])

        if start_dt.date() != end_dt.date():
            end_dt = start_dt + datetime.timedelta(hours=2)

        e = Event()
        e.name = item["event"]
        e.begin = start_dt.isoformat()
        e.end = end_dt.isoformat()
        e.url = item["href"]
        c.events.add(e)

    with open(OUTPUT_ICS_PATH, "w", encoding="utf-8") as f:
        f.writelines(c.serialize_iter())
    print("日历精简版生成成功！")


if __name__ == "__main__":
    main()
