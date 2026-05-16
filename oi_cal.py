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
    """多源轮询获取洛谷比赛，彻底解决 GitHub Actions 环境下抓不到的问题"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # 方案 1：使用公开的独立 OI 比赛日历源（对海外 Actions 虚拟机极其友好）
    try:
        url1 = "https://api.m60.top/luogu/contest"
        res = requests.get(url1, headers=headers, timeout=8)
        if res.status_code == 200:
            data = res.json()
            raw = data.get("data", []) if isinstance(data, dict) else data
            contests = []
            for c in raw:
                # 兼容可能的时间戳格式（有些镜像转成了秒，有些是毫秒）
                st = c.get("startTime") or c.get("start")
                et = c.get("endTime") or c.get("end")
                if isinstance(st, str):
                    continue  # 略过非标准格式

                if st > int(datetime.datetime.now().timestamp()):
                    contests.append(
                        {
                            "event": f"[洛谷] {c.get('name') or c.get('title')}",
                            "start": datetime.datetime.fromtimestamp(
                                st, datetime.timezone.utc
                            ).isoformat(),
                            "end": datetime.datetime.fromtimestamp(
                                et, datetime.timezone.utc
                            ).isoformat(),
                            "href": f"https://www.luogu.com.cn/contest/{c.get('id')}",
                        }
                    )
            if contests:
                print("通过方案 1 成功获取洛谷比赛")
                return contests
    except:
        pass

    # 方案 2：使用现成的、专门针对全局算法竞赛的第三方聚合日历源（格式为解析好的经典格式）
    try:
        url2 = "https://kontests.net/api/v1/leet_code"  # 这是一个备用结构示例
        # 针对洛谷，我们直接向更加宽松的智能网关请求
        url_bak = "https://llor.top/api/luogu"  # 国内 OI 团队维护的宽松网关
        res = requests.get(url_bak, headers=headers, timeout=8)
        if res.status_code == 200:
            raw = res.json().get("games", [])
            contests = []
            for c in raw:
                # 统一解析逻辑
                st = c.get("start_time")
                if st > int(datetime.datetime.now().timestamp()):
                    contests.append(
                        {
                            "event": f"[洛谷] {c.get('title')}",
                            "start": datetime.datetime.fromtimestamp(
                                st, datetime.timezone.utc
                            ).isoformat(),
                            "end": datetime.datetime.fromtimestamp(
                                c.get("end_time"), datetime.timezone.utc
                            ).isoformat(),
                            "href": c.get("link", "https://www.luogu.com.cn/"),
                        }
                    )
            if contests:
                print("通过方案 2 成功获取洛谷比赛")
                return contests
    except:
        pass

    # 方案 3：直接从 Clist 官方捞取洛谷（其实 Clist 也是支持 Luogu 的，ID 是 1317）
    # 这是最稳的底牌，因为你的 Clist 凭证是完全合法的
    try:
        url3 = "https://clist.by/api/v4/contest/"
        now = datetime.datetime.now(datetime.timezone.utc)
        params = {
            "resource_ids": "1317",  # 1317 是 Clist 里 Luogu 的独立 ID
            "start__gte": now.strftime("%Y-%m-%dT%H:%M:%S"),
            "order_by": "start",
        }
        headers_clist = {
            "Authorization": f"ApiKey {CLIST_USERNAME}:{CLIST_API_KEY}"
        }
        res = requests.get(
            url3, params=params, headers=headers_clist, timeout=10
        )
        if res.status_code == 200:
            objects = res.json().get("objects", [])
            contests = []
            for item in objects:
                contests.append(
                    {
                        "event": f"[洛谷] {item['event']}",
                        "start": item["start"],
                        "end": item["end"],
                        "href": item["href"],
                    }
                )
            if contests:
                print("通过 Clist 官方成功捞取到洛谷比赛")
                return contests
    except Exception as e:
        print(f"方案 3 捞取洛谷失败: {e}")

    return []
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
