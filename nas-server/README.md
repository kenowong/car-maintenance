# 车管家 NAS 同步服务（nas-server）

让「车管家」的数据从「仅存手机」升级为「本机 + NAS 双份」：手机每次改动自动备份到 NAS，
可多设备共用、换机不丢。**只在局域网内使用，不经过任何第三方服务器。**

## 一、部署到 QNAP NAS（手动上传，约 2 分钟）

前提：NAS 已从 App Center 装好 **Python 3**（版本 ≥ 3.8 即可）。

1. **上传文件**
   用 File Station 把本目录的 `carcare-sync-server.py` 传到 NAS，例如放到：
   `/share/CACHEDEV1_DATA/车管家同步/`

2. **启动服务**（SSH 登录 NAS 后执行）
   ```bash
   cd /share/CACHEDEV1_DATA/车管家同步
   python3 carcare-sync-server.py 8765
   ```
   看到 `监听端口 : 8765` 即成功。
   > 想让 NAS 重启后自动运行，可把它做成开机启动脚本（QTS：控制台→开机自启动脚本，
   > 追加一行 `nohup python3 /share/.../carcare-sync-server.py 8765 &`）。

3. **建议设置访问密钥**（防止同局域网其他人读写你的数据）：
   ```bash
   SYNC_KEY=自己编一串密码 python3 carcare-sync-server.py 8765
   ```
   设了密钥后，手机 App 里也要填同一个密钥。

## 二、手机 App 里开启

1. 打开车管家 → **设置**
2. 找到 **「数据存储与 NAS 同步」**，打开右侧开关
3. 填 **NAS 服务器地址**：`http://<NAS的局域网IP>:8765`
   （IP 在 NAS 控制台能看到，形如 `192.168.1.5`；设了密钥就填在访问密钥栏）
4. 点 **测试连接** → 提示「连接正常」后点 **立即同步**

顶部徽标会从「数据·本机」变成「数据·NAS」，说明已经双份备份了。

## 三、工作原理与同步策略（简单可靠）

- **数据永远先存手机本地**（离线秒开）；NAS 同步是异步备份，不卡操作
- 每份数据带保存时间戳，连接时**自动取较新的一份**
- 每次改动自动推送到 NAS（连续改动合并、串行、不重复写）
- 服务器只存一份 JSON（`carcare_data.json`），删掉它 = 服务器端数据清空

## 四、接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/ping` | 连通性检测 |
| GET | `/api/data` | 读取整库（可选请求头 `X-Sync-Key`） |
| PUT | `/api/data` | 写入整库（可选请求头 `X-Sync-Key`） |

已开放跨域（CORS），Android 离线版与网页版均可直连。
