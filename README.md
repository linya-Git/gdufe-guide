# 2026广东财经大学新生攻略 — 本地存档 + RAG 知识库

- **来源文档**：https://docs.qq.com/sheet/DUkd6Y2xOS3VnYmty （腾讯文档在线表格）
- **抓取时间**：2026-08-22（GMT+8），文档为公开"链接可读"权限的快照
- **内容**：27 个工作表全部文本 + 24 张图片 + 图片 OCR 识别 + 向量检索（RAG）

## 一、目录结构

```
广东新生攻略/
├── README.md                 # 本说明
├── 汇总.txt                  # 全部 tab 纯文本合并（全文检索用）
├── kb/                       # ★ 知识库：16 个按主题整理的 md（供 Agent 直接读取）
│   └── images/               #   知识库引用的图片
├── rag/                      # ★ RAG 向量检索
│   ├── index/                #   chromadb 向量索引（149 chunks, bge-small-zh）
│   ├── build_index.py        #   构建索引（改完 kb 后重跑）
│   └── search.py             #   检索 CLI
├── ask.py                    # ★ 问答工具（检索+提示词；可接本地 LLM）
├── agent/AGENTS.md           # ★ Agent 人格/使用说明（给 OpenClaw Agent 用）
├── ocr/                      # 图片 OCR 识别文本（24 张图 → txt + json）
├── images/                   # 24 张原始图片 + manifest.json（URL 清单）
├── out/                      # 每个 tab 的 md/csv/txt
├── raw/                      # 抓取时的 API 原始响应（27 个 tab）
└── *.py                      # 抓取/解码/构建脚本
```

## 二、知识库主题（kb/）

| 文件 | 内容 |
|---|---|
| 00-导航总览 | 首页导航（各板块跳转） |
| 01-学校概况与历史 | 概况、历史沿革、教学资源、校园地标 |
| 02-校训校徽校歌 | 校训/校徽/校歌（含校歌歌词 OCR） |
| 03-报到入学准备 | 新生清单、行李打包、贫困资助申请 |
| 04-上课时间与学分 | 两校区上课时间表（OCR）、学分制度 |
| 05-转专业 | 转专业政策全文 |
| 06-辅修 | 辅修管理办法全文（OCR） |
| 07-教学楼与图书馆 | 教学楼、校园地图、图书馆指南 |
| 08-宿舍生活 | 七大宿舍园区详解 |
| 09-食堂餐饮 | 一至四饭介绍 |
| 10-交通出行 | 校内出行、校外往返路线 |
| 11-快递与就医 | 快递点/地址、医务室时间与电话（OCR） |
| 12-常用公众号与网址 | 公众号简介（OCR）、网址导航 |
| 13-学生社团 | 校级社团大全（53 个含简介） |
| 14-学校章程 | 章程全文（约 2.1 万字） |
| 15-广财校历与加分途径 | ⚠️ 原表为浮层图片，未抓到，占位说明 |

## 三、RAG 使用方法

```bash
# 检索
python3 rag/search.py "宿舍条件怎么样" --topk 5

# 问答（输出 RAG 上下文 + 提示词）
python3 ask.py "转专业有什么条件"

# 接本地 LLM（如 ollama）
python3 ask.py "开学要带什么" --llm-cmd "ollama run qwen2.5:7b"
```

依赖（已装）：`chromadb`、`fastembed`、`rapidocr_onnxruntime`
- Embedding 模型：`BAAI/bge-small-zh-v1.5`（512 维，首次运行自动下载，走 hf-mirror）
- 索引重建：修改 `kb/` 后运行 `python3 rag/build_index.py`

## 四、给 Agent 用

把 `agent/AGENTS.md` 作为 Agent 的 instructions/AGENTS.md，知识库路径指向本目录即可。
Agent 回答流程：`rag/search.py` 检索 → 读 `kb/` 对应文件 → 按需引用 `kb/images/` 图片。

## 五、已知限制

- **广财校历、加分途径**：原始内容是"drawing 浮层"图片，游客接口无法下载（图片需登录态资源接口）
- 图书馆_1/2/3、校训校徽_1、行李打包_2 等图片为纯图形（地图/logo），OCR 无文字
- 合并单元格渲染为 `〃`；行列布局为近似还原
- 数据为 2026-08-22 快照，官方如有更新以最新为准

## 六、数据更新流程

```bash
python3 fetch_all.py      # 重新抓取 27 个 tab
python3 extract_all.py    # 提取文本
python3 gen_final.py      # 生成 out/ 文档
python3 ocr_images.py     # 重新 OCR（如图片有更新）
python3 build_kb.py       # 重建知识库
python3 rag/build_index.py  # 重建向量索引
```
