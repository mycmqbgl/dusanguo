#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""沿海州界贴合（重构版）：只动海岸段，不动内陆段。

旧版问题（2026-10 校验发现）：
  `snap_to_coast` 之后统一 `simplify(0.05)`，而原始州界顶点间隔本身就是 0.167°——
  0.05° 容差会把整条内陆边界抹成十几段直线，豫州 92 点 → 23 点、面积 +90%，
  青州 +72%、冀州 +61%。州界一错，郡面/地区/点位全部连带错位。

新版策略：
  1. 完全不碰内陆段：只有「距海岸 < tol」的**连续区段**才重建；
  2. 海岸段沿海岸线加密采样（步长 0.06°），而非吸附孤立顶点后简化；
  3. 内陆段原样保留原始顶点；
  4. 面积守恒校验：|new/orig − 1| ≤ 0.12 才采纳，否则该州保留原始边界并告警。

输出 build/zhoupoly_refit.json（经纬度，顶点密度与原始一致）。
"""
import json, io, os, math
from shapely.geometry import LineString, Polygon, Point, MultiPolygon, MultiPoint, box
from shapely.ops import unary_union, linemerge, nearest_points

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
geo = json.load(io.open(os.path.join(ROOT, 'data/geo-real.json'), encoding='utf-8'))
LNG0, LNG1, LAT0, LAT1 = 97.0, 126.0, 18.0, 44.0
CANVAS = box(LNG0, LAT0, LNG1, LAT1)

segs = [LineString(s) for s in geo['coast'] if len(s) > 1]
merged = linemerge(unary_union(segs))
lines = list(merged.geoms) if hasattr(merged, 'geoms') else [merged]
lines.sort(key=lambda l: -l.length)
main = lines[0]
coast_all = unary_union(lines)
print('海岸主段 len=%.1f bounds=%s；合计 %d 段'
      % (main.length, [round(v) for v in main.bounds], len(lines)))

# 陆地面：海岸主段 + 西/北/南外框闭合（州界不得伸入海中）
coords = list(main.coords)
s0, s1 = coords[0], coords[-1]
ring = coords + [[LNG1, s1[1]], [LNG1, LAT1], [LNG0, LAT1], [LNG0, LAT0], [LNG0, s0[1]], s0]
land = Polygon(ring).buffer(0)
print('陆地面 %.1f°²' % land.area)


def resample_coast(a, b, step=0.06):
    """a→b 之间的海岸折线（沿海岸线走），按 step 加密。找不到连通路径时退回直线。"""
    # 用最近点参数化海岸线，取两点之间的那一段
    try:
        la = coast_all.project(Point(a))
        lb = coast_all.project(Point(b))
        s, e = (la, lb) if la <= lb else (lb, la)
        frac = coast_all.interpolate  # noqa
        n = max(2, int((e - s) / step) + 1)
        pts = [coast_all.interpolate(s + (e - s) * k / n) for k in range(n + 1)]
        pts = [[p.x, p.y] for p in pts]
        if la > lb:
            pts.reverse()
        return pts
    except Exception:
        return [list(a), list(b)]


def refit_one(pts, tol=0.12, step=0.06, cover=None):
    """对单个环：内陆顶点原样保留，海岸连续段沿海岸线重建。
    cover=海岸线数据的包裹框：只有落在框内的顶点才允许贴合。
    交州南界在 16.2°N，而海岸线数据只到 16.0°N，框外的"海岸"其实是史料边界
    （概化直线），不能被 land 面裁掉——否则交州南半部整片消失（-27%）。"""
    ring = [tuple(p) for p in pts]
    if ring[0] == ring[-1]:
        ring = ring[:-1]
    n = len(ring)
    near = [coast_all.distance(Point(p)) < tol and (cover is None or cover.contains(Point(p)))
            for p in ring]
    if not any(near):
        return [list(p) for p in ring], False
    out = []
    i = 0
    changed = False
    while i < n:
        if not near[i]:
            out.append(list(ring[i]))
            i += 1
            continue
        # 找一段连续海岸顶点 [i, j)
        j = i
        while j < n and near[j]:
            j += 1
        # 只有连续 ≥3 个顶点才算真正的海岸段。单个孤立顶点多半是"内陆边界恰好
        # 擦过某段海岸线"（如司隶西南角距杭州湾 0.3°），重采样会把它拽到海岸上，
        # 造成边界出现 21 个密集点 + 一大块面积错位（右扶风因此吞并整个西北）。
        if j - i >= 3:
            # 段内首末顶点吸附到海岸，中间沿海岸线重新采样
            qa = nearest_points(coast_all, Point(ring[i]))[0]
            qb = nearest_points(coast_all, Point(ring[min(j, n - 1)]))[0]
            seg = resample_coast((qa.x, qa.y), (qb.x, qb.y), step)
            out.extend(seg[:-1])
            changed = True
        else:
            q = nearest_points(coast_all, Point(ring[i]))[0]
            if math.hypot(q.x - ring[i][0], q.y - ring[i][1]) > 1e-6:
                changed = True
            out.append([q.x, q.y])
        i = j
    # 去重（吸附后可能出现重合点）
    ded = []
    for p in out:
        if ded and math.hypot(p[0] - ded[-1][0], p[1] - ded[-1][1]) < 1e-4:
            continue
        ded.append(p)
    if len(ded) > 2 and math.hypot(ded[0][0] - ded[-1][0], ded[0][1] - ded[-1][1]) < 1e-4:
        ded.pop()
    return ded, changed


out = {}
coast_box = box(*coast_all.bounds).buffer(0.05)
for z in geo['zhoupoly']:
    name = z['name']
    orig = Polygon([tuple(p) for p in z['pts']])
    if not orig.is_valid:
        orig = orig.buffer(0)
    origs = [g for g in (orig.geoms if hasattr(orig, 'geoms') else [orig])
             if g.geom_type == 'Polygon' and g.area > 0.05]
    origs.sort(key=lambda g: -g.area)

    fixed = []
    for g in origs:
        # 只在海岸数据覆盖范围内做陆地裁剪；框外部分是史料概化边界，保持原样
        clipped = g.intersection(land.union(coast_box)).intersection(CANVAS)
        if clipped.is_empty:
            continue
        subs = [q for q in (clipped.geoms if hasattr(clipped, 'geoms') else [clipped])
                if q.geom_type == 'Polygon' and q.area > 0.05]
        subs.sort(key=lambda q: -q.area)
        for q in subs:
            r, ch = refit_one(q.exterior.coords, cover=coast_box)
            p = Polygon(r)
            if not p.is_valid:
                p = p.buffer(0)
                if hasattr(p, 'geoms'):
                    gs = sorted([x for x in p.geoms if x.geom_type == 'Polygon'], key=lambda x: -x.area)
                    p = gs[0] if gs else None
            if p is None or p.is_empty:
                continue
            fixed.append([[round(x, 5), round(y, 5)] for x, y in p.exterior.coords])

    if not fixed:
        out[name] = [z['pts']]
        print('%-4s 无可用面，保留原界' % name)
        continue

    new_poly = unary_union([Polygon(r) for r in fixed])
    a0 = orig.intersection(CANVAS).area
    a1 = new_poly.intersection(CANVAS).area
    ratio = a1 / a0 if a0 else 0
    n0 = len(z['pts'])
    n1 = sum(len(r) for r in fixed)
    if 0.88 <= ratio <= 1.12 and n1 >= n0 * 0.7:
        out[name] = fixed
        print('%-4s %3d点 → %3d点  面积 %6.2f → %6.2f (%+.1f%%)  贴合'
              % (name, n0, n1, a0, a1, 100 * (ratio - 1)))
    else:
        out[name] = [z['pts']]
        print('%-4s ⚠ 面积 %+.1f%% / 点数 %d→%d 偏差过大，保留原界' % (name, 100 * (ratio - 1), n0, n1))

json.dump(out, io.open(os.path.join(ROOT, 'build/zhoupoly_refit.json'), 'w', encoding='utf-8'),
          ensure_ascii=False)
print('\n— 第一轮完成，进入缝隙填补/重叠消解 —')

# ── 第二轮：缝隙填补 + 重叠消解（迭代 3 轮收敛） ────────────────────────────
# 原始 zhoupoly 是各州独立概化的，相邻州之间本来就留 0.5~2° 的缓冲缝；
# 贴海之后的采样点又会引入新的小缝。做法与 build_junpoly 一致：
#   · 缝隙块 → 按最近州边界（Voronoi 式）分给相邻州，只填「被 ≥2 州包围」的缝；
#   · 重叠块 → 按两侧州界位置对半分（中轴切开），各让一半。
from shapely.ops import voronoi_diagram

def parts_of(g):
    return [q for q in (g.geoms if hasattr(g, 'geoms') else [g]) if q.geom_type == 'Polygon' and not q.is_empty]


def thin(ring, step=0.04):
    """抽稀：缝隙填补会在主环上留下成串 0.006° 的密集点（微锯齿），
    只保留与上一个保留点距离 ≥ step 的顶点，避免前端画出毛刺。"""
    if len(ring) < 4:
        return ring
    out = [ring[0]]
    for p in ring[1:-1]:
        if math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) >= step:
            out.append(p)
    # 末点必须与首点不同（闭合环隐式闭合）
    if math.hypot(out[-1][0] - ring[0][0], out[-1][1] - ring[0][1]) < step and len(out) > 3:
        out.pop()
    return out


def main_ring(g):
    """取最大 part 的外环（并集常返回 MultiPolygon）。"""
    ps = parts_of(g if g.geom_type != 'Polygon' else g)
    if not ps:
        return None
    ps.sort(key=lambda q: -q.area)
    return [[round(x, 5), round(y, 5)] for x, y in ps[0].exterior.coords]

for rnd in range(6):
    P = {k: unary_union([Polygon(r).buffer(0) for r in rs]) for k, rs in out.items()}
    U = unary_union(list(P.values()))
    D = 0.06
    gap = U.buffer(D).buffer(-D).difference(U)
    sealed = 0
    for g in parts_of(gap):
        if g.area < 1e-6:
            continue
        near = [k for k, p in P.items() if p.distance(g) < 1e-6]
        if len(near) < 2:                      # 单州旁的空地（海岸外/沙漠戈壁）不填
            continue
        # 分片锚点必须用「离缝隙最近的州界点」，不能用州整体代表点：
        # 司隶代表点在 (110,35)、荆州在 (111,28)，中垂线会偏离缝隙几十度，
        # 导致整块缝隙全归一方（另一方的 piece 面积为 0）。
        from shapely.ops import nearest_points as _np
        anchors = {}
        for n in near:
            anchors[n] = _np(P[n], g)[0]
        reps = MultiPoint(list(anchors.values()))
        cells = voronoi_diagram(reps, envelope=g.envelope.buffer(0.5))
        cells = list(cells.geoms) if hasattr(cells, 'geoms') else [cells]
        for n in near:
            rp = anchors[n]
            cell = min(cells, key=lambda c: c.distance(rp))
            piece = g.intersection(cell)
            if piece.is_empty or piece.area < 1e-9:
                continue
            rs = out[n]
            big = max(range(len(rs)), key=lambda i: Polygon(rs[i]).buffer(0).area)
            mn = main_ring(Polygon(rs[big]).buffer(0).union(piece).buffer(0))
            if mn:
                out[n][big] = mn
            sealed += 1
    # 重叠消解：按两州 representative_point 连线中轴切
    fixed_ov = 0
    names = list(out)
    for i in range(len(names)):
        for k in range(i + 1, len(names)):
            a, b = names[i], names[k]
            for ia, ra in enumerate(out[a]):
                for ib, rb in enumerate(out[b]):
                    pa, pb = Polygon(ra).buffer(0), Polygon(rb).buffer(0)
                    inter = pa.intersection(pb)
                    if inter.area < 1e-4:
                        continue
                    # 中轴：连接两中心点，过交点质心的垂直平分线
                    ca = pa.representative_point(); cb = pb.representative_point()
                    mx, my = (ca.x + cb.x) / 2, (ca.y + cb.y) / 2
                    dx, dy = cb.x - ca.x, cb.y - ca.y
                    L = math.hypot(dx, dy) or 1.0
                    nx, ny = dx / L, dy / L
                    R = 20.0
                    line = [(mx - ny * R, my + nx * R), (mx + ny * R, my - nx * R)]
                    half_a = Polygon(line + [(mx - ny * R - nx * R, my + nx * R - ny * R),
                                             (mx + ny * R - nx * R, my - nx * R - ny * R)]).buffer(0)
                    # 简化：直接把重叠块按"离各自中心更近"分
                    mid = LineString([(mx - ny * R, my + nx * R), (mx + ny * R, my - nx * R)])
                    from shapely.ops import split as _split
                    pa2 = pa.difference(inter).union(inter.intersection(
                        Polygon([(mx - ny * R, my + nx * R), (mx + ny * R, my - nx * R),
                                 (mx + ny * R - nx * R, my - nx * R - ny * R),
                                 (mx - ny * R - nx * R, my + nx * R - ny * R)])))
                    pb2 = pb.difference(inter).union(inter.difference(pa2))
                    ma, mb = main_ring(pa2), main_ring(pb2)
                    if ma:
                        out[a][ia] = ma
                    if mb:
                        out[b][ib] = mb
                    fixed_ov += 1
    print('  第%d轮：填补缝隙 %d 块，消解重叠 %d 处' % (rnd + 1, sealed, fixed_ov))
    if sealed == 0 and fixed_ov == 0:
        break

# 最终统一抽稀（迭代中抽稀会改变形状→产生新缝隙→不收敛）
n_before = sum(len(r) for v in out.values() for r in v)
for k in out:
    out[k] = [thin(r) for r in out[k]]
n_after = sum(len(r) for v in out.values() for r in v)
print('最终抽稀：%d → %d 点' % (n_before, n_after))

json.dump(out, io.open(os.path.join(ROOT, 'build/zhoupoly_refit.json'), 'w', encoding='utf-8'),
          ensure_ascii=False)

# ── 自检 ───────────────────────────────────────────────────────────────────
P = {k: unary_union([Polygon(r).buffer(0) for r in rs]) for k, rs in out.items()}
U = unary_union(list(P.values()))
D = 0.06
gap = U.buffer(D).buffer(-D).difference(U)
gs = parts_of(gap)
print('\n州间缝隙：%d 块，合计 %.4f°²（最大 %.4f°²）'
      % (len(gs), sum(g.area for g in gs), max([g.area for g in gs] or [0])))
ov = []
names = list(out)
for i in range(len(names)):
    for k in range(i + 1, len(names)):
        a, b = names[i], names[k]
        ar = P[a].intersection(P[b]).area
        if ar > 0.005:
            ov.append((a, b, round(ar, 3)))
print('州间重叠：%d 处（>0.005°²）%s' % (len(ov), '' if not ov else str(ov[:6])))
print('顶点数：' + ' '.join('%s=%d' % (k, sum(len(r) for r in v)) for k, v in out.items()))
print('完成 → build/zhoupoly_refit.json')
