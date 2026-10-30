#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成郡界多边形（画布像素坐标），供底图「郡界层」与地名页「郡高亮」使用。

思路：东汉无精确郡界矢量数据，但每个郡国都有治所（县点 t=都）。
以治所为站点做全平面 Voronoi 剖分（半平面裁剪实现），即「每块郡域 = 离该治所最近的区域」，
再与所属州界求交——这样郡界必然严格落在州界内、互不重叠、无缝隙，是可解释的近似而非随机膨胀。

★ 2026-10 校验修复（关键）：旧版**按州独立剖分**——荆州各郡只与荆州其他郡互裁、
  扬州各郡只与扬州其他郡互裁。于是相邻州的两个郡在州界重叠带里互不知情，
  各自按「最近治所」延伸 → 159 处两两重叠（临川×会稽 1227 px²、南海×合浦 1115 px² …）。
  旧版靠「每州外扩 55px 的楔形回填」把这件事遮住了，而那块回填又让郡面溢出州界 152%。
  现在改为**全部 124 个郡放在同一张平面里一次性剖分**，跨州郡对同样互裁，
  重叠从 159 处 / 38990 px² 降到 0。

坐标：全程在**经纬空间**计算（州界、县点同为经纬），输出时统一投影为像素。
输出 build/junpoly.json：[{name, zhou, seat:[x,y], pts:[[x,y]...], extra:[[...]], n}]
"""
import json, io, os, math, random, zlib
from collections import defaultdict

from shapely.geometry import Polygon, MultiPolygon, Point, LineString, box as sbox
from shapely.ops import unary_union, nearest_points

sys_path_fix = os.path.dirname(os.path.abspath(__file__))
if sys_path_fix not in __import__('sys').path:
    __import__('sys').path.insert(0, sys_path_fix)
from geo_const import OFFCANVAS_JUN, EXTRA_JUN_LL  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
geo = json.load(open(os.path.join(ROOT, 'data/geo-real.json'), encoding='utf-8'))
county = json.load(open(os.path.join(ROOT, 'data/counties-han.json'), encoding='utf-8'))['counties']
places = json.load(open(os.path.join(ROOT, 'build/places.json'), encoding='utf-8'))

# ── 由已知精确点最小二乘拟合线性投影（与 build.py 同源） ───────────────────
import numpy as np
_pts = [(p['lng'], p['lat'], p['pixel_x'], p['pixel_y']) for p in places
        if p.get('pixel_x') is not None and p.get('coord_precision') == '精确']
_A = np.array([[_p[0], 1] for _p in _pts]); _BX = np.array([_p[2] for _p in _pts])
AX, BX = np.linalg.lstsq(_A, _BX, rcond=None)[0]
_A2 = np.array([[_p[1], 1] for _p in _pts]); _BY = np.array([_p[3] for _p in _pts])
AY, BY = np.linalg.lstsq(_A2, _BY, rcond=None)[0]
print('投影拟合：x=%.4f*lng%+.2f  y=%.4f*lat%+.2f' % (AX, BX, AY, BY))


def prj(lng, lat):
    return (round(AX * lng + BX, 1), round(AY * lat + BY, 1))


# ── 平分线自然化：把直线平分线换成确定性噪声弯曲的折线 ──────────────────────
# 同一对郡 (a,b) 的两侧裁剪共用同一条折线（key=排序后的郡名对），因此共享边严丝合缝、
# 不会重叠。噪声用 3 个不同波长正弦叠加（随机相位由 seed 决定），看起来像手绘界线。
def _bisect_polyline(m, n, u, key, R=50.0, step=0.5, L=10.0):
    """沿平分线方向 u 采样 t∈[-R,R]，沿法向 n 偏移 f(t)，返回折线点列。
    f(t)=Σ amp_i*sin(w_i t+φ_i)。振幅按两站点距 L 自适应缩放（min(1, L/3)）——
    密集州相邻治所仅 0.5°，固定振幅会把界线摆过站点本身。"""
    rng = random.Random(zlib.crc32(key.encode('utf-8')))   # crc32：跨进程确定性
    ph = [rng.uniform(0, 2 * math.pi) for _ in range(3)]
    sc = min(1.0, L / 3.0)
    w = [2 * math.pi / 7.0, 2 * math.pi / 2.8, 2 * math.pi / 1.1]   # 波长 7 / 2.8 / 1.1°
    amp = [0.20 * sc, 0.11 * sc, 0.05 * sc]

    def f(t):
        return sum(a * math.sin(wi * t + pi_) for a, wi, pi_ in zip(amp, w, ph))

    pts = []
    nseg = max(2, int(2 * R / step))
    for k in range(nseg + 1):
        t = -R + 2 * R * k / nseg
        d = f(t)
        pts.append((m[0] + u[0] * t + n[0] * d, m[1] + u[1] * t + n[1] * d))
    return pts


def _side_polygon(pts, m, n, u, T, sign=1.0, R=0.0):
    """把折线闭合成「sign 侧」的多边形：折线 + 两端各自沿法向推到「n 坐标 = sign*T」的齐平线。

    ★ 封口方式决定「同一对郡的两个半平面是否严格互补」——这是郡界不重叠/无缝隙的根本。
      历史上踩过三个坑：
        (a) 折线沿切向多伸 1.5° + 两个远端角点 → 延伸段跨过相邻郡折线的拐点，
            两侧半平面既留缝又局部交叉（全平面剖分后仍有 134 处重叠、州内覆盖率 0.56~0.95）；
        (b) 两端各沿法向平移固定 F=80° → 两条封口边不平行，在远端交叉；
        (c) 折线沿 u 只铺到 ±R，够不到裁切区的远端 → 半平面覆盖不全（sum/ENV 仅 0.64）。
      现在：折线铺到 t∈[-R,R]（R 由调用方按裁切区外包算足），两端点各自**沿法向推到同一个
      齐平线**（n 方向坐标 = sign*T），两条封口边严格平行、不交叉。实测 A∩B=0、A∪B 盖满裁切区。"""

    def to_far(p):
        cur = (p[0] - m[0]) * n[0] + (p[1] - m[1]) * n[1]
        delta = sign * T - cur
        return (p[0] + n[0] * delta, p[1] + n[1] * delta)

    ring = list(pts) + [to_far(pts[-1]), to_far(pts[0])]
    p = Polygon(ring)
    if not p.is_valid:
        p = p.buffer(0)
    return p


def clip_side(poly, side_poly):
    if poly.is_empty:
        return poly
    out = poly.intersection(side_poly)
    if out.is_empty:
        return Polygon()
    if out.geom_type not in ('Polygon', 'MultiPolygon'):
        gs = [g for g in getattr(out, 'geoms', []) if g.geom_type == 'Polygon']
        return max(gs, key=lambda g: g.area) if gs else Polygon()
    return out


# ── 弯曲半平面裁剪：保留「到 a 比到 b 更近」的一侧，边界为噪声折线 ────────────
def _poly_parts(geom):
    return [g for g in (geom.geoms if hasattr(geom, 'geoms') else [geom])
            if g.geom_type == 'Polygon' and g.area > 1e-9]


def _assign_by_nearest(region, sites, step=0.06):
    """把 region 按「最近站点」切成若干块，返回 [(站点名, 多边形)]。

    对 region 外包按 step 撒格点，逐点找最近站点（KD 树），再按站点把格点连成方块求并，
    最后与 region 求交。分辨率 0.06°（≈2.4 px），对填缝足够。"""
    if region.is_empty:
        return []
    names = list(sites)
    if len(names) == 1:
        return [(names[0], region)]
    from scipy.spatial import cKDTree
    arr = np.array([[sites[a].x, sites[a].y] for a in names])
    kd = cKDTree(arr)

    minx, miny, maxx, maxy = region.bounds
    nx = max(1, int(math.ceil((maxx - minx) / step)))
    ny = max(1, int(math.ceil((maxy - miny) / step)))
    boxes = defaultdict(list)
    for ix in range(nx):
        x0 = minx + ix * step
        cx = x0 + step / 2
        for iy in range(ny):
            y0 = miny + iy * step
            cy = y0 + step / 2
            if not region.contains(Point(cx, cy)):
                continue
            _, i = kd.query([cx, cy])
            boxes[names[i]].append(sbox(x0, y0, x0 + step, y0 + step))
    out = []
    for a, bs in boxes.items():
        u = unary_union(bs).intersection(region)
        for h in _poly_parts(u):
            out.append((a, h))
    return out


def clip_halfplane(poly, a, b, aname='', bname='', region=None):
    """保留「到 a 比到 b 更近」的一侧；边界为 (aname,bname) 决定的噪声折线。

    ★ 折线必须由「规范方向」生成：早期版本直接按 (a→b) 的向量建折线，
      于是 a 侧调用用 f(t)、b 侧调用（b→a，t 反向）用 f(-t)，
      两条折线在噪声相位上不对称 → 两侧半平面各自偏离中垂线，A∩B≠0（实测 3.27°²）。
      现在统一按「郡名排序靠前者 → 靠后者」的规范轴建折线，再按实际需要的方向取半平面，
      两侧严格共用同一条边界，A∩B=0、A∪B 盖满裁切区。

    region：裁切区外包。折线沿 u 铺到覆盖 region 在 u 方向的全部投影（R），
    封口推到覆盖 region 在 n 方向的最大投影（T），保证半平面盖满裁切区。"""
    if poly.is_empty:
        return poly
    # 规范方向：郡名排序靠前 → 靠后
    if aname <= bname:
        p, q, flip = a, b, False
    else:
        p, q, flip = b, a, True

    ax, ay = p.x, p.y
    bx, by = q.x, q.y
    dx, dy = bx - ax, by - ay
    L = math.hypot(dx, dy)
    if L < 1e-12:
        return poly
    mx, my = (ax + bx) / 2.0, (ay + by) / 2.0
    nx, ny = dx / L, dy / L
    ux, uy = -ny, nx                          # 沿平分线方向

    if region is not None:
        rx0, ry0, rx1, ry1 = region.bounds
        corners = [(rx0, ry0), (rx1, ry0), (rx1, ry1), (rx0, ry1)]
    else:
        corners = [(mx - 60, my - 60), (mx + 60, my - 60),
                   (mx + 60, my + 60), (mx - 60, my + 60)]
    pu = [(c[0] - mx) * ux + (c[1] - my) * uy for c in corners]
    pn = [(c[0] - mx) * nx + (c[1] - my) * ny for c in corners]
    R = min(80.0, max(max(abs(v) for v in pu) + 3.0, L / 2 + 8, 22))
    T = min(80.0, max(abs(v) for v in pn) + 3.0)

    line = _bisect_polyline((mx, my), (nx, ny), (ux, uy),
                            '|'.join(sorted([aname, bname])), R=R, step=0.35, L=L)
    # 规范轴下 p 在 n 的负侧 → sign=-1；调用方要的是 q 侧则取 +1
    sign = 1.0 if flip else -1.0
    side = _side_polygon(line, (mx, my), (nx, ny), (ux, uy), T=T, sign=sign)
    return clip_side(poly, side)


# ── 读州界（经纬） ─────────────────────────────────────────────────────────
# 必须用 refit 后的州界（build/zhoupoly_refit.json），否则郡面按「旧州界」裁剪，
# 与前端实际渲染的州界是两套轮廓 → 郡界并集与州界对不上（校验里表现为
# 州内覆盖率 0.56~0.93、郡面溢出 12%~54%）。
# refit 缺失时回退 geo-real.json，并在日志里明确告警。
_refit = os.path.join(ROOT, 'build', 'zhoupoly_refit.json')
zhou_poly = {}
if os.path.exists(_refit):
    _r = json.load(io.open(_refit, encoding='utf-8'))
    for name, rings in _r.items():
        gs = []
        for r in rings:
            if len(r) < 3:
                continue
            p = Polygon([tuple(q) for q in r])
            if not p.is_valid:
                p = p.buffer(0)
            gs.extend([x for x in (p.geoms if hasattr(p, 'geoms') else [p])
                       if x.geom_type == 'Polygon' and not x.is_empty])
        if gs:
            zhou_poly[name] = unary_union(gs)
    print('州界来源：build/zhoupoly_refit.json（%d 州）' % len(zhou_poly))
else:
    print('! 缺 build/zhoupoly_refit.json，回退 geo-real.json 原始州界（郡界将与渲染州界错位）')
    for z in geo['zhoupoly']:
        poly = Polygon([tuple(p) for p in z['pts']])
        if not poly.is_valid:
            poly = poly.buffer(0)
        zhou_poly[z['name']] = poly
print('州界：', {k: round(v.area, 2) for k, v in list(zhou_poly.items())[:4]}, '...')

# ── 州间楔形回填：已废弃（2026-10 校验） ───────────────────────────────────
# 原实现给每州向外扩 55px 去填州界之间的真空楔形。但前端渲染的是
# build/zhoupoly_refit.json，回填后的 zhou_poly 只用于郡面裁剪——
# 两套州界不一致 → 郡面整体外溢（兖州 152%、豫州 69%），"郡界并集≈州界"永不成立。
# 现在 refit 已在源头把州界缝隙填到 0.05°² 以下、重叠归零，回填不再需要。
print('州间楔形回填：已由 refit 在源头解决，跳过')

# ── 站点：郡治（t=都）优先，缺失取郡内县点均值 ──────────────────────────────
seat = {}
for c in county:
    if c.get('t') == '都':
        seat.setdefault(c['a'], (c['lng'], c['lat']))
agg = defaultdict(list)
for c in county:
    agg[c['a']].append((c['lng'], c['lat']))
for a, ps in agg.items():
    seat.setdefault(a, (sum(p[0] for p in ps) / len(ps), sum(p[1] for p in ps) / len(ps)))

by_zhou = defaultdict(list)
for c in county:
    by_zhou[c['p']].append(c['a'])
for z in by_zhou:
    by_zhou[z] = sorted(set(by_zhou[z]))

# 汉末三国新置/析置郡（不在东汉永和底表）：补站点，使其也能参与剖分。
# 治所坐标为郡治县城的经纬（精确级），点击郡名高亮时的镜头落点。
# ★ 名单与 build_place_hierarchy.py 共用同一份，见 scripts/geo_const.py——
#   两边各写一份已经漂过一次（hierarchy 那份多出广汉郡）。
EXTRA_JUN = list(EXTRA_JUN_LL)
for jn, zt, ll in EXTRA_JUN:
    if zt in zhou_poly:
        seat[jn] = ll
        by_zhou[zt] = sorted(set(by_zhou[zt]) | {jn})

# ★ 2026-10 定案：敦煌郡全篇演义无涉，郡面远超画布西缘（lng<97 的 Voronoi 外溢），
#   整体移出剖分；其余郡越出画布的部分（酒泉郡西缘等）由下方画布裁剪截除。
#   名单与 build_power.py / audit_power.py 共用，见 scripts/geo_const.py。
DROP_JUN = set(OFFCANVAS_JUN)
for jn in DROP_JUN:
    seat.pop(jn, None)
    for z in by_zhou:
        if jn in by_zhou[z]:
            by_zhou[z].remove(jn)

# ══════════════════════════════════════════════════════════════════════════
# 全平面一次性剖分（跨州郡对同样互裁）
# ══════════════════════════════════════════════════════════════════════════
# 站点全集：所有有州归属的郡
JUN2Z = {}
for z, js in by_zhou.items():
    for j in js:
        if j in seat:
            JUN2Z[j] = z
ALL = sorted(JUN2Z)
print('参与剖分的郡：%d 个（覆盖 %d 州）' % (len(ALL), len(by_zhou)))

# 州界是概化多边形，部分治所会落在界外（frontier / 海岸 / 界线偏移）。
# 不「传送」站点（会使郡面错位）：沿站点到州界投影连线加一条走廊 + 站点圆斑，
# 使 cell 围绕真实治所生成。走廊半宽 0.5°。
sit = {}
zone = dict(zhou_poly)                     # zone[z] = 该州参与剖分的区域（可能带走廊）
move_log = []
for a in ALL:
    pt = Point(seat[a])
    z = JUN2Z[a]
    zp = zone[z]
    if not zp.contains(pt):
        q = nearest_points(zp, pt)[0]
        d = q.distance(pt)
        # 走廊半宽按越界距离自适应：越界 >0.6° 的（如新城郡 0.75°）加宽到 0.9°
        hw = 0.9 if d > 0.6 else 0.5
        zone[z] = zp.union(LineString([q, pt]).buffer(hw))
        move_log.append((a, z, round(d, 2), hw))
    sit[a] = pt
if move_log:
    print('治所越界需加走廊：%d 个 → %s' % (len(move_log), move_log))

# 全平面外包（所有州 zone 的并集 + pad）
UZ = unary_union(list(zone.values()))
minx, miny, maxx, maxy = UZ.bounds
PAD = 3.0
ENV = sbox(minx - PAD, miny - PAD, maxx + PAD, maxy + PAD)

cells = {}
for i, a in enumerate(ALL):
    pa = sit[a]
    cell = Polygon(ENV.exterior.coords)
    for j, b in enumerate(ALL):
        if i == j:
            continue
        cell = clip_halfplane(cell, pa, sit[b], aname=a, bname=b, region=ENV)
        if cell.is_empty:
            break
    if not cell.is_empty:
        cells[a] = cell
print('剖分完成：%d/%d 个 cell 非空' % (len(cells), len(ALL)))

# ── 缝隙回填：把每个州域内「无人认领」的部分分配给郡 ───────────────────────
# 半平面剖分是「每对郡各自切一刀」的迭代结果，三方交汇处必然残留细缝；
# 州域加了「治所走廊」之后，走廊末端也可能不在任何 cell 内。
#
# ★ 两个约束是互相矛盾的，必须先定优先级（2026-10 决策：**优先铺满州域**）：
#   · 按「全局最近治所」分 → 几何自然，但徐东、荆南这些「本州治所远、邻州治所近」
#     的地块会被邻州拿走，州内覆盖率永远上不去（徐州 0.68、荆州 0.79）；
#   · 按「本州最近郡」分 → 州域铺满，但可能与邻州 cell 冲突（那些 cell 早就伸过来了）。
#   采取「本州优先」：缝隙只在本州郡之间分配；随后的重叠清除里，
#   跨州冲突一律判给「地块所在州」的那一方（见下面的 _owner_by_zhou），
#   这样填进来的块不会再被清掉，也不会去抢别州的地。
def _owner_by_zhou(q, cand):
    """重叠块 q 的归属：只保留「与 q 所在州一致」的候选；否则退回最近治所。

    ★ 2026-10 修复：cell zone 不是互斥的——治所越界时会加「走廊」（蕲春郡 0.17°、
      新城郡 0.13°，宽 0.5°），走廊跨过州界，于是州界内侧一条 0.5° 宽的带子
      **同时属于两个州的 zone**（扬州∩荆州 0.54°²、益州∩荆州 0.55°²）。
      旧版用 `next((z for z in zone if ...))` 取首个命中州，而 dict 遍历序里
      扬州/益州排在荆州之前 → 落在重叠带里的地块一律判给邻州 →
      荆州 (115.08,30.02) 与 (111.02,32.12) 两处填充块被反复清掉，覆盖率卡在 0.949。
      现在：在**所有**命中州里挑与候选郡同属的那个（有多个命中州时优先「无走廊的真州域」），
      并列才退回最近治所。"""
    c = q.representative_point()
    hits = [z for z in zone if zone[z].contains(c)]
    if not hits:
        return min(cand, key=lambda a: c.distance(sit[a]))
    same = [a for a in cand if JUN2Z[a] in hits]
    if same:
        # 候选本就分别属于不同州时，优先判给「真州域」（未被走廊扩过）那一方
        real = [a for a in same if zhou_poly[JUN2Z[a]].contains(c)]
        pool = real or same
        return min(pool, key=lambda a: c.distance(sit[a]))
    pool = [a for a in cand if zhou_poly[JUN2Z[a]].contains(c)] or cand
    return min(pool, key=lambda a: c.distance(sit[a]))


filled_n = 0
filled_area = 0.0
for z, zp in zone.items():
    own = [a for a in cells if JUN2Z[a] == z]
    if not own:
        continue
    cu = unary_union([cells[a] for a in own])
    gap = zp.buffer(0).difference(cu)
    gs = [g for g in (gap.geoms if hasattr(gap, 'geoms') else [gap])
          if g.geom_type == 'Polygon' and g.area > 1e-7]
    if not gs:
        continue
    own_sit = {a: sit[a] for a in own}
    for g in gs:
        if g.area > 0.02:
            subs = _assign_by_nearest(g, own_sit)      # 本州最近治所
        else:
            c = g.representative_point()
            best = min(own, key=lambda a: c.distance(sit[a]))
            subs = [(best, g)]
        for a, h in subs:
            cells[a] = cells[a].union(h)
            filled_n += 1
            filled_area += h.area
print('缝隙回填：%d 块，合计 %.4f °²' % (filled_n, filled_area))

# ── 重叠清除：兜底（规范化后仍可能有极小块残留） ────────────────────────────
# 每对相交块，判给「治所更近」的一方；距离相同则判给郡名排序靠前者，保证确定性。
cut_n, cut_area = 0, 0.0
for _round in range(4):
    moved = False
    nm = list(cells)
    for i in range(len(nm)):
        for j in range(i + 1, len(nm)):
            A, B = nm[i], nm[j]
            if cells[A].distance(cells[B]) > 0:
                continue
            inter = cells[A].intersection(cells[B])
            parts = _poly_parts(inter)
            if not parts:
                continue
            for q in parts:
                if q.area < 1e-7:
                    continue
                win = _owner_by_zhou(q, (A, B))
                loser = B if win == A else A
                cells[loser] = cells[loser].buffer(0).difference(q).buffer(0)
                cut_n += 1
                cut_area += q.area
                moved = True
    if not moved:
        break
print('重叠清除：%d 块，合计 %.5f °²' % (cut_n, cut_area))

# ── 末道填缝：清完重叠后，每州域内仍可能有无人认领的细缝 ────────────────────
# 成因是「三方交汇点」——三个郡的半平面两两互补，但交点处必然留一个三角形小孔；
# 缝隙回填阶段这些小孔被填过，随后重叠清除又把填进来的部分按 q 切掉，
# 而 q 是「两郡共有块」，切掉后若第三者并不覆盖，就重新露出空白。
# 实测剩余量级很小（兖州 151 px²、豫州 606 px²、徐州 354 px²，最大单块 79 px²），
# 但用户要求「各郡之间没有间隙」，所以必须补齐。
# 这一步在输出之前执行，只在本州郡之间分配，不会引入新的跨州重叠，
# 且分配结果直接并进 cell，随后仍会被 clip 到 zone，不会溢出州界。
top_n, top_area = 0, 0.0
for z, zp in zone.items():
    own = [a for a in cells if JUN2Z[a] == z and not cells[a].is_empty]
    if not own:
        continue
    cu = unary_union([cells[a] for a in own])
    gap = zp.buffer(0).difference(cu)
    gs = [g for g in (gap.geoms if hasattr(gap, 'geoms') else [gap])
          if g.geom_type == 'Polygon' and g.area > 1e-9]
    if not gs:
        continue
    own_sit = {a: sit[a] for a in own}
    for g in gs:
        if g.area > 0.02:
            subs = _assign_by_nearest(g, own_sit)
        else:
            c = g.representative_point()
            subs = [(min(own, key=lambda a: c.distance(sit[a])), g)]
        for a, h in subs:
            # 并入前先从「其他有重叠的 cell」里扣掉 h——末道填缝发生在重叠清除之后，
            # 若只 union 不扣，h 会同时落在邻郡 cell 里 → 重叠暴涨（实测 39.8→1956 px²）。
            for b in list(cells):
                if b == a or cells[b].is_empty or cells[b].distance(h) > 0:
                    continue
                if cells[b].intersects(h):
                    cells[b] = cells[b].difference(h).buffer(0)
            cells[a] = cells[a].union(h)
            top_n += 1
            top_area += h.area
print('末道填缝：%d 块，合计 %.5f °²' % (top_n, top_area))

# ── 输出：cell ∩ 所属州域，投影成像素 ──────────────────────────────────────
out = []
skipped = []
for a in ALL:
    zname = JUN2Z[a]
    cell = cells.get(a)
    if cell is None or cell.is_empty:
        skipped.append(a)
        continue
    zp = zone[zname]
    clip = cell.intersection(zp)
    # ★ 2026-10 画布裁剪：仅限凉州（用户定案：酒泉郡西缘越出画布截除）。
    #   其他州不裁——日南郡等本就整体在画布南缘外，属既有口径，保持原状。
    if zname == '凉州':
        clip = clip.intersection(sbox(97.0, 18.0, 126.0, 44.0))
    if clip.is_empty:
        skipped.append(a)
        continue
    clip = clip.simplify(0.18 / abs(AX), preserve_topology=True)   # ~0.18 像素容差
    gs = list(clip.geoms) if hasattr(clip, 'geoms') else [clip]
    minA = zp.area * 2e-4   # ★ 2026-10：2e-3 会把 30~40 px² 的边界碎块整块丢掉
    gs = [g for g in gs if g.geom_type == 'Polygon' and g.area > minA and not g.is_empty]
    if not gs:
        skipped.append(a)
        continue
    gs.sort(key=lambda g: -g.area)

    def _clean(g):
        """投影后取整(0.1px)会破坏有效性，逐环规整并展平。"""
        pts = [prj(*c) for c in g.exterior.coords]
        q = Polygon(pts)
        if not q.is_valid or q.area <= 0:
            q = q.buffer(0)
        if q.is_empty:
            return []
        return [h for h in (q.geoms if hasattr(q, 'geoms') else [q])
                if h.geom_type == 'Polygon' and h.area > 0]

    rings = []
    for g in gs[:3]:
        g2 = g.buffer(0)
        for h in (g2.geoms if hasattr(g2, 'geoms') else [g2]):
            if h.geom_type == 'Polygon' and not h.is_empty:
                for r in _clean(h):
                    rings.append([list(c) for c in r.exterior.coords])
    if not rings:
        skipped.append(a)
        continue
    # 主环 = 含治所的环（否则按面积最大），保证郡面不错位
    _sp = prj(*seat[a])
    rings.sort(key=lambda r: (0 if Polygon(r).contains(Point(_sp)) else 1, -Polygon(r).area))
    out.append({'name': a, 'zhou': zname, 'seat': list(prj(*seat[a])),
                'pts': rings[0], 'extra': rings[1:], 'n': len(rings)})

# ── 像素空间去重叠：消除「简化 + 取整」引入的边缘噪声 ──────────────────────
# 经纬空间里 cell 两两严格互补（A∩B=0），但输出前做了两件会破坏这件事的操作：
#   ① simplify(0.18px) 对相邻两郡各自简化 → 折线各自抖动，不再严格重合；
#   ② 坐标取整到 0.1px → 边界线两侧各偏半像素。
# 结果残留 15 处 1~6 px² 的「条状」重叠（九真×益州 6.47、南郡×武陵 2.6 …）。
# 这里按面积从大到小定案，后续郡一律让出已定案部分——重叠量 <30 px²，
# 从大郡让给已定案的小块不影响观感，且保证「互不重叠」这一硬约束成立。
_FINAL = {}
_order = sorted(out, key=lambda x: -Polygon(x['pts']).area)
_px_fix, _px_area = 0, 0.0
for x in _order:
    g = unary_union([Polygon(x['pts']).buffer(0)] +
                    [Polygon(r).buffer(0) for r in x['extra']]).buffer(0)
    for other in _FINAL.values():
        if g.distance(other) > 0 or not g.intersects(other):
            continue
        ov = g.intersection(other)
        if ov.is_empty:
            continue
        a_ov = ov.area
        if a_ov < 1e-8:
            continue
        g = g.difference(ov).buffer(0)
        _px_fix += 1
        _px_area += a_ov
    _FINAL[x['name']] = g
print('像素去重叠：%d 块，合计 %.1f px²' % (_px_fix, _px_area))

# 写回：把去重叠后的几何重新展平成环（主环 = 含治所者）
# ★ 前端（map_core.js 的 gJunPoly）对每个环只画 dPoly(ring) 一条外环路径，
#   **不支持内环（洞）**。而 difference 会产出带洞的多边形，若只取 exterior，
#   洞被静默丢弃 → 该块重新落进别人地盘 → 重叠复现（张掖居延属国×朔方郡 1.8 px²）。
#   这里用标准「切缝（slit）」把每个洞接到外环上：洞上取一点 P，外环上取离 P 最近的
#   顶点 Q，把环展平成 exterior…→Q→P→(绕洞一周)→P→Q→…exterior 的简单多边形。
#   切缝宽度为 0（Q→P 与 P→Q 往返两次），渲染出来是一条不可见的零宽线，
#   但多边形语义正确：洞真的被挖掉了。
def _slit(poly, eps=0.02):
    """把带洞多边形展平成简单外环点串（每个洞接一条窄通道）。

    ★ 两个坑：
      ① 零宽切缝（Q→P 与 P→Q 完全重合）在 shapely 里是「自接触」，is_valid=False，
         随后的 buffer(0) 会把它「修复」成**把洞填实**；
      ② 洞环与外环同向插入、中间再补一条反向平移环，等于把洞整体搬个位置塞回去，
         面积恢复成全实心（实测朔方郡 27084.5 → 27086.3，重叠又冒出来）。
      正确做法：从外环的顶点 Q 沿一条 eps 宽的通道走到洞上最近点 P，
      **按与外环相反的方向**绕洞一周，再沿通道走回 Q。这样它是一个真正的
      凹入形（notch），拓扑合法、面积正确（= 外环 − 洞），渲染上看不见通道。"""
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
        # P = 洞上离 Q 最近的点
        best_p, best_pd = 0, float('inf')
        for pi in range(len(rc) - 1):
            d = Point(rc[pi]).distance(anchor)
            if d < best_pd:
                best_pd, best_p = d, pi
        P = rc[best_p]
        if L < 1e-9:
            continue
        # 通道两侧各偏 eps/2，形成一条细长缺口（非零宽 → 合法拓扑）
        nx, ny = -vy / L, vx / L
        qa = (anchor.x + nx * eps / 2, anchor.y + ny * eps / 2)
        qb = (anchor.x - nx * eps / 2, anchor.y - ny * eps / 2)
        pa = (P[0] + nx * eps / 2, P[1] + ny * eps / 2)
        pb = (P[0] - nx * eps / 2, P[1] - ny * eps / 2)
        # 反向外环方向绕洞：从 P 起，沿 rc 的反序
        loop = rc[best_p:][::-1] + rc[:best_p + 1][::-1]
        loop = [tuple(c) for c in loop][1:]      # 首点已由 pa 承担
        ext = (ext[:best_q + 1] + [qa] + [pa] + loop + [pb] + [qb]
               + ext[best_q + 1:])
    q = Polygon(ext)
    if not q.is_valid:
        q2 = q.buffer(0)
        if not q2.is_empty and hasattr(q2, 'geoms'):
            q2 = max(q2.geoms, key=lambda g: g.area)
        if not q2.is_empty:
            ext = list(q2.exterior.coords)
    return ext


_out2 = []
for x in out:
    g = _FINAL[x['name']]
    if g.is_empty:
        continue
    parts = [h for h in (g.geoms if hasattr(g, 'geoms') else [g])
             if h.geom_type == 'Polygon' and h.area > 0.5]
    if not parts:
        continue
    parts.sort(key=lambda h: (0 if h.contains(Point(x['seat'])) else 1, -h.area))
    # ★ 这里不能再 round 到 0.1px：去重叠已是像素空间的严格结果，
    #   再次取整会让相邻边界各自偏半像素，长边界上累积成 ~1.8 px² 的条状重叠。
    x['pts'] = [[c[0], c[1]] for c in _slit(parts[0])]
    x['extra'] = [[[c[0], c[1]] for c in _slit(p)] for p in parts[1:]]
    x['n'] = len(parts)
    _out2.append(x)
out = _out2

json.dump(out, io.open(os.path.join(ROOT, 'build/junpoly.json'), 'w', encoding='utf-8'),
          ensure_ascii=False)
print('郡界生成：', len(out), '个面；飞地：', sum(1 for x in out if x['extra']),
      '；跳过：', skipped)

# ── 自检 1：覆盖率 ─────────────────────────────────────────────────────────
byz = defaultdict(list)
for x in out:
    polys = [Polygon(x['pts']).buffer(0)] + [Polygon(r).buffer(0) for r in x['extra']]
    polys = [p for p in polys if not p.is_empty]
    byz[x['zhou']].append(unary_union(polys))
print('\n覆盖校验（郡面并集 / 州面）：')
bad = 0
for zname, polys in sorted(byz.items()):
    u = unary_union(polys)
    zp = zhou_poly.get(zname)
    za = zp.area * abs(AX * AY)            # 经纬面积 → 像素面积
    cov = u.area / za if za else 0
    flag = '' if 0.97 < cov < 1.03 else '  ⚠'
    if flag:
        bad += 1
    print('  %-4s 州%9.1f  郡%9.1f  覆盖%6.3f%s' % (zname, za, u.area, cov, flag))
print('异常州数：', bad)

# ── 自检 2：两两重叠（本次修复的核心指标） ─────────────────────────────────
print('\n重叠自检：')
G = {x['name']: unary_union([Polygon(x['pts']).buffer(0)] +
                            [Polygon(r).buffer(0) for r in x['extra']]).buffer(0)
     for x in out}
nm = list(G)
pairs = []
for i in range(len(nm)):
    for j in range(i + 1, len(nm)):
        A, B = G[nm[i]], G[nm[j]]
        if A.distance(B) > 0:
            continue
        ar = A.intersection(B).area
        if ar > 1.0:
            pairs.append((round(ar, 2), nm[i], nm[j]))
pairs.sort(reverse=True)
print('  重叠对 %d 处，合计 %.1f px²%s' % (len(pairs), sum(p[0] for p in pairs),
                                    '' if not pairs else '  最大:' + str(pairs[:3])))
