import zlib, struct, os

SIZE = 512
BG = (31, 111, 235, 255)      # 品牌蓝 #1f6feb
WHITE = (255, 255, 255, 255)
DARK = (31, 39, 51, 255)
YELLOW = (255, 221, 120, 255)
RED = (230, 80, 80, 255)

px = [[BG for _ in range(SIZE)] for _ in range(SIZE)]

def setp(x, y, c):
    x = int(x); y = int(y)
    if 0 <= x < SIZE and 0 <= y < SIZE:
        px[y][x] = c

def fill_rect(x0, y0, x1, y1, c):
    for y in range(int(y0), int(y1)):
        for x in range(int(x0), int(x1)):
            setp(x, y, c)

def fill_circle(cx, cy, rad, c):
    for y in range(int(cy - rad), int(cy + rad) + 1):
        for x in range(int(cx - rad), int(cx + rad) + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= rad * rad:
                setp(x, y, c)

def rrect(x0, y0, x1, y1, r, c):
    x0, y0, x1, y1, r = int(x0), int(y0), int(x1), int(y1), int(r)
    for y in range(y0, y1):
        for x in range(x0, x1):
            if x < x0 + r and y < y0 + r and (x - (x0 + r)) ** 2 + (y - (y0 + r)) ** 2 > r * r:
                continue
            if x > x1 - r and y < y0 + r and (x - (x1 - r)) ** 2 + (y - (y0 + r)) ** 2 > r * r:
                continue
            if x < x0 + r and y > y1 - r and (x - (x0 + r)) ** 2 + (y - (y1 - r)) ** 2 > r * r:
                continue
            if x > x1 - r and y > y1 - r and (x - (x1 - r)) ** 2 + (y - (y1 - r)) ** 2 > r * r:
                continue
            setp(x, y, c)

# 车身
rrect(96, 268, 416, 360, 26, WHITE)
# 车舱
rrect(150, 196, 362, 274, 22, WHITE)
# 车窗（留出蓝色分隔）
fill_rect(168, 210, 232, 262, BG)
fill_rect(244, 210, 300, 262, BG)
fill_rect(312, 210, 344, 262, BG)
# 车轮 + 轮毂
fill_circle(168, 360, 42, DARK); fill_circle(168, 360, 16, WHITE)
fill_circle(344, 360, 42, DARK); fill_circle(344, 360, 16, WHITE)
# 前大灯 / 尾灯
fill_rect(402, 290, 414, 306, YELLOW)
fill_rect(98, 290, 110, 306, RED)

def write_png(path):
    raw = bytearray()
    for row in px:
        raw.append(0)
        for (r, g, b, a) in row:
            raw += bytes((r, g, b, a))
    comp = zlib.compress(bytes(raw), 9)
    def chunk(typ, data):
        return (struct.pack('>I', len(data)) + typ + data +
                struct.pack('>I', zlib.crc32(typ + data) & 0xffffffff))
    png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', SIZE, SIZE, 8, 6, 0, 0, 0)) +
           chunk(b'IDAT', comp) + chunk(b'IEND', b''))
    with open(path, 'wb') as f:
        f.write(png)

write_png('icon-512.png')

# 生成 192 版本（最近邻下采样，保持内容在安全区内）
out = [[BG for _ in range(192)] for _ in range(192)]
for ty in range(192):
    for tx in range(192):
        sx = min(SIZE - 1, round(tx * SIZE / 192))
        sy = min(SIZE - 1, round(ty * SIZE / 192))
        out[ty][tx] = px[sy][sx]
px192 = out
path192 = 'icon-192.png'
raw = bytearray()
for row in px192:
    raw.append(0)
    for (r, g, b, a) in row:
        raw += bytes((r, g, b, a))
comp = zlib.compress(bytes(raw), 9)
def chunk(typ, data):
    return (struct.pack('>I', len(data)) + typ + data + struct.pack('>I', zlib.crc32(typ + data) & 0xffffffff))
png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 192, 192, 8, 6, 0, 0, 0)) +
       chunk(b'IDAT', comp) + chunk(b'IEND', b''))
with open(path192, 'wb') as f:
    f.write(png)

print('icons generated:', os.path.getsize('icon-512.png'), os.path.getsize('icon-192.png'))
