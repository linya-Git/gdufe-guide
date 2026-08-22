#!/usr/bin/env python3
"""Fetch all tabs of the Tencent Docs sheet and extract cell data."""
import json, os, subprocess, sys, time
sys.path.insert(0, '.')

TABS = [
    ("BB08J2", "首页"), ("g2s6tt", "辅修"), ("qczq10", "转专业"),
    ("blvgg9", "学校历史"), ("z590g4", "学校概况"), ("712vha", "教学资源"),
    ("wdal8t", "学校章程"), ("cl70mx", "校训校徽"), ("9orjpd", "校园环境"),
    ("et40cc", "新生清单"), ("hkj43t", "贫困资助申请"), ("7z8wjn", "行李打包"),
    ("BB08J4", "广财校历"), ("krb1r6", "校外交通"), ("4gezyk", "教学楼"),
    ("87ejds", "图书馆"), ("sdue2m", "学分"), ("BB08J5", "上课时间"),
    ("BB08J6", "食堂"), ("o420l8", "宿舍"), ("BB08J7", "校内交通"),
    ("3fy2w3", "快递"), ("BB08J3", "常用网址"), ("jza5yd", "就医详解"),
    ("ieulwh", "常用公众号"), ("f49t6z", "学生社团"), ("2flrov", "加分途径"),
]

TOK = open('cookies.txt').read()
import re
m = re.search(r'\tTOK\t\S+\t(\S+)', TOK)
TOK = m.group(1) if m else ''

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
REF = "https://docs.qq.com/sheet/DUkd6Y2xOS3VnYmty"

os.makedirs('raw', exist_ok=True)

def fetch(subid, startrow, endrow):
    url = (f"https://docs.qq.com/dop-api/get/sheet?padId=300000000%24RGzclNKugbkr"
           f"&subId={subid}&startrow={startrow}&endrow={endrow}&xsrf={TOK}"
           f"&_r=0.12345&outformat=1&normal=1&preview_token=&nowb=1&needSheetState=1&sliceStates=1")
    r = subprocess.run(['curl', '-sS', '--max-time', '90', '-A', UA,
                        '-H', f'Referer: {REF}', '-H', 'Origin: https://docs.qq.com',
                        '-b', 'cookies.txt', url], capture_output=True, text=True)
    return r.stdout

for subid, name in TABS:
    fname = f'raw/{subid}_{name}.json'
    if os.path.exists(fname) and os.path.getsize(fname) > 100:
        print(f'skip {name} (exists)')
        continue
    data = fetch(subid, 0, 4000)
    try:
        j = json.loads(data)
    except Exception:
        print(f'{name}: BAD JSON ({len(data)}B)')
        continue
    if j.get('retcode') != 0:
        print(f'{name}: retcode={j.get("retcode")} errmsg={j.get("errmsg")}')
        continue
    open(fname, 'w').write(data)
    texts = j.get('data', {}).get('initialAttributedText', {}).get('text', [])
    print(f'{name} ({subid}): {len(data)}B, blob items={len(texts)}')
    time.sleep(0.3)
