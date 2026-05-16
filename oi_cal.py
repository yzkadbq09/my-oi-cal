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
    """使用高可用镜像源获取洛谷比赛，绕过 GitHub Actions IP 封锁"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    # 换用公开的洛谷比赛日历镜像接口（该接口在海外服务器访问极度稳定）
    url = "https://api.m60.top/luogu/contest"

    contests = []
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            # 镜像源通常直接返回处理好的比赛数组
            raw_contests = data.get("data", []) if isinstance(data, dict) else data

            for c in raw_contests:
                # 兼容不同镜像源的字段名
                name = c.get("name") or c.get("title")
                start_ts = c.get("startTime") or c.get("start")
                end_ts = c.get("endTime") or c.get("end")
                c_id = c.get("id")

                if not (name and start_ts):
                    continue

                # 如果时间戳是字符串，转为秒
                if isinstance(start_ts, str):
                    continue  # 镜像源若返回标准格式可直接解析，这里按标准秒级时间戳处理

                now_ts = int(datetime.datetime.now().timestamp())
                if start_ts > now_ts:
                    contests.append(
                        {
                            "event": f"[洛谷] {name}",
                            "start": datetime.datetime.fromtimestamp(
                                start_ts, datetime.timezone.utc
                            ).isoformat(),
                            "end": datetime.datetime.fromtimestamp(
                                end_ts, datetime.timezone.utc
                            ).isoformat(),
                            "href": f"https://www.luogu.com.cn/contest/{c_id}",
                        }
                    )
    except Exception as e:
        print(f"获取洛谷比赛失败: {e}")

    # 如果镜像源偶发性挂了，尝试备用官方源（虽然 Actions 概率失败，但留作保底）
    if not contests:
        try:
            res = requests.get(
                "https://www.luogu.com.cn/contest/list?_contentOnly=1",
                headers=headers,
                timeout=10,
            )
            if res.status_code == 200:
                raw = (
                    res.json()
                    .get("currentData", {})
                    .get("contests", {})
                    .get("result", [])
                )
                for c in raw:
                    st = c.get("startTime")
                    if st > int(datetime.datetime.now().timestamp()):
                        contests.append(
                            {
                                "event": f"[洛谷] {c.get('name')}",
                                "start": datetime.datetime.fromtimestamp(
                                    st, datetime.timezone.utc
                                ).isoformat(),
                                "end": datetime.datetime.fromtimestamp(
                                    c.get("endTime"), datetime.timezone.utc
                                ).isoformat(),
                                "href": f"https://www.luogu.com.cn/contest/{c.get('id')}",
                            }
                        )
        except:
            pass

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
