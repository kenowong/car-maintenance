#!/bin/bash
# 车管家 · QNAP 直接用 Python 启动（绕过 Docker 镜像拉取问题）
# 用法：
#   1) 把整个 car-maintenance 文件夹上传到 NAS，例如 /share/CACHEDEV1_DATA/container/car-maintenance/
#   2) SSH 登录 NAS（用户 sexsnail），cd 到该目录
#   3) 赋予执行权限： chmod +x start.sh
#   4) 启动： ./start.sh
#
# 说明：
#   - 用 App Center 装的 Python 3.12 运行，无需 pip、无需 Docker。
#   - 数据自动落在同目录的 data/db.json（已持久化在 CACHEDEV1 磁盘上）。
#   - 监听 0.0.0.0:8143，手机用「http://NAS的局域网IP:8143」即可访问，数据存在 NAS。
#   - Ctrl+C 停止；想开机自启见下方 crontab 一行。

# 扩展 PATH：cron 环境下 PATH 很干净，先把常见目录加上，避免找不到 python3 / nohup
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"

# 自动定位 python3：优先用 PATH 里的，找不到再依次尝试 QNAP 各 QPKG 路径
PY="${PY:-}"
if [ -z "$PY" ] || ! command -v "$PY" >/dev/null 2>&1; then
  for p in python3 python /share/CACHEDEV1_DATA/.qpkg/Python3/bin/python3 /share/CACHEDEV1_DATA/.qpkg/Python312/bin/python3; do
    if command -v "$p" >/dev/null 2>&1; then PY="$p"; break; fi
  done
fi
echo "使用 Python: ${PY:-未找到}"

cd "$(dirname "$0")"

# 防止重复启动：如果已有 app.py 在跑，直接退出
if ps | grep -q "[a]pp.py"; then
  echo "车管家已经在运行，无需重复启动"
  exit 0
fi

# 后台常驻，日志写到 carcare.log
# 注意：QNAP busybox 没有 nohup，直接用 & 后台；结合 crontab 每 5 分钟保活即可。
"$PY" app.py > carcare.log 2>&1 &
PID=$!
echo $PID > carcare.pid
echo "车管家已启动，端口 8143（PID $PID）"
echo "日志： tail -f carcare.log"
echo "停止： kill $PID"

# ===== 开机自启 / 保活（推荐，QNAP busybox cron 不支持 @reboot）=====
# 用下面这条 crontab 命令（无需进 vi）：每 5 分钟检查一次，没在跑就拉起。
# 既开机自启，又能在进程崩溃时自动恢复。
# 注意：QNAP 普通用户执行 crontab 会报 "must be suid"，需先 `sudo -s` 切到 root 再执行：
#   (crontab -l 2>/dev/null; echo '*/5 * * * * if ! ps | grep -q "[a]pp.py"; then /bin/bash /share/CACHEDEV1_DATA/container/car-maintenance/start.sh; fi') | crontab -
#
# 备选：若控制台能找到「任务计划」（需切到进阶模式），建「开机执行」任务，
#       命令填： /bin/bash /share/CACHEDEV1_DATA/container/car-maintenance/start.sh
