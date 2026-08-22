#!/usr/bin/env python3
"""清理 kb/*.md 中的 OCR 噪声/导航残留/图片引用残留。"""
import glob, re

def clean_file(f):
    lines = open(f, encoding='utf-8').read().split('\n')
    out = []
    for ln in lines:
        s = ln.strip()
        # 1. 导航残留
        if '点击返回首页' in s or '返回PC端首页' in s:
            continue
        # 2. 图片引用句（图片不展示）
        if re.search(r'如(左|右|上|下)图(所示|中|里)', s):
            continue
        if re.search(r'如图[一二三四]?所?示?', s) and len(s) < 30:
            continue
        # 3. 单字符行（孤立 OCR 字，如 '国' '楼' '口'）
        if len(s) == 1:
            continue
        # 4. 纯 ASCII 短噪声（Sg NN OF 等，保留 1983 年份和 01-07 编号）
        if re.fullmatch(r'[A-Za-z]{1,3}', s):
            continue
        if re.fullmatch(r'[0-9]{1,2}', s):
            # 保留园区编号（01-07 在宿舍上下文）——但删除校歌简谱单数字（如 1 5）
            # 简化：1 位数删，2 位数保留
            if len(s) == 1:
                continue
        # 5. 行内夹杂的 OCR 碎片（如 'x一饭又称...' 开头的孤立字母）
        m = re.match(r'^([A-Za-z\$#%&])([^\x00-\x7f])', s)
        if m and len(s) > 2:
            s = s[1:]
        out.append(s if s != ln else ln)
    # 清理连续空行
    text = '\n'.join(out)
    text = re.sub(r'\n{3,}', '\n\n', text)
    # 6. 删除空的"相关图片"节（图片不展示）
    text = re.sub(r'\n## 相关图片\n\n(?=\n|$)', '\n', text)
    text = re.sub(r'\n## 相关图片\n', '\n', text)
    open(f, 'w', encoding='utf-8').write(text)
    return len(lines) - len(out)

total = 0
for f in sorted(glob.glob('kb/*.md')):
    n = clean_file(f)
    if n:
        print(f'{f}: 清理 {n} 行')
        total += n
print('total cleaned:', total)
