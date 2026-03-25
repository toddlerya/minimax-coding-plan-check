#!/bin/bash
# 启动 MiniMax Coding Plan 统计系统

cd "$(dirname "$0")"

echo "Starting MiniMax Collector in background..."
python3 collector.py &

sleep 2

echo "Starting Web Server..."
python3 server.py --port 8080
