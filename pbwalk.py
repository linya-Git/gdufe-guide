#!/usr/bin/env python3
"""Generic protobuf wire-format dumper."""
import sys, json

def read_varint(b, i):
    r = 0
    s = 0
    while i < len(b):
        x = b[i]
        i += 1
        r |= (x & 0x7f) << s
        if not (x & 0x80):
            return r, i
        s += 7
    raise IndexError

def parse(b, i=0, depth=0, maxdepth=14, out=None):
    if out is None:
        out = []
    n = len(b)
    while i < n:
        try:
            tag, i = read_varint(b, i)
        except IndexError:
            break
        if tag == 0:
            i += 1
            continue
        fnum = tag >> 3
        wt = tag & 7
        try:
            if fnum == 0:
                break
            if wt == 0:
                v, i = read_varint(b, i)
                out.append((fnum, 'varint', v, depth))
            elif wt == 1:
                if i + 8 > n: break
                v = b[i:i+8]; i += 8
                out.append((fnum, '64bit', v.hex(), depth))
            elif wt == 2:
                l, i = read_varint(b, i)
                if i + l > n: break
                chunk = b[i:i+l]; i += l
                # try to see if it's a sub-message (starts with valid tag) or string
                looks_msg = False
                if l > 0:
                    try:
                        t2, _ = read_varint(chunk, 0)
                        if (t2 >> 3) > 0 and t2 & 7 <= 5:
                            looks_msg = True
                    except Exception:
                        looks_msg = False
                txt = None
                try:
                    txt = chunk.decode('utf-8')
                except Exception:
                    pass
                if txt is not None and not looks_msg:
                    out.append((fnum, 'str', txt, depth))
                elif looks_msg and depth < maxdepth:
                    out.append((fnum, 'msg', f'({l} bytes)', depth))
                    parse(chunk, 0, depth + 1, maxdepth, out)
                else:
                    out.append((fnum, 'bytes', chunk.hex()[:80], depth))
            elif wt == 5:
                if i + 4 > n: break
                v = b[i:i+4]; i += 4
                out.append((fnum, '32bit', v.hex(), depth))
            else:
                break
        except IndexError:
            break
    return out

def main():
    fn = sys.argv[1]
    b = open(fn, 'rb').read()
    rows = parse(b)
    for fnum, wt, v, depth in rows:
        pad = '  ' * depth
        if wt == 'str':
            vs = v if len(v) < 200 else v[:200] + '...'
            print(f'{pad}[{fnum}] str: {vs!r}')
        elif wt == 'msg':
            print(f'{pad}[{fnum}] msg {v}')
        elif wt == 'varint':
            print(f'{pad}[{fnum}] varint: {v}')
        else:
            print(f'{pad}[{fnum}] {wt}: {v}')

if __name__ == '__main__':
    main()
