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
        "limit": 100
    }
    headers = {"Authorization": f"ApiKey {CLIST_USERNAME}:{CLIST_API_KEY}"}

    try:
        if not CLIST_USERNAME or "你的" in CLIST_USERNAME:
            response = requests.get(url, params=params, timeout=10)
        else:
            response = requests.get(url, params=params, headers=headers, timeout=10)

        if response.status_code == 200:
            return response.json().get("objects", [])
    except Exception as e:
        print(f"获取 Clist 比赛失败: {e}")
    return []

def get_local_luogu_contests():
    """从本地 Node.js 脚本抓好的 json 文件中安全加载洛谷比赛"""
    contests = []
    if os.path.exists("luogu.json"):
        try:
            with open("luogu.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                raw_contests = data.get("currentData", {}).get("contests", {}).get("result", [])
                now_ts = int(datetime.datetime.now().timestamp())

                for c in raw_contests:
                    start_ts = int(c.get("startTime", 0))
                    end_ts = int(c.get("endTime", 0))
                    
                    if start_ts > now_ts:
                        contests.append({
                            "event": f"[洛谷] {c.get('name')}",
                            "start": datetime.datetime.fromtimestamp(start_ts, datetime.timezone.utc).isoformat(),
                            "end": datetime.datetime.fromtimestamp(end_ts, datetime.timezone.utc).isoformat(),
                            "href": f"https://www.luogu.com.cn/contest/{c.get('id')}"
                        })
                print(f"【成功】从本地文件加载了 {len(contests)} 场洛谷原生比赛！")
        except Exception as e:
            print(f"解析本地洛谷 JSON 失败: {e}")
    else:
        print("未发现本地洛谷数据文件，跳过洛谷部分。")
    return contests

def main():
    c = Calendar()

    clist_data = get_clist_contests()
    luogu_data = get_local_luogu_contests()

    # 处理 CF 和 AtCoder
    for item in clist_data:
        title = item["event"]
        title_lower = title.lower()
        is_cf = "codeforces" in item["host"]

        final_title = ""

        if is_cf:
            if re.search(r"div\.\s*[12]", title_lower) or "1 + 2" in title_lower:
                short_title = title.replace("Codeforces ", "")
                final_title = f"[CF] {short_title}"
            else:
                continue
        else:
            match = re.search(r"\b(abc|arc|agc)\d+\b", title_lower)
            if match:
                final_title = f"[AT] {match.group(0).upper()}"
            else:
                if "beginner" in title_lower:
                    final_title = "[AT] ABC"
                elif "regular" in title_lower:
                    final_title = "[AT] ARC"
                elif "grand" in title_lower:
                    final_title = "[AT] AGC"
                else:
                    continue

        start_dt = datetime.datetime.fromisoformat(item["start"].replace("Z", "+00:00"))
        end_dt = datetime.datetime.fromisoformat(item["end"].replace("Z", "+00:00"))

        if start_dt.date() != end_dt.date():
            end_dt = start_dt + datetime.timedelta(hours=2)

        e = Event()
        e.name = final_title
        e.begin = start_dt.isoformat()
        e.end = end_dt.isoformat()
        e.url = item["href"]
        c.events.add(e)

    # 处理洛谷
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
    print("日历精简版合并生成成功！")

if __name__ == "__main__":
    main()
