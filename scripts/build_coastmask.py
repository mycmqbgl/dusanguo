#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 DEM 提取海岸掩膜（画布像素坐标，1400×1200），供州界贴合与陆面裁剪使用。

为什么不用 data/geo-real.json 的 coast：
  那条海岸线是粗概化折线（相邻顶点间隔 0.25~1°），且把渤海、黄海北部的
  许多岛屿与岸线混在一起；用它做「贴近海岸」会把州界吸到错误的折线上
  （实测幽州东南界被拽成一条斜穿辽东湾的直线）。

本脚本输出 build/coastmask.json：
  { "grid": [W,H] 分辨率,
    "mask": base64(zlib(uint8 0/1))  # 1=陆地
    "rings": [[[x,y]...]]            # 陆面主环（像素坐标，已抽稀） }
"""
import base64, io, json, math, os, sys, zlib
import numpy as np
from PIL import Image
from shapely.geometry import Polygon
from shapely.ops import unary_union

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

W, H = 1400, 1200
SCALE = 3
LNG0, LNG1, LAT0, LAT1 = 97.0, 126.0, 18.0, 44.0
_MIDLAT = math.radians((LAT0 + LAT1) / 2)
_COS = math.cos(_MIDLAT)
_K = min(W / ((LNG1 - LNG0) * _COS), H / (LAT1 - LAT0))
_OFF_X = (W - (LNG1 - LNG0) * _COS * _K) / 2
Z = 8


def tx(lng):
    return (lng + 180.0) / 360.0 * (1 << Z)


def ty(lat):
    r = np.radians(lat)
    return (1 - np.arcsinh(np.tan(r)) / np.pi) / 2 * (1 << Z)


grid = np.load(os.path.join(ROOT, 'data/ne/dem_grid.npy'))
meta = json.load(io.open(os.path.join(ROOT, 'data/ne/dem_grid.npy.json'), encoding='utf-8'))
ox = int(tx(LNG0)) * 256   # 格网原点 = x0*256（不能加 frac，见 build_terrain.py 注释）
oy = int(ty(LAT1)) * 256
print('DEM %s，原点 (%.2f, %.2f)' % (grid.shape, ox, oy))

# 画布像素 → DEM 采样
js, is_ = np.meshgrid(np.arange(H), np.arange(W), indexing='ij')
lng = LNG0 + (is_ - _OFF_X) / (_COS * _K)
lat = LAT1 - js / _K
mx = tx(lng) * 256 - ox
my = ty(lat) * 256 - oy
i0 = np.clip(np.floor(my).astype(np.int64), 0, grid.shape[0] - 2)
j0 = np.clip(np.floor(mx).astype(np.int64), 0, grid.shape[1] - 2)
elev = grid[i0, j0]
inside = (is_ >= _OFF_X) & (is_ <= _OFF_X + (LNG1 - LNG0) * _COS * _K)
land = (elev > 0) & inside
print('陆地占比 %.3f' % land.mean())

# 形态学清理：去掉 1px 噪声
def erode(a):
    b = a.copy()
    b[1:, :] &= a[:-1, :]; b[:-1, :] &= a[1:, :]
    b[:, 1:] &= a[:, :-1]; b[:, :-1] &= a[:, 1:]
    return b


def dilate(a):
    b = a.copy()
    b[1:, :] |= a[:-1, :]; b[:-1, :] |= a[1:, :]
    b[:, 1:] |= a[:, :-1]; b[:, :-1] |= a[:, 1:]
    return b


clean = dilate(erode(land))
clean = erode(dilate(clean))
print('清理后陆地占比 %.3f' % clean.mean())

img = Image.fromarray((clean * 255).astype(np.uint8), 'L')
img.save(os.path.join(ROOT, 'build/coastmask.png'))

# 矢量化（粗网格 → 多边形环），用于州界贴合时算最近海岸
small = np.array(Image.fromarray((clean * 255).astype(np.uint8), 'L').resize((W // 2, H // 2), Image.BILINEAR)) > 127
# 简易 marching-squares 替代：用 PIL 的轮廓追踪不可靠，改在 1/4 分辨率上建多边形
import shapely
from shapely.geometry import box as sbox

cell = 4
gw, gh = W // cell, H // cell
m = np.array(Image.fromarray((clean * 255).astype(np.uint8), 'L').resize((gw, gh), Image.BILINEAR)) > 127
boxes = []
for j in range(gh):
    row = m[j]
    for i in range(gw):
        if row[i]:
            boxes.append(sbox(i * cell, j * cell, (i + 1) * cell, (j + 1) * cell))
u = unary_union(boxes).simplify(1.5, preserve_topology=True)
parts = [g for g in (u.geoms if hasattr(u, 'geoms') else [u]) if g.geom_type == 'Polygon']
parts.sort(key=lambda g: -g.area)
rings = [[[round(c[0], 1), round(c[1], 1)] for c in g.exterior.coords] for g in parts[:80]]
print('陆面环：%d（最大面积 %.0f px²）' % (len(rings), parts[0].area))

packed = base64.b64encode(zlib.compress((clean.astype(np.uint8) * 255).tobytes(), 9)).decode('ascii')
json.dump({'w': W, 'h': H, 'mask_b64': packed, 'rings': rings},
          io.open(os.path.join(ROOT, 'build/coastmask.json'), 'w', encoding='utf-8'),
          ensure_ascii=False)
print('完成 → build/coastmask.json')
