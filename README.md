# MiniMax Coding Plan Monitor

MiniMax Coding Plan 用量监控工具，后台采集 5 小时滚动窗口用量数据，提供 Web 仪表盘和 API 查看实时用量与历史统计。

## 功能

- **后台采集器** - 每 5 分钟自动调用 MiniMax API，采集用量数据并存入 SQLite
- **Web 仪表盘** - HTML 页面可视化当前用量和历史趋势
- **REST API** - 支持按日/周/月/自定义时间段查询统计
- **Systemd 服务** - 支持后台长期运行

## 快速开始

### 1. 配置 API Key

```bash
mkdir -p ~/.minimax-quota
echo '{"api_key": "sk-cp-你的TokenPlanKey"}' > ~/.minimax-quota.json
chmod 600 ~/.minimax-quota.json
```

> **注意**：必须使用 `sk-cp-` 开头的 Token Plan Key，普通 API Key 无法调用额度接口。

### 2. 启动采集器

```bash
python3 collector.py
# 或指定采集间隔（秒）
python3 collector.py --interval 300
```

### 3. 启动 Web 服务

```bash
python3 server.py
# 或指定端口
python3 server.py --port 8080
```

访问 `http://localhost:8080` 查看仪表盘。

### 4. Systemd 服务方式（可选）

```bash
# 安装采集器服务
sudo cp minimax-collector.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable minimax-collector
sudo systemctl start minimax-collector

# 安装仪表盘服务
sudo cp minimax-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable minimax-dashboard
sudo systemctl start minimax-dashboard
```

## API 接口

| 接口 | 说明 |
|------|------|
| `GET /api/data?hours=24` | 获取最近 N 小时记录 |
| `GET /api/summary` | 获取当前用量摘要 |
| `GET /api/daily?days=7` | 获取每日统计 |
| `GET /api/weekly?weeks=4` | 获取每周统计 |
| `GET /api/monthly?months=6` | 获取每月统计 |
| `GET /api/range?start=2026-03-01&end=2026-03-24` | 指定时间段统计 |
| `GET /api/icon` | 动态 SVG 用量图标 |

## 目录结构

```
.
├── collector.py          # 后台采集器
├── server.py             # Web 服务器
├── db.py                 # 数据库操作
├── minimax-quota.sh      # 命令行快速查询脚本
├── templates/
│   └── index.html        # 仪表盘页面
├── data/                  # SQLite 数据库目录
├── minimax-collector.service  # systemd 服务配置
└── minimax-dashboard.service   # systemd 服务配置
```

## 依赖

- Python 3.8+
- 无其他第三方依赖（使用标准库）
