#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""州界吸附：消除相邻州界之间的发丝缝（build/zhoupoly_refit.json）。

问题：refit 阶段只把「海岸段」的顶点重绘到海岸线上，内陆段的顶点是各州
      独立 Voronoi 生成的——两州的公共边在顶点级并不严格重合，于是留下
      一条条零点几像素宽的缝隙。实测 28 对相邻州全部有缝，合计 41.1 px²
      （占州域总面积 0.0034%），最大单块宽 1.15 px。
      校验工具 `audit_map.py` 的「州与州之间无缝隙」因此不通过。

做法（不改动州界形状，只补缝）：
  1. 对每个缝隙块，找出「同时贴住」的两个州（贴 ≥2 个州也照此处理）；
  2. 把它并入「到该块最近」的那个州——即把公共边推到两侧州界的中间线；
  3. 若缝隙块恰好还压在别的州面上（重叠），先从该州扣掉，保证互不重叠。

约束：
  · 只处理「两块之间」的缝（同时贴 A、B）：凹角、海湾开敞处不动；
  · 单块面积上限 50 px²，超过的不动（那种是真的没画，不是缝）；
  · 处理后重算：缝隙应降到 0，且州界仍两两不重叠。

用法：python3 scripts/snap_zhoupoly.py [--dry]
"""
import json, io, os, sys

from shapely.geometry import Polygon
from shapely.ops import unary_union

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, 'build', 'zhoupoly_refit.json')

# 投影（与 build.py / build_junpoly.py 同源）：经纬 ↔ 像素
AX, BX, AY, BY = 39.5608, -3711.03, -46.1517, 2030.70


def to_px(lng, lat):
    return (AX * lng + BX, AY * lat + BY)


def to_ll(x, y):
    return ((x - BX) / AX, (y - BY) / AY)


raw = json.load(io.open(P, encoding='utf-8'))
LL = {k: [list(map(tuple, r)) for r in rings] for k, rings in raw.items()}
ZH = {}                                    # 像素空间（用于几何运算）
for k, rings in LL.items():
    ps = []
    for r in rings:
        if len(r) < 3:
            continue
        p = Polygon([to_px(*c) for c in r])
        if not p.is_valid:
            p = p.buffer(0)
        ps.append(p)
    ZH[k] = unary_union(ps)


def gaps_between(A, B, D=3.0):
    """A、B 之间的窄缝块（同时贴住两者）。"""
    AB = A.union(B)
    g = AB.buffer(D).buffer(-D).difference(AB)
    out = []
    for h in (g.geoms if hasattr(g, 'geoms') else [g]):
        if h.geom_type != 'Polygon' or h.area <= 1e-4 or h.area > 50:
            continue
        hb = h.buffer(0.05)
        if hb.intersects(A) and hb.intersects(B):
            out.append(h)
    return out


def measure(Z, verbose=False):
    n = list(Z)
    tot, cnt, maxw = 0.0, 0, 0.0
    for i in range(len(n)):
        for j in range(i + 1, len(n)):
            if Z[n[i]].distance(Z[n[j]]) > 3.0:
                continue
            for h in gaps_between(Z[n[i]], Z[n[j]]):
                tot += h.area
                cnt += 1
                maxw = max(maxw, 4 * h.area / max(h.length, 1e-9))
                if verbose:
                    c = h.centroid
                    print('   %-4s×%-4s %6.2f px²  at %s'
                          % (n[i], n[j], h.area,
                             tuple(round(v, 2) for v in to_ll(c.x, c.y))))
    return cnt, tot, maxw


print('吸附前：')
c0, a0, w0 = measure(ZH)
print('  缝隙 %d 块，合计 %.1f px²，最大宽 %.2f px' % (c0, a0, w0))

if '--dry' in sys.argv:
    print('（--dry：不写盘）')
    sys.exit(0)

n = list(ZH)
FILL = {k: [] for k in n}
for i in range(len(n)):
    for j in range(i + 1, len(n)):
        A, B = ZH[n[i]], ZH[n[j]]
        if A.distance(B) > 3.0:
            continue
        for h in gaps_between(A, B):
            da, db = h.distance(A), h.distance(B)
            # 缝隙中线归属：距离相同则判给面积大的州（视觉上更稳定）
            win = n[i] if (da < db or (da == db and A.area >= B.area)) else n[j]
            FILL[win].append(h)

_fill_n, _fill_a = 0, 0.0
for k, hs in FILL.items():
    if not hs:
        continue
    u = unary_union(hs)
    # 从别的州里扣掉（极少见，防御性）
    for other in n:
        if other == k:
            continue
        if ZH[other].intersects(u):
            ZH[other] = ZH[other].difference(u).buffer(0)
    ZH[k] = ZH[k].union(u).buffer(0)
    _fill_n += len(hs)
    _fill_a += u.area
print('补缝：%d 块，合计 %.2f px²' % (_fill_n, _fill_a))

print('吸附后：')
c1, a1, w1 = measure(ZH)
print('  缝隙 %d 块，合计 %.1f px²，最大宽 %.2f px' % (c1, a1, w1))

# 终段修剪：补缝 + buffer(0) 修复可能在个别州对上留下 1~3 px² 的发丝重叠。
# 每对重叠从「面积较小」的州一侧切掉（difference 是精确布尔运算，不再 buffer，
# 避免再次引入形变）。迭代至收敛（最多 4 轮）。
for _t in range(4):
    n = list(ZH)
    moved = 0
    for i in range(len(n)):
        for j in range(i + 1, len(n)):
            A, B = ZH[n[i]], ZH[n[j]]
            if A.distance(B) > 0:
                continue
            ov = A.intersection(B)
            if ov.is_empty or ov.area <= 0.5:
                continue
            loser = n[j] if A.area >= B.area else n[i]
            ZH[loser] = ZH[loser].difference(ov)      # 不 buffer(0)
            moved += 1
    print('  修剪重叠：%d 处' % moved)
    if not moved:
        break

# 重叠自检
n = list(ZH)
ov = []
for i in range(len(n)):
    for j in range(i + 1, len(n)):
        A, B = ZH[n[i]], ZH[n[j]]
        if A.distance(B) > 0:
            continue
        ar = A.intersection(B).area
        if ar > 0.5:
            ov.append((round(ar, 2), n[i], n[j]))
print('  州界重叠 %d 处 %s' % (len(ov), '' if not ov else str(sorted(ov, reverse=True)[:5])))

# ── 写回（经纬，保留 4 位小数 ≈ 11 m，与 refit 精度一致）────────────────────
out = {}
for k, g in ZH.items():
    rings = []
    for h in (g.geoms if hasattr(g, 'geoms') else [g]):
        if h.geom_type != 'Polygon' or h.area < 1e-6:
            continue
        r = [[round(v, 4) for v in to_ll(x, y)] for x, y in h.exterior.coords]
        rings.append(r)
    rings.sort(key=lambda r: -Polygon(r).area)
    out[k] = rings

bak = P.replace('.json', '.pre-snap.json')
if not os.path.exists(bak):
    io.open(bak, 'w', encoding='utf-8').write(io.open(P, encoding='utf-8').read())
io.open(P, 'w', encoding='utf-8').write(json.dumps(out, ensure_ascii=False))
print('已写回 %s（备份 %s）' % (os.path.relpath(P, ROOT), os.path.relpath(bak, ROOT)))
print('顶点总数：%d → %d' % (sum(len(r) for rs in raw.values() for r in rs),
                            sum(len(r) for rs in out.values() for r in rs)))
