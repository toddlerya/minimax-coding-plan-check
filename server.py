#!/usr/bin/env python3
"""
MiniMax Coding Plan Web Server
Provides HTML dashboard and API endpoints for usage data.
"""

import argparse
import json
import os
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import db


def format_remains_time(ms: int) -> str:
    """Format remaining time in human readable format."""
    if ms <= 0:
        return "N/A"
    seconds = ms // 1000
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


class RequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for MiniMax quota dashboard."""

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

    def send_json(self, data: dict, status: int = 200):
        """Send JSON response."""
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, html: str, status: int = 200):
        """Send HTML response."""
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self.serve_html()
        elif path == "/api/data":
            hours = int(query.get("hours", [24])[0])
            self.serve_data(hours)
        elif path == "/api/summary":
            self.serve_summary()
        elif path == "/api/daily":
            days = int(query.get("days", [7])[0])
            self.serve_daily_stats(days)
        elif path == "/api/weekly":
            weeks = int(query.get("weeks", [4])[0])
            self.serve_weekly_stats(weeks)
        elif path == "/api/monthly":
            months = int(query.get("months", [6])[0])
            self.serve_monthly_stats(months)
        elif path == "/api/range":
            start = query.get("start", [None])[0]
            end = query.get("end", [None])[0]
            if start and end:
                self.serve_range_stats(start, end)
            else:
                self.send_json({"error": "start and end parameters required (YYYY-MM-DD)"}, 400)
        elif path == "/api/icon":
            self.serve_icon()
        else:
            self.send_json({"error": "Not found"}, 404)

    def serve_html(self):
        """Serve the main HTML page."""
        html_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
        if os.path.exists(html_path):
            with open(html_path) as f:
                self.send_html(f.read())
        else:
            self.send_html("<html><body><h1>Error: HTML template not found</h1></body></html>", 500)

    def serve_data(self, hours: int = 24):
        """Serve usage records as JSON."""
        try:
            if hours > 24:
                records = db.get_all_records(days=hours // 24)
            else:
                records = db.get_records(hours=hours)

            # Format timestamps as Beijing time (UTC+8)
            for r in records:
                if isinstance(r["timestamp"], str):
                    ts = r["timestamp"]
                else:
                    ts = r["timestamp"].isoformat()
                # Timestamp is stored as naive datetime string in local CST (UTC+8),
                # just append the timezone suffix for ISO format output
                ts_clean = ts.replace("+08:00", "")
                r["timestamp"] = f"{ts_clean}+08:00"

            self.send_json({"records": records})
        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    def serve_summary(self):
        """Serve summary statistics as JSON."""
        try:
            summary = db.get_summary()

            # Format current data
            if summary.get("current"):
                current = summary["current"]
                summary["current"] = {
                    "total": current["total"],
                    "used": current["used"],
                    "remaining": current["remaining"],
                    "percentage": round(current["percentage"], 1),
                    "remains_time": format_remains_time(current["remains_time_ms"]),
                    "remains_time_ms": current["remains_time_ms"]
                }

            # Format stats
            summary["stats"] = {
                "avg_percentage": round(summary["avg_percentage"], 1) if summary["avg_percentage"] else 0,
                "max_percentage": round(summary["max_percentage"], 1) if summary["max_percentage"] else 0,
                "min_percentage": round(summary["min_percentage"], 1) if summary["min_percentage"] else 0,
                "record_count": summary["record_count"]
            }

            if summary.get("latest_record_time"):
                ts = str(summary["latest_record_time"])
                # Timestamp stored as naive CST string, just append timezone suffix
                summary["latest_record_time"] = f"{ts.replace('+08:00', '')}+08:00"

            self.send_json(summary)
        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    def serve_daily_stats(self, days: int = 7):
        """Serve daily usage statistics."""
        try:
            stats = db.get_daily_stats(days)
            for r in stats:
                for key in ["avg_percentage", "max_percentage", "min_percentage"]:
                    if r.get(key) is not None:
                        r[key] = round(r[key], 1)
            self.send_json({"daily": stats})
        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    def serve_weekly_stats(self, weeks: int = 4):
        """Serve weekly usage statistics."""
        try:
            stats = db.get_weekly_stats(weeks)
            for r in stats:
                for key in ["avg_percentage", "max_percentage", "min_percentage"]:
                    if r.get(key) is not None:
                        r[key] = round(r[key], 1)
            self.send_json({"weekly": stats})
        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    def serve_monthly_stats(self, months: int = 6):
        """Serve monthly usage statistics."""
        try:
            stats = db.get_monthly_stats(months)
            for r in stats:
                for key in ["avg_percentage", "max_percentage", "min_percentage"]:
                    if r.get(key) is not None:
                        r[key] = round(r[key], 1)
            self.send_json({"monthly": stats})
        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    def serve_range_stats(self, start_date: str, end_date: str):
        """Serve usage statistics for a specified date range."""
        try:
            stats = db.get_range_stats(start_date, end_date)
            self.send_json(stats)
        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    def serve_icon(self):
        """Serve dynamic SVG icon with current usage percentage."""
        try:
            summary = db.get_summary()
            pct = summary.get("current", {}).get("percentage", 0)

            # Icon params: 180x180, r=65, stroke-width=18
            circumference = 2 * 3.14159 * 65  # ≈ 408.4
            filled = circumference * pct / 100
            gap = circumference - filled
            dasharray = f"{filled:.1f} {gap:.1f}"

            svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 180 180">
    <rect width="180" height="180" rx="40" fill="#111827"/>
    <circle cx="90" cy="90" r="65" fill="none" stroke="#06b6d4" stroke-width="18" stroke-dasharray="{dasharray}" stroke-linecap="round" transform="rotate(-90 90 90)"/>
    <text x="90" y="115" font-family="system-ui,sans-serif" font-size="70" font-weight="700" fill="white" text-anchor="middle">M</text>
</svg>'''

            body = svg.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self.send_json({"error": str(e)}, 500)


def run_server(port: int = 8080):
    """Run the HTTP server."""
    db.init_db()

    server = HTTPServer(("0.0.0.0", port), RequestHandler)
    print(f"MiniMax Dashboard server running at http://0.0.0.0:{port}")
    print("Press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped")
        server.shutdown()


def main():
    parser = argparse.ArgumentParser(description="MiniMax Coding Plan Web Server")
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8080,
        help="Port to listen on (default: 8080)"
    )
    args = parser.parse_args()

    run_server(port=args.port)


if __name__ == "__main__":
    main()
