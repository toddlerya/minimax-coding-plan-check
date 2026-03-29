# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

MiniMax Coding Plan 监控工具，监控 5 小时滚动窗口用量。包含三个组件：

- **采集器** (`collector.py`) - 后台进程，每 5 分钟获取一次用量
- **Web 服务** (`server.py`) - 仪表盘和 REST API，端口 8080
- **CLI 脚本** (`minimax-quota.sh`) - 终端快速查询

## 常用命令

```bash
# 配置 API Key（必须使用 sk-cp- 前缀，不能用普通 sk- Key）
mkdir -p ~/.minimax-quota
echo '{"api_key": "sk-cp-your-token-plan-key"}' > ~/.minimax-quota.json
chmod 600 ~/.minimax-quota.json

# 运行采集器（每 5 分钟抓取一次）
python3 collector.py

# 运行 Web 仪表盘
python3 server.py --port 8080

# 终端快速查询
./minimax-quota.sh
```

## Systemd 服务

两个服务已注册到系统 systemd（`/etc/systemd/system/`），开机自启：

```bash
# 重启服务（代码更新后需手动执行）
sudo systemctl restart minimax-collector minimax-dashboard

# 查看状态
systemctl status minimax-collector minimax-dashboard
```

服务文件：`minimax-collector.service`、`minimax-dashboard.service`

## 架构

- `collector.py` → 从 MiniMax API 获取数据，存入 SQLite
- `server.py` → HTTP 服务器 (`BaseHTTPRequestHandler`)，提供仪表盘和 API
- `db.py` → SQLite 操作（数据库文件 `data/quota.sqlite`），使用上下文管理器
- `minimax-quota.sh` → bash 脚本，需要 `jq`，读取 `~/.minimax-quota.json`
- `templates/index.html` → 独立仪表盘页面（无外部依赖）

**数据流**: MiniMax API → `collector.py` → `db.py` (SQLite) → `server.py` → 浏览器

## API Key 要求

**关键**: 必须使用 `sk-cp-` 前缀的 Token Plan Key，不能用普通的 `sk-` API Key。用错类型会返回 `status_code != 0` 或 `invalid token`。

## 数据库

SQLite 数据库位于 `data/quota.sqlite`。`timestamp` 存为 **Unix 毫秒整数**（UTC），避免时区歧义。表结构：
- `usage_records`: timestamp (INTEGER, ms), total, used, remaining, percentage, remains_time_ms
- 在 `timestamp` 上建有索引，用于时间范围查询
- Schema 版本 2，首次启动时自动清除旧字符串格式数据

## Web API 接口

| 接口 | 说明 |
|------|------|
| `GET /` | 仪表盘 HTML 页面 |
| `GET /api/data?hours=24` | 最近 N 小时记录 |
| `GET /api/summary` | 当前用量 + 统计摘要 |
| `GET /api/daily?days=7` | 每日聚合统计 |
| `GET /api/weekly?weeks=4` | 每周聚合统计 |
| `GET /api/monthly?months=6` | 每月聚合统计 |
| `GET /api/range?start=YYYY-MM-DD&end=YYYY-MM-DD` | 自定义时间段统计 |
| `GET /api/icon` | 动态 SVG 用量图标 |
