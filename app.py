#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
车管家 · 汽车维修保养记录 —— NAS 部署后端
==========================================
纯标准库实现，无需 pip 安装任何依赖。

· 提供静态文件服务（手机/电脑浏览器访问）
· 通过 /api/data 将全量数据持久化到 NAS 本地的 data/db.json
· 前端会自动探测：能连上本服务 → 数据存 NAS；连不上 → 数据存手机浏览器(localStorage)

部署（QNAP/群晖/任意 Linux NAS）：
    python3 app.py
默认端口 8143，可用环境变量覆盖：PORT=9000 python3 app.py

Container Station / docker-compose 时，把本目录挂载进容器，命令填：
    python3 /app/app.py
并映射端口（如 8143:8143）。
注意：应用代码用 ./:/app 挂载时，改完源码 restart 即可，无需重建镜像。
"""
import http.server
import socketserver
import json
import os
import sys

PORT = int(os.environ.get("PORT", "8143"))
BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")
DB_PATH = os.path.join(DATA_DIR, "db.json")
os.makedirs(DATA_DIR, exist_ok=True)

CT = {
    "html": "text/html; charset=utf-8",
    "js": "application/javascript; charset=utf-8",
    "css": "text/css; charset=utf-8",
    "json": "application/json; charset=utf-8",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "svg": "image/svg+xml",
    "webmanifest": "application/manifest+json",
    "ico": "image/x-icon",
}


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "CarCareNAS/1.0"

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(204, b"")

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/health":
            return self._send(200, json.dumps({"ok": True, "mode": "nas"}))
        if path == "/api/data":
            try:
                with open(DB_PATH, "r", encoding="utf-8") as f:
                    data = f.read()
            except FileNotFoundError:
                data = "{}"
            return self._send(200, data, CT["json"])
        return self.serve_static(path)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/data":
            length = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                json.loads(raw)
            except Exception:
                return self._send(400, json.dumps({"error": "invalid json"}))
            tmp = DB_PATH + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(raw.decode("utf-8"))
            os.replace(tmp, DB_PATH)  # 原子写，避免半截文件
            return self._send(200, json.dumps({"ok": True}))
        return self._send(404, json.dumps({"error": "not found"}))

    def serve_static(self, path):
        rel = "index.html" if path in ("/", "/index.html") else path.lstrip("/")
        fp = os.path.normpath(os.path.join(BASE, rel))
        # 防目录穿越
        if not fp.startswith(BASE):
            return self._send(403, "forbidden", "text/plain; charset=utf-8")
        if os.path.isfile(fp):
            ext = fp.rsplit(".", 1)[-1].lower()
            with open(fp, "rb") as f:
                return self._send(200, f.read(), CT.get(ext, "application/octet-stream"))
        return self._send(404, "not found", "text/plain; charset=utf-8")

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", PORT), Handler) as httpd:
        print(f"车管家 NAS 服务已启动: http://0.0.0.0:{PORT}")
        print(f"数据文件: {DB_PATH}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止")
            sys.exit(0)
