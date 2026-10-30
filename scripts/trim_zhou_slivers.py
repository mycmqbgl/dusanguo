#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""州界发丝重叠修剪（build/zhoupoly_refit.json）。

snap_zhoupoly 在像素空间补缝/修剪后写回经纬（4 位小数），三州交汇点与
共享边两侧各自取整会留下 0.0005~0.001°²（1~2 px²）的发丝重叠——
audit_map.py 的「州界两两不重叠」（>1 px² 计失败）刚好被卡住。
本脚本在经纬空间做最终修剪：每对重叠从面积较小的州一侧切掉，迭代至收敛。
"""
import json, io, os
from shapely.geometry import Polygon
from shapely.ops import unary_union

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, 'build', 'zhoupoly_refit.json')

raw = json.load(io.open(P, encoding='utf-8'))
Z = {k: unary_union([Polygon(r).buffer(0) for r in v]) for k, v in raw.items()}


def _slit(poly, eps=1e-4):
    """把带洞多边形展平成简单外环（洞经窄通道接到外环），洞真正被挖掉。"""
    import math
    from shapely.geometry import Point
    ext = list(poly.exterior.coords)
    if not poly.interiors:
        return ext
    for ring in poly.interiors:
        rc = list(ring.coords)
        hc = Polygon(rc).centroid
        best_q, best_d = 0, float('inf')
        for qi in range(len(ext) - 1):
            d = hc.distance(Point(ext[qi]))
            if d < best_d:
                best_d, best_q = d, qi
        anchor = Point(ext[best_q])
        vx, vy = anchor.x - hc.x, anchor.y - hc.y
        L = math.hypot(vx, vy)
        best_p, best_pd = 0, float('inf')
        for pi in range(len(rc) - 1):
            d = Point(rc[pi]).distance(anchor)
            if d < best_pd:
                best_pd, best_p = d, pi
        P = rc[best_p]
        if L < 1e-12:
            continue
        nx, ny = -vy / L, vx / L
        qa = (anchor.x + nx * eps / 2, anchor.y + ny * eps / 2)
        qb = (anchor.x - nx * eps / 2, anchor.y - ny * eps / 2)
        pa = (P[0] + nx * eps / 2, P[1] + ny * eps / 2)
        pb = (P[0] - nx * eps / 2, P[1] - ny * eps / 2)
        loop = rc[best_p:][::-1] + rc[:best_p + 1][::-1]
        loop = [tuple(c) for c in loop][1:]
        ext = (ext[:best_q + 1] + [qa] + [pa] + loop + [pb] + [qb] + ext[best_q + 1:])
    return ext


total = 0
for _t in range(6):
    n = list(Z)
    moved = 0
    for i in range(len(n)):
        for j in range(i + 1, len(n)):
            A, B = Z[n[i]], Z[n[j]]
            if A.distance(B) > 0:
                continue
            ov = A.intersection(B)
            if ov.is_empty or ov.area <= 1e-5:      # <0.02 px²，取整噪声
                continue
            loser = n[j] if A.area >= B.area else n[i]
            Z[loser] = Z[loser].difference(ov)
            moved += 1
            total += 1
    if not moved:
        break
print('修剪重叠 %d 处' % total)

# 写回：只写被修改的州，环取自修剪后的几何（保留 5 位小数）
out = {}
for k in raw:
    g = Z[k]
    rings = []
    for h in (g.geoms if hasattr(g, 'geoms') else [g]):
        if h.geom_type != 'Polygon' or h.area < 1e-6:
            continue
        q = Polygon(_slit(h))
        if not q.is_valid:
            q = q.buffer(0)
            if hasattr(q, 'geoms'):
                q = max(q.geoms, key=lambda g: g.area)
        rings.append([[round(x, 5), round(y, 5)] for x, y in q.exterior.coords])
    rings.sort(key=lambda r: -Polygon(r).area)
    out[k] = rings
json.dump(out, io.open(P, 'w', encoding='utf-8'), ensure_ascii=False)
print('已写回', P)
