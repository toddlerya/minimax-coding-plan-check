#!/usr/bin/env python3
"""SQLite database module for MiniMax quota usage records."""

import sqlite3
import os
from datetime import datetime, timedelta
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "quota.sqlite")


def get_db_path():
    return DB_PATH


@contextmanager
def get_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Initialize the database with required tables."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usage_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                total INTEGER NOT NULL,
                used INTEGER NOT NULL,
                remaining INTEGER NOT NULL,
                percentage REAL NOT NULL,
                remains_time_ms INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON usage_records(timestamp)
        """)


def insert_record(total: int, used: int, remaining: int, percentage: float, remains_time_ms: int) -> int:
    """Insert a new usage record. Returns the record id."""
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO usage_records (total, used, remaining, percentage, remains_time_ms)
            VALUES (?, ?, ?, ?, ?)
        """, (total, used, remaining, percentage, remains_time_ms))
        return cursor.lastrowid


def get_records(hours: int = 24) -> list:
    """Get records from the last N hours."""
    # Use utcnow to match the timezone of stored timestamps
    since = datetime.utcnow() - timedelta(hours=hours)
    # Replace T with space to match SQLite's 'YYYY-MM-DD HH:MM:SS' format
    since_str = since.isoformat().replace("T", " ")
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT timestamp, total, used, remaining, percentage, remains_time_ms
            FROM usage_records
            WHERE timestamp >= ?
            ORDER BY timestamp ASC
        """, (since_str,)).fetchall()
        return [dict(row) for row in rows]


def get_all_records(days: int = 7) -> list:
    """Get all records from the last N days (for longer time ranges)."""
    # Use utcnow to match the timezone of stored timestamps
    since = datetime.utcnow() - timedelta(days=days)
    # Replace T with space to match SQLite's 'YYYY-MM-DD HH:MM:SS' format
    since_str = since.isoformat().replace("T", " ")
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT timestamp, total, used, remaining, percentage, remains_time_ms
            FROM usage_records
            WHERE timestamp >= ?
            ORDER BY timestamp ASC
        """, (since_str,)).fetchall()
        return [dict(row) for row in rows]


def get_summary() -> dict:
    """Get summary statistics of all records."""
    with get_connection() as conn:
        row = conn.execute("""
            SELECT
                COUNT(*) as record_count,
                AVG(percentage) as avg_percentage,
                MAX(percentage) as max_percentage,
                MIN(percentage) as min_percentage,
                MAX(timestamp) as latest_record_time
            FROM usage_records
        """).fetchone()

        latest = conn.execute("""
            SELECT total, used, remaining, percentage, remains_time_ms
            FROM usage_records
            ORDER BY timestamp DESC
            LIMIT 1
        """).fetchone()

        return {
            "record_count": row["record_count"] or 0,
            "avg_percentage": row["avg_percentage"] or 0,
            "max_percentage": row["max_percentage"] or 0,
            "min_percentage": row["min_percentage"] or 0,
            "latest_record_time": row["latest_record_time"],
            "current": dict(latest) if latest else None
        }


def get_daily_stats(days: int = 7) -> list:
    """Get daily usage statistics for the last N days."""
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                date(timestamp) as date,
                AVG(percentage) as avg_percentage,
                MAX(percentage) as max_percentage,
                MIN(percentage) as min_percentage,
                SUM(used) as total_used,
                AVG(remaining) as avg_remaining,
                COUNT(*) as record_count
            FROM usage_records
            WHERE timestamp >= ?
            GROUP BY date(timestamp)
            ORDER BY date ASC
        """, (since,)).fetchall()
        return [dict(row) for row in rows]


def get_weekly_stats(weeks: int = 4) -> list:
    """Get weekly usage statistics for the last N weeks."""
    since = (datetime.utcnow() - timedelta(weeks=weeks * 7)).strftime("%Y-%m-%d")
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                strftime('%Y-W%W', timestamp) as week,
                AVG(percentage) as avg_percentage,
                MAX(percentage) as max_percentage,
                MIN(percentage) as min_percentage,
                SUM(used) as total_used,
                AVG(remaining) as avg_remaining,
                COUNT(*) as record_count
            FROM usage_records
            WHERE timestamp >= ?
            GROUP BY strftime('%Y-W%W', timestamp)
            ORDER BY week ASC
        """, (since,)).fetchall()
        return [dict(row) for row in rows]


def get_monthly_stats(months: int = 6) -> list:
    """Get monthly usage statistics for the last N months."""
    since = (datetime.utcnow() - timedelta(days=months * 30)).strftime("%Y-%m-%d")
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                strftime('%Y-%m', timestamp) as month,
                AVG(percentage) as avg_percentage,
                MAX(percentage) as max_percentage,
                MIN(percentage) as min_percentage,
                SUM(used) as total_used,
                AVG(remaining) as avg_remaining,
                COUNT(*) as record_count
            FROM usage_records
            WHERE timestamp >= ?
            GROUP BY strftime('%Y-%m', timestamp)
            ORDER BY month ASC
        """, (since,)).fetchall()
        return [dict(row) for row in rows]


def get_range_stats(start_date: str, end_date: str) -> dict:
    """Get usage statistics for a specified date range (YYYY-MM-DD format)."""
    with get_connection() as conn:
        # Get overall stats for the range
        row = conn.execute("""
            SELECT
                COUNT(*) as record_count,
                AVG(percentage) as avg_percentage,
                MAX(percentage) as max_percentage,
                MIN(percentage) as min_percentage,
                SUM(used) as total_used,
                AVG(remaining) as avg_remaining,
                MIN(timestamp) as start_time,
                MAX(timestamp) as end_time
            FROM usage_records
            WHERE date(timestamp) >= date(?) AND date(timestamp) <= date(?)
        """, (start_date, end_date)).fetchone()

        # Get daily breakdown
        daily = conn.execute("""
            SELECT
                date(timestamp) as date,
                AVG(percentage) as avg_percentage,
                MAX(percentage) as max_percentage,
                MIN(percentage) as min_percentage,
                SUM(used) as total_used,
                AVG(remaining) as avg_remaining,
                COUNT(*) as record_count
            FROM usage_records
            WHERE date(timestamp) >= date(?) AND date(timestamp) <= date(?)
            GROUP BY date(timestamp)
            ORDER BY date ASC
        """, (start_date, end_date)).fetchall()

        return {
            "range": {
                "start_date": start_date,
                "end_date": end_date,
                "record_count": row["record_count"] or 0,
                "avg_percentage": round(row["avg_percentage"], 1) if row["avg_percentage"] else 0,
                "max_percentage": round(row["max_percentage"], 1) if row["max_percentage"] else 0,
                "min_percentage": round(row["min_percentage"], 1) if row["min_percentage"] else 0,
                "total_used": row["total_used"] or 0,
                "avg_remaining": round(row["avg_remaining"], 0) if row["avg_remaining"] else 0,
                "start_time": row["start_time"],
                "end_time": row["end_time"]
            },
            "daily": [dict(r) for r in daily]
        }


if __name__ == "__main__":
    init_db()
    print("Database initialized at:", DB_PATH)
