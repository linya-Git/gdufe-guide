#!/usr/bin/env python3
"""Extract all tabs -> CSV + Markdown, and build an index."""
import json, os, sys
sys.path.insert(0, '.')

from extract import extract_sheet

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

os.makedirs('out', exist_ok=True)

def cells_to_grid(cells, max_row, max_col):
    grid = []
    for r in range(max_row + 1):
        row = []
        for c in range(max_col + 1):
            info = cells.get((r, c), {})
            row.append(info)
        grid.append(row)
    return grid

def render_markdown(tab_name, grid, max_col):
    lines = [f'# {tab_name}', '']
    # find last non-empty row
    last = len(grid) - 1
    while last >= 0 and all((not g.get('text') and not g.get('link')) for g in grid[last]):
        last -= 1
    if last < 0:
        return f'# {tab_name}\n\n（空）\n'
    lines.append('| ' + ' | '.join(f'列{c}' for c in range(max_col + 1)) + ' |')
    lines.append('|' + '---|' * (max_col + 1))
    for r in range(last + 1):
        vals = []
        for c in range(max_col + 1):
            g = grid[r][c]
            t = g.get('text') or ''
            link = g.get('link')
            if link:
                t = f'[{t or "→"}](https://docs.qq.com/sheet/DUkd6Y2xOS3VnYmty?tab={link})' if t else f'[链接→{link}]'
            vals.append(t.replace('|', '\\|').replace('\n', '<br>'))
        lines.append('| ' + ' | '.join(vals) + ' |')
    return '\n'.join(lines) + '\n'

def render_text(tab_name, grid, max_col):
    """Plain text rendering: lines of tab-separated cells."""
    last = len(grid) - 1
    while last >= 0 and all((not g.get('text') and not g.get('link')) for g in grid[last]):
        last -= 1
    out = []
    for r in range(last + 1):
        vals = []
        for c in range(max_col + 1):
            g = grid[r][c]
            t = g.get('text') or ''
            link = g.get('link')
            if link:
                t = f'{t} [→tab:{link}]' if t else f'[→tab:{link}]'
            vals.append(t)
        line = '\t'.join(vals).rstrip('\t')
        if line.strip():
            out.append(line)
    return '\n'.join(out) + '\n'

def render_csv(grid, max_col):
    import csv, io
    buf = io.StringIO()
    w = csv.writer(buf)
    last = len(grid) - 1
    while last >= 0 and all((not g.get('text') and not g.get('link')) for g in grid[last]):
        last -= 1
    for r in range(last + 1):
        row = []
        for c in range(max_col + 1):
            g = grid[r][c]
            t = g.get('text') or ''
            if g.get('link'):
                t = f'{t} [tab:{g["link"]}]' if t else f'[tab:{g["link"]}]'
            row.append(t)
        w.writerow(row)
    return buf.getvalue()

summary = []
for subid, name in TABS:
    fn = f'raw/{subid}_{name}.json'
    if not os.path.exists(fn):
        continue
    d = json.load(open(fn))
    texts = d.get('data', {}).get('initialAttributedText', {}).get('text', [])
    blob = texts[0].get('related_sheet') if texts else None
    out = extract_sheet(blob) if blob else None
    if not out:
        summary.append((name, 'FAILED'))
        continue
    grid = cells_to_grid(out['cells'], out['max_row'], out['max_col'])
    safe = name.replace('/', '_')
    with open(f'out/{safe}.md', 'w') as f:
        f.write(render_markdown(name, grid, out['max_col']))
    with open(f'out/{safe}.csv', 'w') as f:
        f.write(render_csv(grid, out['max_col']))
    with open(f'out/{safe}.txt', 'w') as f:
        f.write(render_text(name, grid, out['max_col']))
    ntext = sum(1 for r in grid for g in r if g.get('text'))
    summary.append((name, f'{out["max_row"]+1}x{out["max_col"]+1}', f'{ntext} cells with text'))

for s in summary:
    print(s)
