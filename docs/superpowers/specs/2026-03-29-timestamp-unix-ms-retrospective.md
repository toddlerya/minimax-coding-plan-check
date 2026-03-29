# 时间戳重构复盘

## 修复的问题

### 1. 时区混乱 (Schema v1 → v2)
**根因**: `timestamp` 存为 SQLite `DATETIME`（取决于服务器时区），查询混用 `datetime.now()` / `datetime.utcnow()`，展示层多次时区转换仍有 bug。

**修复**:
- `timestamp` 改为 `INTEGER` 存 Unix 毫秒
- 统一用 `datetime.now(timezone.utc)` 获取当前时间（aware datetime，避免 naive 时间被 `.timestamp()` 当本地时间处理的陷阱）
- collector 存实际采集时间（ms），不再用 API 的 `start_time`（5小时窗口开始时间）
- 向后兼容：Schema v2 首次启动自动清除旧字符串格式数据

### 2. collector 采集超时 (systemd 代理)
**根因**: `minimax-quota.sh` 用 `curl` 自动读 shell 代理环境变量；`collector.py` 用 Python `urllib` 不会自动用代理。systemd service 没有配置代理环境变量。

**修复**:
- systemd service 加 `Environment=ALL_PROXY=socks5://127.0.0.1:7897` 和 `HTTPS_PROXY`
- 加 `PYTHONUNBUFFERED=1` 确保日志实时输出

### 3. naive datetime 的 .timestamp() 陷阱
**根因**: `datetime.utcnow()` 返回 naive datetime（无 tzinfo），`.timestamp()` 会把它当作**本地时区**转换，而非 UTC。机器本地时区 CST(UTC+8)，导致存储时间比实际早 8 小时。

**错误代码**:
```python
now_ms = int(datetime.utcnow().timestamp() * 1000)  # BUG: 差了 8 小时
```

**正确代码**:
```python
now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)  # aware datetime
```

### 4. 时间轴全显示 API 窗口起始时间
**根因**: collector 把 API 返回的 `start_time`（5小时窗口开始时间）当作记录时间存入 DB。同一窗口内的所有记录 `start_time` 相同，导致图表时间轴全是同一时间。

**修复**: 存实际采集时间，不复用 API 的 `start_time`。

## 变更文件

| 文件 | 变更 |
|------|------|
| `db.py` | schema INTEGER(ms)、所有查询改用 ms 整数比较、`date()` 分组改用 `date(timestamp/1000,'unixepoch')` |
| `collector.py` | 存实际采集时间（`datetime.now(timezone.utc)`）、加 `PYTHONUNBUFFERED`、加代理环境变量 |
| `server.py` | 时间戳展示统一用 `datetime.fromtimestamp(ms/1000, tz=timezone.utc)` + timedelta(hours=8) |
| `CLAUDE.md` | 更新数据库说明、加 Systemd 服务说明 |
| `minimax-collector.service` | 加 `PYTHONUNBUFFERED=1` 和代理环境变量 |

## 验证

- [x] `SELECT typeof(timestamp) FROM usage_records` 返回 `integer`
- [x] 新记录 `timestamp` 转换为北京时正确（接近当前时间）
- [x] collector 每 5 分钟自动采集，不超时
- [x] system

## 经验教训

1. **naive vs aware datetime**: Python 的 `datetime.utcnow()` 是 naive 的，配合 `.timestamp()` 会踩坑。永远优先用 `datetime.now(timezone.utc)` 获得 aware datetime。
2. **systemd 环境隔离**: systemd service 的环境变量与 shell 独立，需要显式配置代理。
3. **Schema 设计**: 时间字段存整数（Unix ms）比存字符串/datetime 更安全，消除时区歧义。
