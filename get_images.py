#!/usr/bin/env python3
"""Extract image URLs from all tabs and download them."""
import json, os, re, subprocess, sys, base64, zlib

TABS = [("BB08J2","首页"),("g2s6tt","辅修"),("qczq10","转专业"),("blvgg9","学校历史"),("z590g4","学校概况"),("712vha","教学资源"),("wdal8t","学校章程"),("cl70mx","校训校徽"),("9orjpd","校园环境"),("et40cc","新生清单"),("hkj43t","贫困资助申请"),("7z8wjn","行李打包"),("BB08J4","广财校历"),("krb1r6","校外交通"),("4gezyk","教学楼"),("87ejds","图书馆"),("sdue2m","学分"),("BB08J5","上课时间"),("BB08J6","食堂"),("o420l8","宿舍"),("BB08J7","校内交通"),("3fy2w3","快递"),("BB08J3","常用网址"),("jza5yd","就医详解"),("ieulwh","常用公众号"),("f49t6z","学生社团"),("2flrov","加分途径")]

URL_RE = re.compile(rb'https?://docimg\d+\.docs\.qq\.com/image/[A-Za-z0-9_\-]+\.(?:jpeg|jpg|png|gif|webp)(?:\?[^\x00-\x1f\x7f\s"\']{0,100})?')
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

os.makedirs('images', exist_ok=True)
manifest = {}
seen = set()
for subid, name in TABS:
    fn = f'raw/{subid}_{name}.json'
    if not os.path.exists(fn):
        continue
    d = json.load(open(fn))
    texts = d.get('data', {}).get('initialAttributedText', {}).get('text', [])
    urls = []
    for t in texts:
        blob = t.get('related_sheet')
        if not blob:
            continue
        try:
            dec = zlib.decompress(base64.b64decode(blob))
        except Exception:
            dec = base64.b64decode(blob)
        urls += [u.decode() for u in URL_RE.findall(dec)]
    urls = list(dict.fromkeys(urls))
    manifest[name] = urls
    for i, u in enumerate(urls):
        if u in seen:
            continue
        seen.add(u)
        ext = 'jpg'
        m = re.search(r'\.(jpeg|jpg|png|gif|webp)', u)
        if m:
            ext = m.group(1)
        out = f'images/{name}_{i+1}.{ext}'
        r = subprocess.run(['curl', '-sS', '-L', '--max-time', '40', '-A', UA,
                            '-H', 'Referer: https://docs.qq.com/', u, '-o', out],
                           capture_output=True)
        size = os.path.getsize(out) if os.path.exists(out) else 0
        head = open(out, 'rb').read(4) if size else b''
        ok = size > 1000 and head[:2] in (b'\xff\xd8', b'\x89P', b'GIF8', b'RIFF')
        print(f'{name} #{i+1}: {size}B {"OK" if ok else "FAIL?"} {u[:70]}')
        if not ok:
            os.remove(out) if os.path.exists(out) else None

json.dump(manifest, open('images/manifest.json', 'w'), ensure_ascii=False, indent=1)
print('done, total unique:', len(seen))
