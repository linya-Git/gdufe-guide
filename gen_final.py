#!/usr/bin/env python3
"""Final output generator: clean per-tab documents + README."""
import json, os, re, sys
sys.path.insert(0, '.')
from extract import extract_sheet, parse_value, decode_blob

TABS = [("BB08J2","首页"),("g2s6tt","辅修"),("qczq10","转专业"),("blvgg9","学校历史"),("z590g4","学校概况"),("712vha","教学资源"),("wdal8t","学校章程"),("cl70mx","校训校徽"),("9orjpd","校园环境"),("et40cc","新生清单"),("hkj43t","贫困资助申请"),("7z8wjn","行李打包"),("BB08J4","广财校历"),("krb1r6","校外交通"),("4gezyk","教学楼"),("87ejds","图书馆"),("sdue2m","学分"),("BB08J5","上课时间"),("BB08J6","食堂"),("o420l8","宿舍"),("BB08J7","校内交通"),("3fy2w3","快递"),("BB08J3","常用网址"),("jza5yd","就医详解"),("ieulwh","常用公众号"),("f49t6z","学生社团"),("2flrov","加分途径")]

IMAGES = json.load(open('images/manifest.json')) if os.path.exists('images/manifest.json') else {}
IMG_FILES = {}
if os.path.exists('images'):
    for f in os.listdir('images'):
        m = re.match(r'(.+?)_(\d+)\.(jpe?g|png|gif|webp)$', f)
        if m:
            IMG_FILES.setdefault(m.group(1), []).append(f)

def clean_text(t):
    if not t:
        return ''
    # trim leading/trailing whitespace lines but keep internal newlines
    t = t.replace('\r\n', '\n')
    # collapse 3+ newlines to 2
    t = re.sub(r'\n{3,}', '\n\n', t)
    return t.strip()

def dedupe_values(vals):
    """Remove values whose text is contained within a larger sibling (merge duplicates)."""
    out = []
    texts = [v.get('text') or '' for v in vals]
    for i, v in enumerate(vals):
        t = v.get('text') or ''
        if not t and not v.get('link'):
            continue
        if t:
            # skip if contained in another larger text
            dup = False
            for j, t2 in enumerate(texts):
                if i != j and t2 and len(t2) > len(t) and t in t2:
                    dup = True
                    break
            if dup:
                continue
        out.append(v)
    return out

def render_doc(name, vals, imgs):
    L = []
    L.append(f'# {name}')
    L.append('')
    body = []
    footnotes = []
    for v in vals:
        t = clean_text(v.get('text') or '')
        link = v.get('link')
        if not t and not link:
            continue
        if link and link == 'BB08J2' and (not t or '返回' in t or '首页' in t):
            footnotes.append(f'- 返回首页：[链接](https://docs.qq.com/sheet/DUkd6Y2xOS3VnYmty?tab=BB08J2)')
            continue
        if link and link == 'BB08J2' and t == '返回PC端首页':
            continue
        if link:
            body.append(f'[{t or "链接"}](https://docs.qq.com/sheet/DUkd6Y2xOS3VnYmty?tab={link})')
        else:
            body.append(t)
    for b in body:
        for para in b.split('\n\n'):
            para = para.strip()
            if para:
                L.append(para)
                L.append('')
    for f in footnotes:
        if f not in L:
            L.append(f)
    for img in imgs:
        L.append(f'![{name}图片](images/{img})')
        L.append('')
    return '\n'.join(L).rstrip() + '\n'

def render_table(name, grid, max_col, imgs):
    L = [f'# {name}', '']
    last = len(grid) - 1
    while last >= 0 and all((not g.get('text') and not g.get('link')) for g in grid[last]):
        last -= 1
    if last < 0:
        L.append('（本表无文本内容）')
        L.append('')
    else:
        L.append('| ' + ' | '.join(f'列{c}' for c in range(max_col + 1)) + ' |')
        L.append('|' + '---|' * (max_col + 1))
        prev_vals = [''] * (max_col + 1)
        for r in range(last + 1):
            vals = []
            for c in range(max_col + 1):
                g = grid[r][c]
                t = clean_text(g.get('text') or '')
                link = g.get('link')
                if t == prev_vals[c] and not link:
                    vals.append('〃')
                    continue
                prev_vals[c] = t
                if link and link != 'BB08J2':
                    t = f'[{t or "链接"}](https://docs.qq.com/sheet/DUkd6Y2xOS3VnYmty?tab={link})'
                elif link == 'BB08J2':
                    t = f'[🏠 返回首页](https://docs.qq.com/sheet/DUkd6Y2xOS3VnYmty?tab=BB08J2)' if not t else f'{t} [🏠](https://docs.qq.com/sheet/DUkd6Y2xOS3VnYmty?tab=BB08J2)'
                vals.append(t.replace('|', '\\|').replace('\n', '<br>'))
            L.append('| ' + ' | '.join(vals) + ' |')
        L.append('')
    for img in imgs:
        L.append(f'![{name}图片](images/{img})')
        L.append('')
    return '\n'.join(L).rstrip() + '\n'

def render_txt(name, grid, max_col):
    last = len(grid) - 1
    while last >= 0 and all((not g.get('text') and not g.get('link')) for g in grid[last]):
        last -= 1
    out = [f'===== {name} =====']
    for r in range(last + 1):
        vals = []
        for c in range(max_col + 1):
            g = grid[r][c]
            t = (g.get('text') or '').strip()
            if g.get('link'):
                t = f'{t}[→{g["link"]}]' if t else f'[→{g["link"]}]'
            vals.append(t)
        line = '\t'.join(vals).rstrip('\t')
        if line.strip():
            out.append(line)
    return '\n'.join(out) + '\n'

summary = []
os.makedirs('out', exist_ok=True)
for subid, name in TABS:
    fn = f'raw/{subid}_{name}.json'
    if not os.path.exists(fn):
        continue
    d = json.load(open(fn))
    data = d.get('data', {})
    texts = data.get('initialAttributedText', {}).get('text', [])
    blob = texts[0].get('related_sheet') if texts else None
    out = extract_sheet(blob) if blob else None
    res = decode_blob(blob) if blob else None
    vals = [parse_value(v) for v in (res['values'] if res else [])]
    imgs = sorted(IMG_FILES.get(name, []))
    safe = name.replace('/', '_')
    if out and out.get('cells'):
        max_col = out.get('max_col', 0)
        max_row = out.get('max_row', 0)
        grid = []
        for r in range(max_row + 1):
            row = []
            for c in range(max_col + 1):
                row.append(out['cells'].get((r, c), {}))
            grid.append(row)
        placed = [g for row in grid for g in row if g.get('text')]
        if len(placed) >= 3:
            md = render_table(name, grid, max_col, imgs)
            csv_lines = []
            for row in grid:
                csv_lines.append(','.join('"' + (g.get('text') or '').replace('"', '""') + '"' for g in row))
            csv = '\n'.join(csv_lines) + '\n'
            txt = render_txt(name, grid, max_col)
            style = 'table'
        else:
            # doc style: use values in order
            clean_vals = dedupe_values(vals)
            md = render_doc(name, clean_vals, imgs)
            csv = '\n'.join(f'"{i+1}","{(v.get("text") or "").replace(chr(34), chr(34)*2)}"' for i, v in enumerate(clean_vals) if v.get('text')) + '\n'
            txt = '\n\n'.join(clean_text(v.get('text') or '') for v in clean_vals if v.get('text')) + '\n'
            style = 'doc'
    else:
        md = render_doc(name, dedupe_values(vals), imgs)
        csv = ''
        txt = ''
        style = 'doc'
    with open(f'out/{safe}.md', 'w') as f:
        f.write(md)
    with open(f'out/{safe}.csv', 'w') as f:
        f.write(csv)
    with open(f'out/{safe}.txt', 'w') as f:
        f.write(txt)
    nchars = sum(len((v.get('text') or '')) for v in vals)
    summary.append((name, style, len(vals), nchars, len(imgs)))

print(f'{"tab":<12}{"style":<8}{"values":<8}{"chars":<8}{"imgs":<6}')
for name, style, nv, nc, ni in summary:
    print(f'{name:<12}{style:<8}{nv:<8}{nc:<8}{ni:<6}')
