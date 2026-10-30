# -*- coding: utf-8 -*-
"""P2-R 地形晕渲底图

数据源：AWS Open Data「Terrarium」DEM 瓦片（Zoom 8，含陆高与海深，Mercator 投影）
  https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png

处理：
  1. 下载覆盖画布范围（97–126E / 18–44N）的 z8 瓦片，拼成高程格网
  2. 重投影到本项目的像素投影（等经距 + 标准纬线 cos31°，与 build.py::project 一致）
  3. 高程分色（hypsometric tint，仿谭图淡彩）× 山体阴影（hillshade）× 海域分层
  4. 输出 app/assets/terrain.png（2 倍分辨率 RGBA，投影矩形之外透明）

海岸线由 DEM 0m 等高线自然产生（现代海岸，苏北一带与东汉有差异，与矢量层同口径）。
"""
import io, json, math, os, sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 与 build.py CANVAS 保持一致（此处复制常量，build.py 是唯一权威）
W, H = 1400, 1200
LNG0, LNG1, LAT0, LAT1 = 97.0, 126.0, 18.0, 44.0
_MIDLAT = math.radians((LAT0 + LAT1) / 2)
_COS = math.cos(_MIDLAT)
_K = min(W / ((LNG1 - LNG0) * _COS), H / (LAT1 - LAT0))
_OFF_X = (W - (LNG1 - LNG0) * _COS * _K) / 2

SCALE = 3                 # 输出分辨率倍数（4200×3600，z8 DEM 重采样约 145px/°，高级缩放不糊）
Z = 8                     # DEM 瓦片层级
TILE_URL = 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'

# ---------------------------------------------------------------- 瓦片下载
def tile_x(lng, z): return (lng + 180.0) / 360.0 * (1 << z)
def tile_y(lat, z):
    r = math.radians(lat)
    return (1 - math.asinh(math.tan(r)) / math.pi) / 2 * (1 << z)

def fetch_tile(tx, ty):
    url = TILE_URL.format(z=Z, x=tx, y=ty)
    for attempt in (0, 1, 2):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                img = Image.open(io.BytesIO(r.read())).convert('RGB')
            a = np.asarray(img, dtype=np.float32)
            return a[:, :, 0] * 256 + a[:, :, 1] + a[:, :, 2] / 256 - 32768
        except Exception:
            if attempt == 2:
                raise
    return None

def build_grid():
    x0, x1 = int(tile_x(LNG0, Z)), int(tile_x(LNG1, Z))
    y0, y1 = int(tile_y(LAT1, Z)), int(tile_y(LAT0, Z))   # 上纬对应小 y
    xs = list(range(x0, x1 + 1)); ys = list(range(y0, y1 + 1))
    print('DEM 瓦片 z%d：%d×%d = %d 张' % (Z, len(xs), len(ys), len(xs) * len(ys)))
    grid = np.zeros((len(ys) * 256, len(xs) * 256), dtype=np.float32)
    def one(args):
        i, j, tx, ty = args
        return i, j, fetch_tile(tx, ty)
    jobs = [(i, j, tx, ty) for j, ty in enumerate(ys) for i, tx in enumerate(xs)]
    with ThreadPoolExecutor(max_workers=12) as ex:
        for i, j, a in ex.map(one, jobs):
            grid[j*256:(j+1)*256, i*256:(i+1)*256] = a
    # 瓦片原点（格网 [0,0] 像素）在墨卡托世界像素坐标系中的位置 = x0*256。
    # ★ 不能再加 tile_x(LNG0)%1*256：x0=int(tile_x) 已经把小数部分 floor 掉了，
    #   再加 frac 等于把整幅格网向左/上平移一个"分数瓦片"（≈0.98°），底图整体错位。
    ox = x0 * 256
    oy = y0 * 256
    return grid, ox, oy

# ---------------------------------------------------------------- 重投影
def reproject(grid, ox, oy):
    OW, OH = W * SCALE, H * SCALE
    # 输出像素 → 经纬度（与 project() 反算一致，x 用 SCALE/2 抵消）
    js, is_ = np.meshgrid(np.arange(OH), np.arange(OW), indexing='ij')
    lng = LNG0 + (is_ / SCALE - _OFF_X) / (_COS * _K)
    lat = LAT1 - (js / SCALE) / _K
    # 经纬度 → 墨卡托像素
    mx = (lng + 180.0) / 360.0 * (1 << Z) * 256 - ox
    r = np.radians(lat)
    my = (1 - np.arcsinh(np.tan(r)) / math.pi) / 2 * (1 << Z) * 256 - oy
    # 双线性采样
    x0f = np.floor(mx).astype(np.int64); y0f = np.floor(my).astype(np.int64)
    fx = mx - x0f; fy = my - y0f
    gh, gw = grid.shape
    x0c = np.clip(x0f, 0, gw - 2); y0c = np.clip(y0f, 0, gh - 2)
    x1c = x0c + 1; y1c = y0c + 1
    v = (grid[y0c, x0c] * (1 - fx) * (1 - fy) + grid[y0c, x1c] * fx * (1 - fy)
         + grid[y1c, x0c] * (1 - fx) * fy + grid[y1c, x1c] * fx * fy)
    # 投影矩形之外的画布边距 → NaN（转透明）
    inside = (is_ / SCALE >= _OFF_X) & (is_ / SCALE <= _OFF_X + (LNG1 - LNG0) * _COS * _K)
    v = np.where(inside, v, np.nan)
    return v, inside, lng, lat

# ---------------------------------------------------------------- 配色
def lerp(c1, c2, t):
    return c1 + (c2 - c1) * t

# 高程分档（米）→ RGB（仿谭图淡彩：平原绿、丘陵黄、山地棕、高原灰紫）
BANDS = [
    (-8000, (168, 192, 209)),   # 深海
    (-200,  (181, 203, 218)),   # 近海
    (0,     (214, 226, 219)),   # 海岸/滨海
    (50,    (206, 213, 178)),   # 平原
    (200,   (209, 206, 164)),   # 台地
    (500,   (205, 189, 148)),   # 低丘
    (1000,  (189, 167, 126)),   # 山地
    (2000,  (170, 143, 106)),   # 高山
    (3500,  (152, 126, 100)),   # 高原
    (5000,  (196, 190, 184)),   # 雪线/极高山
]
def hypso(elev):
    out = np.zeros(elev.shape + (3,), dtype=np.float32)
    for lo1, c1 in zip(BANDS[:-1], BANDS[1:]):
        pass
    for i in range(len(BANDS) - 1):
        e0, c0 = BANDS[i]; e1, c1 = BANDS[i + 1]
        m = (elev >= e0) & (elev < e1)
        if not m.any():
            continue
        t = np.clip((elev[m] - e0) / (e1 - e0), 0, 1)
        t = t[..., None]
        col = np.asarray(c0, dtype=np.float32) * (1 - t) + np.asarray(c1, dtype=np.float32) * t
        out[m] = col
    m = elev >= BANDS[-1][0]
    out[m] = BANDS[-1][1]
    return out

def hillshade(elev):
    """山体阴影：az 315°，alt 45°。格网间距近似用输出像素。"""
    gy, gx = np.gradient(elev)
    slope = np.pi / 2 - np.arctan(np.hypot(gx, gy) * 3.0)   # 3.0 ≈ 每像素≈333m 的坡度放大
    aspect = np.arctan2(-gx, gy)
    az = math.radians(315.0); alt = math.radians(45.0)
    sh = (np.sin(alt) * np.sin(slope)
          + np.cos(alt) * np.cos(slope) * np.cos(az - aspect))
    return np.clip(sh, 0, 1)

# 汉代为海、现代为陆的淤进区（与 prepare_geo.py 的手工海岸线同口径）。
# 多边形内的高程强制设为浅海（-2m），使地形底图上的"汉海"呈海色。
HAND_SEA = [
    # 渤海湾西—黄河口（禹河口以西至天津）。非海岸边（北/东界）全部推进到
    # 渤海中部海域，避开山东半岛北岸陆地，避免在海底晕渲上切出直边
    [(117.0,40.5),(117.28,39.6),(117.35,39.3),(117.5,39.05),(117.65,38.8),(117.85,38.55),
     (118.05,38.3),(118.3,38.0),(118.55,37.7),(118.9,37.5),(119.3,37.45),(119.65,37.3),
     (119.8,37.6),(120.05,37.8),(120.25,38.15),(120.55,38.6),(120.65,39.4),(120.65,40.5)],
    # 苏北（1128 年黄河夺淮后淤出的滨海平原）
    [(119.88,34.95),(119.7,34.4),(119.78,34.0),(119.83,33.5),(119.88,33.0),(119.93,32.7),
     (120.02,32.5),(120.0,32.3),(121.15,32.35),(121.15,35.0)],
    # 长江口—上海—杭州湾北（汉代口门在镇江—扬州，上海大部尚未成陆）
    [(120.22,32.0),(120.3,32.1),(120.4,32.3),(120.5,32.45),(120.65,32.55),(121.2,32.55),
     (122.5,32.75),(122.5,29.9),(121.9,29.95),(121.75,30.2),(121.55,30.32),(121.3,30.48),
     (121.15,30.65),(121.0,30.8),(120.85,30.95),(120.62,31.2),(120.6,31.5),(120.6,31.75),
     (120.4,31.85)],
]

def sea_mask(lng, lat, polys):
    """射线法（向量化）：点是否落在任一汉海多边形内"""
    m = np.zeros(lng.shape, dtype=bool)
    for poly in polys:
        inside = np.zeros(lng.shape, dtype=bool)
        n = len(poly)
        for i in range(n):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % n]
            if y1 == y2:
                continue
            cross = (y1 > lat) != (y2 > lat)
            xint = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
            inside ^= cross & (lng < xint)
        m |= inside
    return m

def main():
    cache = os.path.join(ROOT, 'data', 'ne', 'dem_grid.npy')
    meta = cache + '.json'
    if os.path.exists(cache) and os.path.exists(meta):
        g = json.load(io.open(meta, encoding='utf-8'))
        if g['z'] == Z:
            grid = np.load(cache)
            ox, oy = g['ox'], g['oy']
            print('使用缓存高程格网', grid.shape)
        else:
            grid, ox, oy = build_grid()
    else:
        grid, ox, oy = build_grid()
    np.save(cache, grid)
    json.dump({'z': Z, 'ox': ox, 'oy': oy}, io.open(meta, 'w'))
    print('高程格网 %d×%d，范围 %.0f–%.0f m' % (grid.shape[1], grid.shape[0], grid.min(), grid.max()))
    elev, inside, lngs, lats = reproject(grid, ox, oy)
    han_sea = sea_mask(lngs, lats, HAND_SEA).astype(np.float32)
    # 羽化：mask 高斯模糊 → 与浅海高程混合，涂海边界平滑过渡无直边
    from PIL import ImageFilter
    mimg = Image.fromarray((han_sea * 255).astype(np.uint8))
    mimg = mimg.filter(ImageFilter.GaussianBlur(radius=36))
    mf = np.asarray(mimg, dtype=np.float32) / 255.0
    elev = np.where(np.isfinite(elev), elev * (1 - mf) + (-6.0) * mf, elev)
    print('汉海淤进区涂海：核心 %d px（羽化过渡）' % int((han_sea > 0.5).sum()))
    land = elev > 0
    sea = np.isfinite(elev) & ~land
    col = hypso(np.where(np.isfinite(elev), elev, 0))
    # 海面压平阴影（海也保留一点深浅纹理）
    sh = hillshade(np.where(np.isfinite(elev), elev, 0))
    col[land] *= (0.82 + 0.30 * sh[land])[:, None]
    col[land] = np.clip(col[land], 0, 255)
    # 海：轻微按深度变深
    depth = np.clip(-elev / 4000, 0, 1)
    for c in range(3):
        col[:, :, c][sea] *= (1 - 0.22 * depth[sea])
    alpha = np.where(inside, 255, 0).astype(np.uint8)
    img = np.dstack([col.astype(np.uint8), alpha])
    out = os.path.join(ROOT, 'app', 'assets', 'terrain.png')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    Image.fromarray(img, 'RGBA').save(out, optimize=True)
    print('输出 %s（%d×%d，%d KB）' % (out, img.shape[1], img.shape[0],
          os.path.getsize(out) // 1024))

if __name__ == '__main__':
    main()
