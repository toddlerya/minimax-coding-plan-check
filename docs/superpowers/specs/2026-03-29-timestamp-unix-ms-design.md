# MiniMax Coding Plan - 时间戳重构设计方案

## 背景

当前系统存在时区混乱问题：

- MiniMax API 返回 UTC 毫秒时间戳 (`start_time`)
- SQLite `CURRENT_TIMESTAMP` 取决于服务器时区（UTC 服务器上返回 UTC 时间）
- `db.py` 查询混用 `datetime.now()` / `datetime.utcnow()`
- 展示层时区转换逻辑多次变更，仍有 bug

## 目标

1. **消除时区歧义**：所有时间以 Unix 毫秒时间戳（UTC）存储
2. **与 API 对齐**：直接使用 API 返回的 `start_time` 作为记录时间
3. **简化展示逻辑**：展示层统一 +8 小时转北京时

## 数据流（重构后）

```
MiniMax API (UTC ms start_time)
  → collector.py 提取 start_time (ms)
    → db.insert_record() 存为 INTEGER
      → db.get_records() 用 ms 整数比较查询
        → server.py ms → 北京时字符串展示
```

## Schema 变更

### `db.py` - usage_records 表

```sql
CREATE TABLE usage_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,          -- 毫秒时间戳，UTC（来自 API start_time）
    total INTEGER NOT NULL,
    used INTEGER NOT NULL,
    remaining INTEGER NOT NULL,
    percentage REAL NOT NULL,
    remains_time_ms INTEGER NOT NULL,
    created_at INTEGER DEFAULT (strftime('%s', 'now') * 1000)
)
CREATE INDEX idx_timestamp ON usage_records(timestamp)
```

**变更点**：
- `timestamp` 从 `DATETIME DEFAULT CURRENT_TIMESTAMP` 改为 `INTEGER NOT NULL`
- `created_at` 从 `DATETIME` 改为 `INTEGER`（存 ms）

### 向后兼容：首次启动时清空旧数据

```python
SCHEMA_VERSION = 2

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_connection() as conn:
        # 检查旧数据格式，首次升级时清除
        try:
            row = conn.execute(
                "SELECT typeof(timestamp) as t FROM usage_records LIMIT 1"
            ).fetchone()
            if row and row['t'] == 'text':  # 旧字符串格式
                conn.execute("DROP TABLE usage_records")
                conn.execute("DROP INDEX IF EXISTS idx_timestamp")
        except sqlite3.OperationalError:
            pass  # 表不存在，直接创建

        # 创建新表
        conn.execute("""...""")
        conn.execute("CREATE INDEX idx_timestamp ON usage_records(timestamp)")
```

## 模块变更

### `collector.py`

`parse_and_store()` 变更：

```python
def parse_and_store(data: dict) -> bool:
    record = model_remains[0]
    start_time_ms = int(record.get("start_time", 0))  # API 窗口开始时间
    total = int(record.get("current_interval_total_count", 0))
    remaining = int(record.get("current_interval_usage_count", 0))
    used = total - remaining
    percentage = (used / total * 100) if total > 0 else 0
    remains_time_ms = int(record.get("remains_time", 0))

    db.insert_record(start_time_ms, total, used, remaining, percentage, remains_time_ms)
```

**签名变更**：`insert_record()` 第一个参数从 `total` 改为 `timestamp_ms`

### `db.py`

#### `insert_record()` 签名变更

```python
def insert_record(timestamp_ms: int, total: int, used: int,
                  remaining: int, percentage: float, remains_time_ms: int) -> int:
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO usage_records (timestamp, total, used, remaining, percentage, remains_time_ms)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (timestamp_ms, total, used, remaining, percentage, remains_time_ms))
        return cursor.lastrowid
```

#### `get_records()` 查询变更

```python
def get_records(hours: int = 24) -> list:
    now_ms = int(datetime.utcnow().timestamp() * 1000)
    since_ms = now_ms - hours * 3600 * 1000
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT timestamp, total, used, remaining, percentage, remains_time_ms
            FROM usage_records
            WHERE timestamp >= ?
            ORDER BY timestamp ASC
        """, (since_ms,)).fetchall()
        return [dict(row) for row in rows]
```

#### `get_all_records()` 查询变更

```python
def get_all_records(days: int = 7) -> list:
    now_ms = int(datetime.utcnow().timestamp() * 1000)
    since_ms = now_ms - days * 86400 * 1000
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT timestamp, total, used, remaining, percentage, remains_time_ms
            FROM usage_records
            WHERE timestamp >= ?
            ORDER BY timestamp ASC
        """, (since_ms,)).fetchall()
        return [dict(row) for row in rows]
```

#### 统计查询变更

`get_daily_stats`、`get_weekly_stats`、`get_monthly_stats` 的 `WHERE timestamp >= ?` 条件改为 ms 整数。

SQLite 日期分组需用 `date(timestamp/1000, 'unixepoch')` 转换：

```sql
SELECT date(timestamp/1000, 'unixepoch') as date, ...
```

#### `get_summary()`

```python
latest = conn.execute("""
    SELECT timestamp, total, used, remaining, percentage, remains_time_ms
    FROM usage_records
    ORDER BY timestamp DESC
    LIMIT 1
""").fetchone()
# latest_record_time 保持原样返回（ms 整数）
```

### `server.py`

#### `serve_data()` 时间戳展示

```python
from datetime import datetime, timedelta, timezone
for r in records:
    ts_ms = int(r["timestamp"])
    dt_utc = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
    dt_beijing = dt_utc + timedelta(hours=8)
    r["timestamp"] = dt_beijing.strftime("%Y-%m-%d %H:%M:%S+08:00")
```

#### `serve_summary()` 时间戳展示

同上，`timestamp` 从整数转为北京时字符串。

#### 其他 API

`serve_daily_stats`、`serve_weekly_stats`、`serve_monthly_stats` 中的 `date` / `week` / `month` 字段来自 SQLite `date()` 函数，不涉及 timestamp 列，仅需确认 schema 兼容即可。

## 验证步骤

重构完成后验证：

1. `curl http://localhost:8080/api/data?hours=6` 返回数据时间范围正确（当前时刻 -6h 内）
2. `curl http://localhost:8080/api/summary` 的 `latest_record_time` 为北京时格式
3. 数据库中 `SELECT typeof(timestamp) FROM usage_records LIMIT 1` 返回 `integer`

## 影响范围

- `db.py`: schema + 所有查询函数
- `collector.py`: `parse_and_store()` 参数顺序
- `server.py`: 时间戳展示逻辑
- **数据**：首次启动自动清空旧数据

## 风险评估

- **低风险**：逻辑简单，字符串→整数，无数据迁移
- **注意**：需确保所有时间计算用 UTC
