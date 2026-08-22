#!/usr/bin/env python3
"""Extract (row, col, value, link) from Tencent Docs related_sheet blob."""
import base64, json, re, sys, zlib

def varint_at(b, i):
    r = 0; s = 0
    while i < len(b):
        x = b[i]; i += 1
        r |= (x & 0x7f) << s
        if not x & 0x80:
            return r, i
        s += 7
    raise IndexError

def parse_fields(b):
    out = []
    i = 0
    while i < len(b):
        try:
            tag, i = varint_at(b, i)
        except IndexError:
            break
        fnum, wt = tag >> 3, tag & 7
        if fnum == 0:
            break
        if wt == 0:
            try:
                v, i = varint_at(b, i)
            except IndexError:
                break
            out.append((fnum, ('varint', v)))
        elif wt == 2:
            try:
                l, i = varint_at(b, i)
            except IndexError:
                break
            if i + l > len(b):
                break
            out.append((fnum, b[i:i+l]))
            i += l
        else:
            break
    return out

def get_field(b, fn):
    for f, v in parse_fields(b):
        if f == fn:
            return v
    return None

def decode_blob(blob_b64):
    raw = base64.b64decode(blob_b64)
    try:
        data = zlib.decompress(raw)
    except Exception:
        data = raw
    body = get_field(data, 1)
    if not isinstance(body, bytes):
        return None
    f5s = [v for fn, v in parse_fields(body) if fn == 5 and isinstance(v, bytes)]
    big = f5s[-1]
    f19 = get_field(big, 19)
    if not isinstance(f19, bytes):
        return None
    result = {'meta': None, 'values': [], 'grid': []}
    for fn, v in parse_fields(f19):
        if fn == 3 and isinstance(v, bytes) and len(v) < 50:
            result['meta'] = v
        elif fn == 5 and isinstance(v, bytes):
            for _, cell in parse_fields(v):
                if isinstance(cell, bytes):
                    result['values'].append(cell)
        elif fn == 6 and isinstance(v, bytes):
            result['grid'].append(v)
    return result

def parse_value(b):
    """Return dict {text, link} for a value entry. Handles plain strings,
    nested strings, and rich text (concatenating paragraphs)."""
    text = None
    link = None

    def try_str(v):
        try:
            return v.decode('utf-8')
        except Exception:
            return None

    FONTS = {'FangSong', 'KaiTi', 'Microsoft YaHei', 'SimSun', 'SimHei', '汉仪中黑', '微软雅黑', '等线', '宋体', '黑体', '楷体', '仿宋', 'Times New Roman', 'Arial', 'Helvetica', 'FangSong_GB2312', 'KaiTi_GB2312'}
    def looks_like_text(s):
        if not s:
            return False
        if not all(c >= ' ' or c in '\n\t' for c in s):
            return False
        if len(s) <= 8 and re.fullmatch(r'[0-9A-Fa-f]{6,8}', s):
            return False
        if s in FONTS:
            return False
        if len(s) == 1 and not ('\u4e00' <= s <= '\u9fff'):
            return False
        return True

    # field 1: plain string (direct or {1: str})
    v = get_field(b, 1)
    if isinstance(v, bytes):
        s = try_str(v)
        if s is not None and looks_like_text(s):
            text = s
        else:
            inner = get_field(v, 1)
            if isinstance(inner, bytes):
                s2 = try_str(inner)
                if s2 is not None and looks_like_text(s2):
                    text = s2

    # field 2 or 3: rich text (may be repeated)
    all_parts = []
    all_link = None
    def walk(v3, parts, in_link=False):
        for fnx, vx in parse_fields(v3):
            if not isinstance(vx, bytes):
                continue
            if fnx == 7:
                v711 = get_field(vx, 11)
                if isinstance(v711, bytes):
                    v1 = get_field(v711, 1)
                    if isinstance(v1, bytes):
                        nonlocal_link[0] = try_str(v1)
                walk(vx, parts, True)
                continue
            if in_link:
                walk(vx, parts, True)
                continue
            sub = parse_fields(vx)
            if sub and sub[0][0] == 1 and isinstance(sub[0][1], bytes):
                s = try_str(sub[0][1])
                if s is not None and looks_like_text(s):
                    parts.append(s)
                    continue
            s = try_str(vx)
            if s is not None and looks_like_text(s):
                parts.append(s)
                continue
            walk(vx, parts, in_link)
    for fn, v in parse_fields(b):
        if fn in (2, 3) and isinstance(v, bytes):
            parts = []
            nonlocal_link = [None]
            walk(v, parts)
            all_parts.extend(parts)
            if nonlocal_link[0]:
                all_link = nonlocal_link[0]
    # fallback: raw field-1 string (may be huge) if nothing found
    if not all_parts and not all_link:
        v1 = get_field(b, 1)
        if isinstance(v1, bytes):
            s = try_str(v1)
            if s is not None and looks_like_text(s):
                all_parts.append(s)
    if all_parts:
        text = ''.join(all_parts)
    if all_link:
        link = all_link

    if text is None:
        v2 = get_field(b, 2)
        if isinstance(v2, tuple):
            text = str(v2[1])
    return {'text': text, 'link': link}

def parse_grid_entry(b):
    """Return dict {row, col, style_ref, value_idx, link}."""
    row = col = None
    value_idx = None
    link = None
    for fn, v in parse_fields(b):
        if fn == 1 and isinstance(v, tuple):
            row = v[1]
        elif fn == 2 and isinstance(v, tuple):
            col = v[1]
        elif fn == 3 and isinstance(v, bytes):
            # style: {1: font, 2: {1: value_idx}, 4: {1: style_ref}, 8: hyperlink}
            for fn2, v2 in parse_fields(v):
                if fn2 == 2 and isinstance(v2, bytes):
                    for fn3, v3 in parse_fields(v2):
                        if fn3 == 1 and isinstance(v3, tuple):
                            value_idx = v3[1]
                elif fn2 == 8 and isinstance(v2, bytes):
                    for fn3, v3 in parse_fields(v2):
                        if fn3 == 11 and isinstance(v3, bytes):
                            for fn4, v4 in parse_fields(v3):
                                if fn4 == 1 and isinstance(v4, bytes):
                                    try:
                                        link = v4.decode('utf-8')
                                    except Exception:
                                        pass
    return {'row': row, 'col': col, 'value_idx': value_idx, 'link': link}

def extract_sheet(blob_b64):
    res = decode_blob(blob_b64)
    if not res:
        return None
    values = [parse_value(v) for v in res['values']]
    cells = {}  # (row, col) -> {text, link}
    cur_row = 0
    for entry in res['grid']:
        g = parse_grid_entry(entry)
        if g['row'] is not None:
            cur_row = g['row']
        col = g['col'] if g['col'] is not None else 0
        info = {'link': g['link']}
        if g['value_idx'] is not None and g['value_idx'] < len(values):
            vv = values[g['value_idx']]
            info['text'] = vv['text']
            if vv['link']:
                info['link'] = vv['link']
        cells[(cur_row, col)] = info
    # sheet meta: {1: sheetId, 4: ?, 5: ?}
    meta = None
    if res['meta']:
        v = get_field(res['meta'], 1)
        if isinstance(v, bytes):
            try:
                meta = v.decode('utf-8')
            except Exception:
                pass
    return {'sheetId': meta, 'cells': cells, 'max_row': max((r for r, c in cells), default=-1),
            'max_col': max((c for r, c in cells), default=-1)}

if __name__ == '__main__':
    blob = open(sys.argv[1]).read().strip()
    out = extract_sheet(blob)
    if not out:
        print('FAILED')
        sys.exit(1)
    print('sheetId:', out['sheetId'], 'max_row:', out['max_row'], 'max_col:', out['max_col'])
    for (r, c) in sorted(out['cells']):
        info = out['cells'][(r, c)]
        if info.get('text') is not None or info.get('link'):
            print(f'r{r} c{c}: {info.get("text")!r} link={info.get("link")}')
