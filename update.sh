#!/bin/bash
# 广财新生攻略 - 一键更新脚本
# 用法: ./update.sh
# 流程: 重新抓取腾讯文档 -> 提取 -> 生成文档 -> OCR -> 知识库 -> 向量索引 -> 重启服务
set -e
cd "$(dirname "$0")"
echo "==> [1/6] 重新抓取腾讯文档数据..."
python3 fetch_all.py || echo "  (抓取失败，继续使用现有 raw/ 数据)"
echo "==> [2/6] 提取文本..."
python3 extract_all.py
echo "==> [3/6] 生成文档..."
python3 gen_final.py
echo "==> [4/6] 图片 OCR..."
python3 ocr_images.py || echo "  (OCR 跳过)"
echo "==> [5/6] 重建知识库..."
python3 build_kb.py
echo "==> [6/6] 重建向量索引 + 重启服务..."
HF_ENDPOINT=https://hf-mirror.com HF_HUB_DISABLE_XET=1 python3 rag/build_index.py
pkill -f "server.py 8899" 2>/dev/null || true
sleep 1
nohup python3 server.py 8899 > /tmp/gdufe_web.log 2>&1 &
sleep 3
echo "完成！http://127.0.0.1:8899"
echo
echo "未处理反馈 (feedback/feedback.jsonl):"
[ -f feedback/feedback.jsonl ] && wc -l feedback/feedback.jsonl || echo "  (无)"
