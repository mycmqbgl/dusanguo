#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""郡面发丝重叠修剪（build/junpoly.json）。

build_junpoly 的「像素去重叠」在内存里是严格互斥的，但输出经 _slit 切缝展平后，
前端/审计按 Polygon(pts).buffer(0) 重建几何——零宽切缝若被 buffer(0) 修复成实心，
被挖掉的部分会原样回来（实测九真×交趾 1.74 px²）。本脚本在输出文件上做最终修剪：
每对 >0.5 px² 的重叠从面积较小的一方切掉，洞用切缝展平（eps 放大到 0.05px 保证
buffer(0) 不回填）。
"""
import json, io, math, os
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, 'build', 'junpoly.json')


def _slit(poly, eps=0.05):
    ext = list(poly.exterior.coords)
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
        Pt = rc[best_p]
        if L < 1e-9:
            continue
        nx, ny = -vy / L, vx / L
        qa = (anchor.x + nx * eps / 2, anchor.y + ny * eps / 2)
        qb = (anchor.x - nx * eps / 2, anchor.y - ny * eps / 2)
        pa = (Pt[0] + nx * eps / 2, Pt[1] + ny * eps / 2)
        pb = (Pt[0] - nx * eps / 2, Pt[1] - ny * eps / 2)
        loop = rc[best_p:][::-1] + rc[:best_p + 1][::-1]
        loop = [tuple(c) for c in loop][1:]
        ext = ext[:best_q + 1] + [qa] + [pa] + loop + [pb] + [qb] + ext[best_q + 1:]
    q = Polygon(ext)
    if not q.is_valid:
        q2 = q.buffer(0)
        if not q2.is_empty:
            q2 = max(q2.geoms, key=lambda g: g.area) if hasattr(q2, 'geoms') else q2
            ext = list(q2.exterior.coords)
    return ext


raw = json.load(io.open(P, encoding='utf-8'))
G = {x['name']: unary_union([Polygon(x['pts']).buffer(0)] +
                            [Polygon(r).buffer(0) for r in x.get('extra') or []]).buffer(0)
     for x in raw}

total = 0
for _t in range(5):
    nm = list(G)
    moved = 0
    for i in range(len(nm)):
        for j in range(i + 1, len(nm)):
            A, B = G[nm[i]], G[nm[j]]
            if A.distance(B) > 0:
                continue
            ov = A.intersection(B)
            if ov.is_empty or ov.area <= 0.5:
                continue
            loser = nm[j] if A.area >= B.area else nm[i]
            G[loser] = G[loser].difference(ov)
            moved += 1
            total += 1
    if not moved:
        break
print('修剪郡面重叠 %d 处' % total)

for x in raw:
    g = G[x['name']]
    parts = [h for h in (g.geoms if hasattr(g, 'geoms') else [g])
             if h.geom_type == 'Polygon' and h.area > 0.5]
    parts.sort(key=lambda h: (0 if h.contains(Point(x['seat'])) else 1, -h.area))
    if not parts:
        continue
    x['pts'] = [[c[0], c[1]] for c in _slit(parts[0])]
    x['extra'] = [[[c[0], c[1]] for c in _slit(pt)] for pt in parts[1:]]
    x['n'] = len(parts)

json.dump(raw, io.open(P, 'w', encoding='utf-8'), ensure_ascii=False)
print('已写回', P)
