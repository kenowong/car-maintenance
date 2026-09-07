#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
车管家 NAS 数据同步服务（单文件 · 零第三方依赖）

用途：
    给「车管家」App / 网页版提供局域网数据备份与多设备共用。
    App 设置页 →「数据存储与 NAS 同步」→ 填写本服务地址即可。

运行：
    python3 carcare-sync-server.py [端口]        # 默认端口 8765

可选环境变量：
    SYNC_KEY=xxxx    设置后客户端必须填相同的访问密钥，否则拒绝读写
    PORT=xxxx        不传命令行参数时用此端口

数据文件：
    保存在脚本同目录 carcare_data.json（每次写入先写临时文件再原子替换，
    不怕断电写坏）。删除该文件 = 服务器端数据清空。

验证：
    浏览器打开  http://NAS地址:8765/api/ping   应返回 {"ok": true, ...}
"""
import http.server
import json
import os
import sys
import threading
import time

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "carcare_data.json")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", "8765"))
KEY = os.environ.get("SYNC_KEY", "").strip()          # 留空 = 不校验
LOCK = threading.Lock()


def _load():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save(data):
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, DATA_FILE)


class Handler(http.server.BaseHTTPRequestHandler):
    # ---------- CORS：App 页面(https://appassets…/https 站点)跨源访问本服务 ----------
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,PUT,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type,X-Sync-Key")
        self.send_header("Access-Control-Max-Age", "86400")

    def _auth_ok(self):
        if not KEY:
            return True
        return self.headers.get("X-Sync-Key", "") == KEY

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            pass

    def _path(self):
        return self.path.split("?")[0]

    def do_OPTIONS(self):                      # PUT + 自定义头会先触发预检
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        p = self._path()
        if p == "/api/ping":
            self._json(200, {"ok": True, "name": "carcare-sync", "t": int(time.time())})
            return
        if p == "/api/data":
            if not self._auth_ok():
                self._json(401, {"error": "bad key"})
                return
            with LOCK:
                self._json(200, _load())
            return
        self._json(404, {"error": "not found"})

    def do_PUT(self):
        p = self._path()
        if p != "/api/data":
            self._json(404, {"error": "not found"})
            return
        if not self._auth_ok():
            self._json(401, {"error": "bad key"})
            return
        try:
            n = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(n).decode("utf-8"))
            if not isinstance(data, dict) or "vehicles" not in data:
                raise ValueError("数据格式不正确")
            with LOCK:
                _save(data)
            self._json(200, {"ok": True, "bytes": os.path.getsize(DATA_FILE)})
        except Exception as e:                 # noqa: BLE001
            self._json(400, {"error": str(e)[:200]})

    def log_message(self, *a):                 # 安静模式，不刷日志
        pass


if __name__ == "__main__":
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    print("[carcare-sync] 车管家数据同步服务")
    print(f"  监听端口 : {PORT}")
    print(f"  数据文件 : {DATA_FILE}")
    print(f"  访问密钥 : {'已设置 (SYNC_KEY)' if KEY else '未设置（局域网内任何人都可读写）'}")
    print("  手机 App 设置页填写地址 → http://<本机IP>:%d" % PORT)
    http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
