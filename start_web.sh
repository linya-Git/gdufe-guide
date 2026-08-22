#!/bin/bash
# 启动广财新生攻略 Web 前端
cd "$(dirname "$0")"
nohup python3 server.py 8899 > /tmp/gdufe_web.log 2>&1 &
echo "已启动: http://127.0.0.1:8899  (日志: /tmp/gdufe_web.log)"
