#!/usr/bin/env python3
"""Decode Tencent Docs sheet blob (related_sheet) -> cells with (row, col, value)."""
import base64, json, sys, zlib

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
    """Return list of (fnum, ('varint', v) | bytes)."""
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

def get_string(b):
    """Extract string from value wrapper: {1: str} or {1: {1: str}}."""
    try:
        fields = parse_fields(b)
        for fn, v in fields:
            if fn == 1:
                if isinstance(v, bytes):
                    try:
                        return v.decode('utf-8')
                    except Exception:
                        inner = parse_fields(v)
                        for fn2, v2 in inner:
                            if fn2 == 1 and isinstance(v2, bytes):
                                try:
                                    return v2.decode('utf-8')
                                except Exception:
                                    return None
                        return None
    except Exception:
        return None
    return None

def decode_blob(blob_b64):
    raw = base64.b64decode(blob_b64)
    try:
        data = zlib.decompress(raw)
    except Exception:
        data = raw
    # outer wrapper: field 1
    fields = parse_fields(data)
    body = None
    for fn, v in fields:
        if fn == 1 and isinstance(v, bytes):
            body = v
            break
    if body is None:
        return None
    # body fields
    bf = parse_fields(body)
    f5s = [v for fn, v in bf if fn == 5 and isinstance(v, bytes)]
    big = f5s[-1]
    bigf = parse_fields(big)
    f19 = None
    for fn, v in bigf:
        if fn == 19 and isinstance(v, bytes):
            f19 = v
            break
    if f19 is None:
        return None
    f19f = parse_fields(f19)
    result = {'meta': None, 'styled': [], 'values': [], 'grid': []}
    for fn, v in f19f:
        if fn == 3 and isinstance(v, bytes) and len(v) < 50:
            result['meta'] = v
        elif fn == 4 and isinstance(v, bytes):
            for _, cell in parse_fields(v):
                if isinstance(cell, bytes):
                    result['styled'].append(cell)
        elif fn == 5 and isinstance(v, bytes):
            for _, cell in parse_fields(v):
                if isinstance(cell, bytes):
                    result['values'].append(cell)
        elif fn == 6 and isinstance(v, bytes):
            result['grid'].append(v)
    return result

def parse_grid_entry(b):
    """Parse a f6 grid entry -> (row, col, hyperlink_target, style)."""
    row = col = None
    link = None
    for fn, v in parse_fields(b):
        if fn == 1 and isinstance(v, tuple):
            row = v[1]
        elif fn == 2 and isinstance(v, tuple):
            col = v[1]
        elif fn == 3 and isinstance(v, bytes):
            for fn2, v2 in parse_fields(v):
                if fn2 == 8 and isinstance(v2, bytes):
                    for fn3, v3 in parse_fields(v2):
                        if fn3 == 11 and isinstance(v3, bytes):
                            for fn4, v4 in parse_fields(v3):
                                if fn4 == 1 and isinstance(v4, bytes):
                                    try:
                                        link = v4.decode('utf-8')
                                    except Exception:
                                        pass
    return row, col, link

if __name__ == '__main__':
    blob = sys.argv[1]
    b64 = open(blob).read().strip() if not blob.startswith('eAG') else blob
    res = decode_blob(b64)
    if not res:
        print('decode failed')
        sys.exit(1)
    print('meta:', res['meta'])
    print('styled cells:', len(res['styled']), 'value cells:', len(res['values']), 'grid entries:', len(res['grid']))
    print()
    print('=== VALUES (f5) ===')
    for i, c in enumerate(res['values']):
        s = get_string(c)
        print(f'{i}: {s!r}')
    print()
    print('=== GRID with positions (f6) ===')
    for i, c in enumerate(res['grid']):
        row, col, link = parse_grid_entry(c)
        print(f'{i}: row={row} col={col} link={link}')
