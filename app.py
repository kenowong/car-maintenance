#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
车管家 · 汽车维修保养记录 —— NAS 部署后端（网页 + 数据同步一体）
==================================================================
纯标准库实现，无需 pip 安装任何依赖。

功能：
· 静态文件服务：手机/电脑浏览器访问（页面 + PWA 资源）
· 数据持久化：整库 JSON 原子写入本地 data/db.json
· 双协议兼容（老网页与新 APK 同步都用同一个端口）：
    - 旧版网页 NAS 模式：GET /api/data（读）、POST /api/data（写）
    - v6 APK / 新版网页 NAS 同步：GET /api/ping（连通检测）、
      GET/PUT /api/data（写走 PUT），可选请求头 X-Sync-Key
· 可选访问密钥：SYNC_KEY 环境变量（防止同局域网其他人读写你的数据）

部署（QNAP/群晖/任意 Linux NAS，Python ≥ 3.8）：
    python3 app.py                          # 默认端口 8143
    PORT=9000 python3 app.py                # 换端口
    SYNC_KEY=自己编一串密码 python3 app.py  # 开启访问密钥（App 里填同一串）

Docker / Container Station：
    python3 /app/app.py      # 源码用 ./:/app 挂载，映射 8143:8143
    （改完源码 docker compose restart <服务> 即可，无需重建镜像）

数据文件：data/db.json（删掉它 = 服务器端数据清空）
"""
import http.server
import socketserver
import json
import os
import sys
import hmac

PORT = int(os.environ.get("PORT", "8143"))
SYNC_KEY = os.environ.get("SYNC_KEY", "") or None  # 设了则 /api/* 需带 X-Sync-Key
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

    # ---------- 工具 ----------
    def _auth_ok(self):
        """未设 SYNC_KEY 一律放行；设了则比对 X-Sync-Key 头。"""
        if not SYNC_KEY:
            return True
        got = self.headers.get("X-Sync-Key", "")
        return hmac.compare_digest(got, SYNC_KEY)

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        # CORS 全放行：跨源(https appassets / github.io)也能直连 http NAS
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Sync-Key")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_db(self):
        try:
            with open(DB_PATH, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return "{}"

    def _write_db(self, raw):
        try:
            json.loads(raw)  # 校验必须是合法 JSON
        except Exception:
            return False
        tmp = DB_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(raw)
        os.replace(tmp, DB_PATH)  # 原子写，避免半截文件
        return True

    # ---------- HTTP 方法 ----------
    def do_OPTIONS(self):                      # PUT + 自定义头会先触发预检
        self._send(204, b"")

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/ping":                # v6 同步：连通性检测
            if not self._auth_ok():
                return self._send(401, json.dumps({"error": "bad key"}))
            return self._send(200, json.dumps({"ok": True, "mode": "nas", "sync": True}))
        if path == "/api/data":
            if not self._auth_ok():
                return self._send(401, json.dumps({"error": "bad key"}))
            return self._send(200, self._read_db(), CT["json"])
        return self.serve_static(path)

    def do_POST(self):                         # 旧网页 NAS 模式写库
        self._handle_data_write()

    def do_PUT(self):                          # v6 同步写库
        self._handle_data_write()

    def _handle_data_write(self):
        path = self.path.split("?", 1)[0]
        if path != "/api/data":
            return self._send(404, json.dumps({"error": "not found"}))
        if not self._auth_ok():
            return self._send(401, json.dumps({"error": "bad key"}))
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            raw = raw.decode("utf-8")
        except Exception:
            return self._send(400, json.dumps({"error": "invalid utf-8"}))
        if not self._write_db(raw):
            return self._send(400, json.dumps({"error": "invalid json"}))
        return self._send(200, json.dumps({"ok": True}))

    # ---------- 静态文件 ----------
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
        print(f"访问密钥: {'已开启（需 X-Sync-Key）' if SYNC_KEY else '未开启'}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止")
            sys.exit(0)
