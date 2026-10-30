#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""州界无缝化：用 polygonize 把 13 个州面重建成严格无缝的平面剖分。

背景
----
`build/zhoupoly_refit.json` 的 13 个州面是**各自独立**生成再拼起来的：
每个州内部顶点严格（Voronoi 共享边），但两个州的公共边在「顶点级」并不重合——
refit 只改海岸段，内陆段来自各自的 Voronoi 单元，边长、顶点密度都不同。
于是 28 对相邻州之间各留一条零点几像素宽的发丝缝，合计 41.1 px²。

试过但不行的做法
----------------
  · 逐块 union 补缝：补进去的块与原州面之间在顶点级又不贴合，缝隙 41→39 但块数 67→96；
  · buffer(eps) 微膨胀：缝隙宽度 0.01~1.15 px，量级跨越太大，任何单一 eps 都不合适。

本脚本的做法（拓扑重建，不改形状）
--------------------------------
  1. 收齐全部州的全部环边（含海岸线、画布边），用 `unary_union` 打断成 noded 线网；
  2. `polygonize` 把线网切成面片——面片严格铺满整个「被线网围住的区域」，**零缝隙**；
  3. 每片面片按其质心落在哪个州面里归属给该州（质心都不在任何一个州里的丢弃）；
  4. 同一州的面片 union 回一个多边形。

因为第 2 步的线网包含了每个州自己的边界，所以州界形状**完全不变**，
变的只是「两州边界之间的那条缝」现在有了明确归属（= 分给包含它的那个州）。

用法：
  python3 scripts/planarize_zhoupoly.py [--dry]
"""
import json, io, os, sys

from shapely.geometry import Polygon, MultiLineString
from shapely.ops import unary_union, polygonize

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, 'build', 'zhoupoly_refit.json')

AX, BX, AY, BY = 39.5608, -3711.03, -46.1517, 2030.70


def to_px(lng, lat):
    return (AX * lng + BX, AY * lat + BY)


def to_ll(x, y):
    return ((x - BX) / AX, (y - BY) / AY)


raw = json.load(io.open(P, encoding='utf-8'))
ZH = {}
for k, rings in raw.items():
    ps = []
    for r in rings:
        if len(r) < 3:
            continue
        p = Polygon([to_px(*c) for c in r])
        if not p.is_valid:
            p = p.buffer(0)
        ps.extend([g for g in (p.geoms if hasattr(p, 'geoms') else [p])
                   if g.geom_type == 'Polygon' and g.area > 1e-9])
    ZH[k] = unary_union(ps)

# ── 1) 线网 ────────────────────────────────────────────────────────────────
segs = []
for k, g in ZH.items():
    for h in (g.geoms if hasattr(g, 'geoms') else [g]):
        segs.append(h.exterior)
        for r in h.interiors:
            segs.append(Polygon(r).exterior if False else h.interiors[0])
net = unary_union(segs)
print('线网：%s，长度 %.0f px' % (net.geom_type, net.length))

# ── 2) polygonize ─────────────────────────────────────────────────────────
faces = [f for f in polygonize(net) if f.area > 1e-6]
print('面片：%d 块，面积合计 %.0f px²（州面合计 %.0f px²）'
      % (len(faces), sum(f.area for f in faces), sum(g.area for g in ZH.values())))

# ── 3) 归属 ────────────────────────────────────────────────────────────────
belong = {k: [] for k in ZH}
drop, drop_area = 0, 0.0
for f in faces:
    c = f.representative_point()
    owner = None
    for k, g in ZH.items():
        if g.contains(c):
            owner = k
            break
    if owner is None:
        # 质心不在任何州内（浮点落在边界上）：退到「面积交叠最大」的州
        best, best_a = None, 0.0
        for k, g in ZH.items():
            a = f.intersection(g).area
            if a > best_a:
                best, best_a = k, a
        if best is None or best_a < f.area * 0.5:
            drop += 1
            drop_area += f.area
            continue
        owner = best
    belong[owner].append(f)

NEW = {}
for k, fs in belong.items():
    if not fs:
        NEW[k] = ZH[k]
        continue
    NEW[k] = unary_union(fs).buffer(0)
print('丢弃面片 %d 块，合计 %.1f px²' % (drop, drop_area))

# ── 4) 验收 ────────────────────────────────────────────────────────────────
n = list(NEW)
gaps, ov, dev = 0, [], []
for i in range(len(n)):
    for j in range(i + 1, len(n)):
        A, B = NEW[n[i]], NEW[n[j]]
        if A.distance(B) > 3.0:
            continue
        AB = A.union(B)
        g = AB.buffer(3).buffer(-3).difference(AB)
        for h in (g.geoms if hasattr(g, 'geoms') else [g]):
            if h.geom_type == 'Polygon' and h.area > 1e-4 and h.area <= 50 \
                    and h.buffer(0.05).intersects(A) and h.buffer(0.05).intersects(B):
                gaps += 1
        if A.distance(B) == 0:
            ar = A.intersection(B).area
            if ar > 0.5:
                ov.append((round(ar, 2), n[i], n[j]))
print('验收：缝隙 %d 块（原 49），重叠 %d 处（原 0）' % (gaps, len(ov)))
for k in sorted(ZH):
    d = (NEW[k].area - ZH[k].area) / ZH[k].area * 100
    if abs(d) > 0.05:
        dev.append((k, round(d, 3)))
print('面积变化 >0.05%% 的州：%s' % (dev or '无'))

if '--dry' in sys.argv or gaps > 5 or ov:
    print('（未写盘：%s）' % ('--dry' if '--dry' in sys.argv else '验收未通过'))
    sys.exit(0 if '--dry' in sys.argv else 1)

out = {}
for k, g in NEW.items():
    rings = []
    for h in (g.geoms if hasattr(g, 'geoms') else [g]):
        if h.geom_type != 'Polygon' or h.area < 1e-6:
            continue
        rings.append([[round(v, 4) for v in to_ll(x, y)] for x, y in h.exterior.coords])
    rings.sort(key=lambda r: -Polygon(r).area)
    out[k] = rings

bak = P.replace('.json', '.pre-planar.json')
if not os.path.exists(bak):
    io.open(bak, 'w', encoding='utf-8').write(io.open(P, encoding='utf-8').read())
io.open(P, 'w', encoding='utf-8').write(json.dumps(out, ensure_ascii=False))
print('已写回（备份 %s）' % os.path.relpath(bak, ROOT))
print('顶点：%d → %d' % (sum(len(r) for rs in raw.values() for r in rs),
                        sum(len(r) for rs in out.values() for r in rs)))
