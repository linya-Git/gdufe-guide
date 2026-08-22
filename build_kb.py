#!/usr/bin/env python3
"""Build curated knowledge base for the GDUFE freshman-guide agent."""
import json, os, re, shutil

os.makedirs('kb', exist_ok=True)
os.makedirs('kb/images', exist_ok=True)

# topic file -> (tab names to include, ocr files to append, images to reference)
TOPICS = [
    ("00-导航总览.md", ["首页"], [], [], "新生攻略导航总览（首页）"),
    ("01-学校概况与历史.md", ["学校概况", "学校历史", "教学资源", "校园环境"], ["学校历史_3"], ["学校历史_1", "学校历史_2", "学校历史_3"], "学校概况、历史沿革、校区介绍、校园地标"),
    ("02-校训校徽校歌.md", ["校训校徽"], ["校训校徽_3", "校训校徽_2"], ["校训校徽_1", "校训校徽_2", "校训校徽_3"], "校训、校徽、校歌（含校歌歌词OCR）"),
    ("03-报到入学准备.md", ["新生清单", "行李打包", "贫困资助申请"], ["行李打包_1"], ["行李打包_1", "行李打包_2"], "新生报到清单、行李打包、贫困资助申请"),
    ("04-上课时间与学分.md", ["上课时间", "学分"], ["上课时间_1"], ["上课时间_1"], "上课时间表（三水/广州校区）、学分制度"),
    ("05-转专业.md", ["转专业"], [], [], "转专业政策全文"),
    ("06-辅修.md", ["辅修"], ["辅修_1", "辅修_2", "辅修_3", "辅修_4"], ["辅修_1", "辅修_2", "辅修_3", "辅修_4"], "辅修管理办法全文"),
    ("07-教学楼与图书馆.md", ["教学楼", "图书馆"], ["教学楼_1"], ["教学楼_1", "图书馆_1", "图书馆_2", "图书馆_3"], "教学楼介绍、校园地图、图书馆指南"),
    ("08-宿舍生活.md", ["宿舍"], [], [], "宿舍园区详解（杏园/桂园/李园/桃园/紫园/竹园/有为书院）"),
    ("09-食堂餐饮.md", ["食堂"], [], [], "一饭/二饭/三饭/四饭介绍"),
    ("10-交通出行.md", ["校内交通", "校外交通"], [], [], "校内出行（小绿/小白车）、校外往返路线"),
    ("11-快递与就医.md", ["快递", "就医详解"], ["就医详解_1"], ["就医详解_1"], "快递点与收货地址、医务室就诊指南"),
    ("12-常用公众号与网址.md", ["常用公众号", "常用网址"], ["常用公众号_1", "常用公众号_2", "常用公众号_3", "常用公众号_4", "常用公众号_5", "常用公众号_6"], ["常用公众号_1", "常用公众号_2", "常用公众号_3", "常用公众号_4", "常用公众号_5", "常用公众号_6"], "官方/常用公众号、常用网址导航"),
    ("13-学生社团.md", ["学生社团"], [], [], "校级社团大全（含简介）"),
    ("14-学校章程.md", ["学校章程"], [], [], "广东财经大学章程全文"),
    ("15-广财校历与加分途径.md", ["广财校历", "加分途径"], [], [], "校历与加分途径（原表为图片型内容，未能抓取，此处为占位说明）"),
]

def load_txt(name):
    fn = f'out/{name}.txt'
    if not os.path.exists(fn):
        return ''
    t = open(fn).read().strip()
    # remove the '===== name =====' header line if present
    lines = t.split('\n')
    if lines and lines[0].startswith('====='):
        lines = lines[1:]
    return '\n'.join(lines).strip()

def load_ocr(name):
    fn = f'ocr/{name}.txt'
    if not os.path.exists(fn):
        return ''
    return open(fn).read().strip()

def copy_images(imgs):
    for img in imgs:
        src = f'images/{img}'
        dst = f'kb/images/{img}'
        if os.path.exists(src) and not os.path.exists(dst):
            shutil.copy(src, dst)

for fname, tabs, ocrs, imgs, desc in TOPICS:
    copy_images(imgs)
    parts = []
    parts.append(f'# {desc}')
    parts.append('')
    for tab in tabs:
        t = load_txt(tab)
        if not t:
            continue
        parts.append(f'## {tab}')
        parts.append('')
        parts.append(t)
        parts.append('')
    if ocrs:
        parts.append('## 图片内容（OCR 识别）')
        parts.append('')
        for ocr_name in ocrs:
            ot = load_ocr(ocr_name)
            if ot:
                parts.append(f'### {ocr_name}')
                parts.append('')
                parts.append(ot)
                parts.append('')
    if imgs:
        parts.append('## 相关图片')
        parts.append('')
        for img in imgs:
            parts.append(f'![{img}](images/{img})')
        parts.append('')
    content = '\n'.join(parts)
    with open(f'kb/{fname}', 'w') as f:
        f.write(content)
    print(f'{fname}: {len(content)} chars')

print('KB built.')
