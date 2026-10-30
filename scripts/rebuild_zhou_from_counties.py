#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按县点重建 13 州州界（v2：凸包种子 + 约束 Voronoi）。

背景
----
data/geo-real.json 的 zhoupoly 是手绘示意多边形，与 counties-han.json 的 342 个
真实县点坐标系统性不符：101 个县点（29.5%）落在自己州界外，兖州 68%、并州 63%、
徐州 60%、凉州 48%。郡界、地区、地名定位全部连带错位。

v1（纯点 Voronoi）的失败
-----------------------
直接对 342 个县点做 Voronoi 再按州汇聚，等价于「按县点密度分配面积」：
兖州 25 个县点却要覆盖狭长地带，被邻州反复啃食，6 轮迭代后从 6.16°² 掉到 0.07°²。

v2 方案
-------
1. 每州种子 = 该州县点的**凸包**（凸包面积与史实疆域比例相符：
   兖 4.0 / 青 4.1 / 司隶 5.1 / 冀 6.6 / 徐 8.6 / 豫 10.3 / 并 17.8 / 幽 22.2 …）；
2. 种子间做 Voronoi（凸包内均匀撒点 → 点 Voronoi → 按点归州，
   等效于多边形 Voronoi），每州分到「离自己凸包最近」的区域；
3. 裁到陆地面与画布；界外县点局部外扩补回；
4. 州间缝隙归零、重叠归零（切分方向取两州凸包中心，避免用重合的边界点）；
5. 收敛后校验：县点 100% 界内、缝隙 < 0.05°²、重叠 0。

输出 build/zhoupoly_refit.json（经纬度，格式与旧文件一致，下游无需改动）。
"""
import json, io, os, math
from collections import defaultdict

from shapely.geometry import Polygon, MultiPoint, Point, LineString, box
from shapely.ops import unary_union, linemerge, voronoi_diagram, nearest_points
from shapely.strtree import STRtree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
geo = json.load(io.open(os.path.join(ROOT, 'data/geo-real.json'), encoding='utf-8'))
county = json.load(io.open(os.path.join(ROOT, 'data/counties-han.json'), encoding='utf-8'))['counties']

LNG0, LNG1, LAT0, LAT1 = 97.0, 126.0, 18.0, 44.0
CANVAS = box(LNG0, LAT0, LNG1, LAT1)

# ── 陆地面：拼出「完整海岸线」+ 西北外框 ────────────────────────────────────
# ★ 关键修复（2026-10）：早期版本直接取 linemerge 后最长的那一段当海岸线。
#   而 NE 10m 海岸数据在长江口（119.918E, 32.754N）处断成两段——
#   第 0 段 108.3E/16.0N → 119.918E/32.754N（华南、东南沿海，99.2°），
#   第 1 段 119.918E/32.754N → 129.99E/41.96N（苏北、山东、渤海、辽东，84.7°），
#   两段端点完全重合，但 linemerge 因端点方向不连续没有并成一条。
#   只取第 0 段 → 「徐州以东 124~126E 的整片黄海」被外框兜成了陆地：
#   徐州州界一路伸到 125.59E、青州到 125.02E，郡面再也铺不满州域（徐州覆盖率仅 0.53）。
#   现在显式按端点贪心拼接所有长段，得到 184° 的完整海岸线。
segs = [LineString(s) for s in geo['coast'] if len(s) > 1]
merged = linemerge(unary_union(segs))
parts = [p for p in (merged.geoms if hasattr(merged, 'geoms') else [merged])
         if p.length > 2.0]                      # 太短的碎段（<2°）是离岛，跳过
parts.sort(key=lambda l: -l.length)
chain = list(parts.pop(0).coords)
TOL = 1e-6
while parts:
    hit = None
    for i, p in enumerate(parts):
        pc = list(p.coords)
        if math.dist(chain[-1], pc[0]) < TOL:
            hit = (i, pc[1:])
            break
        if math.dist(chain[-1], pc[-1]) < TOL:
            hit = (i, pc[::-1][1:])
            break
        if math.dist(chain[0], pc[-1]) < TOL:
            hit = (i, 'pre', pc[:-1])
            break
        if math.dist(chain[0], pc[0]) < TOL:
            hit = (i, 'pre', pc[::-1][:-1])
            break
    if hit is None:
        break
    i, tail = hit
    if len(hit) == 3:
        chain = list(tail) + chain
    else:
        chain = chain + list(tail)
    parts.pop(i)
co = chain
s0, s1 = co[0], co[-1]
# ★ 2026-10：外框西界用 LNGW=93.5 而非 LNG0=97。敦煌郡（92.5~97E）在画布经度
#   判定上是画布外（97E 以西），但底图像素画布实际覆盖到 93.8E（x=0 ↔ 93.8E），
#   底图上敦煌一带是可见陆地；外框若止于 97E，HEXI 补块 ∩land 会变成空集，
#   渊泉/敦煌继续沦为孤立圆斑。
LNGW = 93.5
land = Polygon(co + [[LNG1, s1[1]], [LNG1, LAT1], [LNGW, LAT1], [LNGW, LAT0],
                     [LNGW, s0[1]], s0]).buffer(0)
print('海岸线 %.1f°（拼接 %d 段），%d 点；陆地面 %.1f°²' % (
    LineString(co).length, len(co), len(co), land.area))

ZHOUS = sorted({c['p'] for c in county})
pts_of = defaultdict(list)
for c in county:
    pts_of[c['p']].append((c['lng'], c['lat']))
print('县点 %d，%d 州' % (len(county), len(ZHOUS)))


def parts_of(g):
    return [p for p in (g.geoms if hasattr(g, 'geoms') else [g])
            if p.geom_type == 'Polygon' and not p.is_empty]


def center(g):
    """州的稳定中心：凸包质心。比 representative_point 稳，不会因碎块漂移。"""
    return g.convex_hull.centroid


# ── 1. 种子 = 县点凸包 ─────────────────────────────────────────────────────
seed = {}
for z in ZHOUS:
    hull = MultiPoint(pts_of[z]).convex_hull
    if hull.geom_type != 'Polygon':
        hull = hull.buffer(0.3)
    seed[z] = hull.buffer(0.02)
print('种子（凸包）面积：' + ' '.join('%s=%.1f' % (z, seed[z].area) for z in ZHOUS))

# ── 2. 种子 Voronoi：凸包内均匀撒点，点 Voronoi 后按点归州 ─────────────────
def sample_in(poly, step=0.25):
    minx, miny, maxx, maxy = poly.bounds
    out = []
    y = miny + step / 2
    while y <= maxy:
        x = minx + step / 2
        while x <= maxx:
            if poly.contains(Point(x, y)):
                out.append((x, y))
            x += step
        y += step
    if not out:
        rp = poly.representative_point()
        out = [(rp.x, rp.y)]
    return out


all_sites = []
for z in ZHOUS:
    for (x, y) in sample_in(seed[z]):
        all_sites.append((z, x, y))
# ★ 2026-10：县点本身也作为站点加入 Voronoi。此前只对凸包内采样点剖分，
#   县点稀疏的州（兖州南部）分界被邻州密集点云推过县点，随后 fix_points
#   逐点挖盘回收，每个回收盘都是「圆头+细腰」的葫芦形齿——兖州南界一排
#   葫芦串就是这么来的。县点入站后，每个县点自带一个必归本州的小 cell，
#   州界在县点之间自然平分，事后回收几乎归零。
for z in ZHOUS:
    for (x, y) in pts_of[z]:
        all_sites.append((z, x, y))
print('种子采样点 %d（含县点 %d）' % (len(all_sites), len(county)))

# ── 剖分边界 CLIP ─────────────────────────────────────────────────────────
# ★ 这是本脚本最要紧的一处修复（2026-10）。早期版本直接对 CANVAS(97~126E) 做 Voronoi：
#   凸包最外圈的采样点，其单元会**无界地**向四周延伸——
#   徐州凸包最东只到 120.4E，单元却一路伸到画布东界 126E，整片黄海被算进徐州，
#   徐州州界于是变成 116.6~125.6E 的巨块，郡面永远铺不满（覆盖率 0.53）。
#   同样，扬州南界被拉到画布南界 18N（整片南海归扬州），交州西界被拉到 98.9E。
#
#   限幅必须「东紧南北西松」：
#     · 东侧（>121.5E）：黄海、东海不该属任何州，从 121.5E 起一刀切；
#     · 南侧、西侧：交州（日南 106.5E/16.8N）、益州（永昌 99E/22N）真实辖域离凸包远，
#       必须保留到画布边界，否则会把合法辖域切掉（实测扬州 137.7→84.6）。
#   于是 CLIP = 凸包并集外扩 6°（足够覆盖边疆州） ∩ 「东界分段」 ∪ 画布。
# ★ 2026-10 修复：东切不能一刀切到 44N——辽东郡（襄平 123.2E）、玄菟（侯城 123.4E/
#   高句骊 125.4E）、乐浪（朝鲜 125.4E）都是汉朝实土，全在 122.3E 以东。
#   一刀切的结果是幽州主环被截到 122.7E、半岛主体消失，三个治所靠 keep_points
#   补成孤立圆斑（用户看到的「辽东=一条竖条+三个圆斑」就是这里来的）。
#   现在东切按纬度分段：40°N 以南（黄海/东海，徐青扬的虚假东扩）照旧切到 122.3E；
#   40°N 以北（辽东—乐浪，真实汉土）保留到画布东界，海面由陆地面裁切负责。
COAST_CUT_LNG = 122.3
# ★ 2026-10 二次修复：38.3N 以北整块放开 → Voronoi 单元会一路铺到画布东界 126E，
#   幽州主环于是在朝鲜半岛东侧长出一根 123~126E 的巨型直边楔子（画面上是一条
#   压在朝鲜半岛/日本海上的竖条），并且把乐浪的单元从主体上「掰」开。
# ★ 2026-10 三修：收紧到 124.9/125.95/125.6 又产生新问题——这些直边落在朝鲜半岛
#   陆地内部（乐浪以东是半岛山地），放大后仍是一条压在陆地上的竖线。
#   现在辽东—朝鲜段直接放开到画布东界 126E：幽州单元延伸到画布边后被陆地面
#   (geo-real coast，覆盖到 130E) 裁切，朝鲜东海岸在 128E+ 超出画布，
#   最终州界的「直边」全部落到画布外，画面上只见贴合海岸/山地的边界。
#     · 18~38.3N  黄海/东海：切到 122.3E（徐、青、扬的虚假东扩）；
#     · 38.3~44.0N 辽东—乐浪（真实汉土）：放开到画布东界 126E。
PEN_EDGE = [  # (lat_hi, lng_hi)
    (38.3, 122.3),
    (LAT1 + 1, LNG1),
]
_east = []
for (hi, lng) in PEN_EDGE:
    lo = LAT0 if not _east else _east[-1][0]
    _east.append((hi, box(LNG0, lo, lng, hi)))
EAST_CUT = unary_union([b for _, b in _east])
# 凸包并集外扩 6°（覆盖边疆州）∪ 「西南保留区」= 画布本体；整体再与「122.3E 以西」求交。
# 注意不要先 union 画布再 intersect——那样等于把整块画布又并回来了（限幅失效）。
WEST_SOUTH = unary_union(list(seed.values())).buffer(6.0).union(CANVAS)
CLIP = WEST_SOUTH.intersection(EAST_CUT).intersection(CANVAS).buffer(0)
# ★ 补一块朝鲜半岛实土：凸包并集只到 125.4E/39.16N，而乐浪郡南界（带方、列口）
#   与半岛西海岸（124.9~125.9E, 38.3~39.9N）在凸包外，会被 CLIP 直接切掉。
PEN_BOX = box(124.55, 38.25, 126.0, 39.95).intersection(CANVAS)
CLIP = CLIP.union(PEN_BOX.intersection(land)).buffer(0)
# ★ 2026-10：河西走廊西段同理。画布/剖分西界 97E 切掉了敦煌郡（92.5~97E），
#   渊泉(96.0,40.45)、敦煌(94.66,40.14) 落在剖分范围外，keep_points 把它们
#   补成两个孤立圆斑（用户截图「河西左边两个圈」）。底图像素画布实际覆盖
#   到 93.8E（x=0 ↔ 93.8E），底图上敦煌一带是可见陆地。把剖分范围在河西
#   纬度带向西放开到 93.5E（画布内），∩land 后贴真实地形。
WEXT = box(93.5, LAT0, LNG1, LAT1)
HEXI = box(93.5, 38.0, 97.6, 43.4)
CLIP = CLIP.union(HEXI.intersection(land).intersection(WEXT)).buffer(0)
print('剖分区域 %.1f°²  bounds %s' % (CLIP.area, [round(v, 1) for v in CLIP.bounds]))

vd = voronoi_diagram(MultiPoint([(x, y) for _, x, y in all_sites]), envelope=CLIP.envelope)
cells = []
for cc in (vd.geoms if hasattr(vd, 'geoms') else [vd]):
    i = cc.intersection(CLIP)            # envelope 不裁边界，必须显式求交
    for q in (i.geoms if hasattr(i, 'geoms') else [i]):
        if q.geom_type == 'Polygon' and q.area > 1e-6:
            cells.append(q)
print('单元 %d' % len(cells))

# 每个 Voronoi 单元归给「包含它的采样点」所属的州。一个单元可能被多个州的采样点共享
# （三角形漏点附近），也可能整个落在所有凸包之外（海面、荒漠），此时归给**种子凸包最近**的州。
# ★ 修复（2026-10）：早期版本对「无采样点包含的单元」直接 `min(cells, key=distance(p))`
#   就近分配——黄海上那一大片单元离徐州、青州的凸包最近，于是整块黄海被算进了徐州/青州，
#   州界一路伸到 125.6E，郡面再也铺不满州域。现在要求「单元必须挨着本州凸包 0.6° 以内」，
#   超出的单元直接丢弃（陆地裁切后本来也不会要它）。
tree = STRtree(cells)
seed_geoms = {z: seed[z] for z in ZHOUS}
# ★ 2026-10：空 cell / 重叠归属判据用「县点云距离」而非凸包距离。
#   凸包对县点稀疏的州失真（兖州南部县点离邻州凸包更近），把县点 cell
#   周围的空 cell 全判给邻州，县点 cell 只剩角点与主体相连 → unary_union
#   后长出「圆头+细腰」的葫芦串边界。县点云距离让分界自然走在两州县点中间。
from shapely.geometry import MultiPoint as _MP
seed_pts = {z: _MP(pts_of[z]) for z in ZHOUS}


def nearest_zhou(cell):
    best, bd = None, None
    c = cell.representative_point()
    for z in ZHOUS:
        d = seed_pts[z].distance(Point(c.x, c.y))
        if bd is None or d < bd:
            bd, best = d, z
    return best, bd


state_union = defaultdict(list)
dropped = 0
site_pts = [(z, Point(x, y)) for (z, x, y) in all_sites if True]
site_tree = STRtree([p for _, p in site_pts])
for ci, cell in enumerate(cells):
    owners = set()
    idx = site_tree.query(cell)
    for i in idx:
        if cell.contains(site_pts[i][1]):
            owners.add(site_pts[i][0])
    if not owners:
        z, d = nearest_zhou(cell)
        if d > 0.6:                     # 离所有凸包都远（海面/荒漠），丢弃
            dropped += 1
            continue
        owners = {z}
    for z in owners:
        state_union[z].append(cell)
print('丢弃远离各州的海面单元：%d' % dropped)

states = {z: unary_union(state_union[z]).buffer(0) for z in ZHOUS}
print('DBG after_voronoi: 兖州 ratio %.2f' % ((lambda g: g.length/g.area)(states['兖州'])))
_d={}
for _z in ZHOUS:
    _g=states[_z]
    _ps=_g.geoms if hasattr(_g,'geoms') else [_g]
    _d[_z]=[[(round(x,4),round(y,4)) for x,y in p.exterior.coords] for p in _ps if p.geom_type=='Polygon']
json.dump(_d, open('build/tmp/voronoi_stage.json','w'))
print('Voronoi 初稿：' + ' '.join('%s=%.1f' % (z, states[z].area) for z in ZHOUS))


# ── 3. 裁陆地 + 画布；界外县点局部外扩补回 ────────────────────────────────
def keep_points(zp, pts, max_bump=0.55):
    zp = zp.buffer(0)
    moved = 0
    for (x, y) in pts:
        p = Point(x, y)
        if zp.contains(p):
            continue
        q = nearest_points(zp, p)[0]
        if q.distance(p) > max_bump:
            continue
        # ★ 2026-10：补点圆盘半径不能固定 0.18°。max_bump 放到 0.9° 后，
        #   离界 0.9° 的点也被接上，固定半径的圆盘与州界之间留下一根极细的连杆，
        #   buffer(0) 一修就把圆盘判成「孤岛碎块」→ 归入邻州 → 画面上又冒出孤立圆斑
        #   （乐浪郡只有朝鲜一个治所点，就正是这样被补成小圆的）。
        #   半径按「接回距离」自适应，保证圆盘与主体是粗壮相连而非发丝粘连。
        zp = zp.union(LineString([q, p]).buffer(min(0.6, 0.18 + q.distance(p) * 0.6),
                                               cap_style=1)).buffer(0)
        moved += 1
    return zp, moved


for z in ZHOUS:
    # ★ 2026-10：必须只裁 land。早期写法 land.union(CANVAS) 是恒等裁切（CLIP⊂CANVAS），
    #   北黄海（122.3E 以东、38.3N 以北的海面）整个被算进幽州——这就是画面上
    #   辽东高亮伸进黄海、并带出一条直边楔子的来源。land 外环从 97E/16N 沿画布
    #   西界北上，整个画布西部（含西北荒漠）都在 land 内，只有海域在外，
    #   所以直接 ∩land 不会误伤边疆州；若某州裁空仍回退原面兜底。
    g = states[z].intersection(land).intersection(WEXT)
    if g.is_empty:
        g = states[z]
    g, _ = keep_points(g, pts_of[z])
    states[z] = g.buffer(0)
print('裁陆面后：' + ' '.join('%s=%.1f' % (z, states[z].area) for z in ZHOUS))
print('DBG after_land: 兖州 ratio %.2f' % ((lambda g: g.length/g.area)(states['兖州'])))

# ── 4. 缝隙归零 + 重叠归零 ─────────────────────────────────────────────────
for rnd in range(8):
    P = {z: states[z].buffer(0) for z in ZHOUS}
    U = unary_union(list(P.values()))
    D = 0.08
    gap = U.buffer(D).buffer(-D).difference(U)
    sealed = 0
    for g in parts_of(gap):
        if g.area < 1e-8:
            continue
        near = [z for z in ZHOUS if P[z].distance(g) < 1e-6]
        if len(near) < 2:
            continue
        anchors = {z: center(P[z]) for z in near}
        keys = {(round(a.x, 4), round(a.y, 4)) for a in anchors.values()}
        if len(keys) < len(near):
            continue
        cs = voronoi_diagram(MultiPoint(list(anchors.values())),
                             envelope=g.envelope.buffer(1))
        cs = list(cs.geoms) if hasattr(cs, 'geoms') else [cs]
        for z in near:
            a = anchors[z]
            cell = min(cs, key=lambda c: c.distance(a))
            piece = g.intersection(cell)
            if piece.is_empty or piece.area < 1e-10:
                continue
            states[z] = unary_union([states[z], piece]).buffer(0)
            sealed += 1
    # 重叠：每块按「离哪个州的种子（凸包）更近」判归属，
    # 归 a 的部分从 b 里减掉、归 b 的从 a 里减掉。不做半平面切割——
    # 兖州/豫州凸包中心仅相距 0.8°，一刀切会砍掉兖州 96%（5.0 → 0.2）。
    fixed = 0
    for i, a in enumerate(ZHOUS):
        for b in ZHOUS[i + 1:]:
            inter = states[a].buffer(0).intersection(states[b].buffer(0)).buffer(0)
            if inter.area < 1e-9:
                continue
            for q in parts_of(inter):
                c = q.representative_point()
                if seed_pts[a].distance(c) <= seed_pts[b].distance(c):
                    states[b] = states[b].buffer(0).difference(q).buffer(0)
                else:
                    states[a] = states[a].buffer(0).difference(q).buffer(0)
            fixed += 1
    print('  第%d轮：填缝 %d 消重 %d | %s' % (rnd + 1, sealed, fixed,
          ' '.join('%s=%.1f' % (z, states[z].area) for z in
                   ['兖州', '青州', '冀州', '司隶', '豫州', '徐州'])))
    if sealed == 0 and fixed == 0:
        break

# ── 4b. 最终重叠清除 ───────────────────────────────────────────────────────
# 注意：两州交集常是 GeometryCollection（101 个部件里绝大多数是 LineString/Point，
# 面积为 0）。必须只处理 Polygon 部件，且循环条件看「Polygon 部件总面积」，
# 不能看 inter.area 总体（它包含退化部件会误判为"还有重叠"）。
def poly_parts(g):
    if g.is_empty:
        return []
    out = []
    for q in (g.geoms if hasattr(g, 'geoms') else [g]):
        if q.geom_type == 'Polygon' and q.area > 0:
            out.append(q)
        elif hasattr(q, 'geoms'):
            out.extend(x for x in q.geoms if x.geom_type == 'Polygon' and x.area > 0)
    return out


for _pass in range(8):
    tot_before = 0.0
    for i, a in enumerate(ZHOUS):
        for b in ZHOUS[i + 1:]:
            inter = states[a].buffer(0).intersection(states[b].buffer(0)).buffer(0)
            ps = poly_parts(inter)
            if not ps:
                continue
            tot_before += sum(q.area for q in ps)
            minx, miny, maxx, maxy = inter.bounds
            step = 0.01
            y = miny
            while y < maxy:
                x = minx
                while x < maxx:
                    cell = box(x, y, x + step, y + step)
                    piece = cell.intersection(inter)
                    if not piece.is_empty and piece.area > 1e-12:
                        c = piece.centroid
                        # 若这一格里就有县点，直接判给该县点所属州——
                        # 否则会与 fix_points 互相拉锯（回收→被消重切走→再回收，永不收敛）
                        owner = None
                        for zz in ZHOUS:
                            if any(piece.buffer(1e-6).contains(Point(px, py))
                                   for (px, py) in pts_of[zz]):
                                owner = zz
                                break
                        if owner is None:
                            owner = a if seed_pts[a].distance(c) <= seed_pts[b].distance(c) else b
                        if owner == a:
                            states[b] = states[b].buffer(0).difference(piece).buffer(0)
                        else:
                            states[a] = states[a].buffer(0).difference(piece).buffer(0)
                    x += step
                y += step
    tot_after = 0.0
    for i, a in enumerate(ZHOUS):
        for b in ZHOUS[i + 1:]:
            ps = poly_parts(states[a].buffer(0).intersection(states[b].buffer(0)).buffer(0))
            tot_after += sum(q.area for q in ps)
    print('  消重 pass%d：%.4f → %.4f°²' % (_pass + 1, tot_before, tot_after))
    if tot_after < 1e-4:
        break


# ── 4c. 边界形态学平滑（去葫芦齿） ─────────────────────────────────────────
# 兖州南界的「圆头+细腰葫芦串」：县点 cell 周围的采样 cell 被邻州占据时，
# 县点 cell 只剩角点与主体相连。closing（膨胀+收缩 r=0.12）把细腰焊粗、
# 把齿间凹谷填平；closing 削掉的凸尖由「无人区按原州交集归还」补回，
# 重叠交给收尾循环重清。
CLOSE_R = 0.12
_orig = {z: states[z].buffer(0) for z in ZHOUS}
for z in ZHOUS:
    g = states[z].buffer(CLOSE_R).buffer(-CLOSE_R)
    if not g.is_empty and g.area > states[z].area * 0.85:
        states[z] = g.buffer(0)
print('closing(%s) 后：' % CLOSE_R + ' '.join('%s=%.1f' % (z, states[z].area) for z in ZHOUS))
_missing = unary_union(list(_orig.values())).difference(unary_union(list(states.values())))
_back = 0
for q in parts_of(_missing):
    if q.area < 1e-8:
        continue
    best, ba = None, 0.0
    for z in ZHOUS:
        a = _orig[z].intersection(q).area
        if a > ba:
            ba, best = a, z
    if best is not None:
        states[best] = unary_union([states[best], q]).buffer(0)
        _back += 1
print('closing 无人区归还 %d 块' % _back)

# ── 5. 最终县点兜底（放在重叠清除之后，否则刚收回的地被再度切走） ────────────────────────────────────────────────────────
# 界线邻近的县点会被凸包 Voronoi 判给邻州（豫州昆阳/虹/鲁/邹、青州安德）。
# 这里「谁的点归谁」：把该点周围一小片从邻州手里收回本州（半径 0.16°，
# 约 6px，只削掉边界薄薄一层，不动邻州主体）。
for z in ZHOUS:
    for (x, y) in pts_of[z]:
        p = Point(x, y)
        if states[z].buffer(0.004).contains(p):
            continue
        # 半径按「该点到本州现状边界的距离」自适应：鲁/邹距豫州界 0.4°，
        # 固定 0.16° 收不回来；上限 0.6° 防止一把抓走邻州主体。
        need = states[z].distance(p)
        disk = p.buffer(min(0.6, max(0.16, need + 0.10)))
        for o in ZHOUS:
            if o == z:
                continue
            if states[o].intersects(disk):
                states[o] = states[o].buffer(0).difference(disk).buffer(0)
        states[z] = unary_union([states[z], disk]).buffer(0)

lost = []
for z in ZHOUS:
    st, _ = keep_points(states[z], pts_of[z], max_bump=0.9)
    states[z] = st.buffer(0)
    for (x, y) in pts_of[z]:
        if not states[z].buffer(0.004).contains(Point(x, y)):
            lost.append((z, round(x, 2), round(y, 2)))
print('最终界外县点：%d %s' % (len(lost), lost[:10]))


# ── 5b. 收尾修正：县点归属 + 重叠清除 交替，直到两点同时满足 ────────────────
def fix_points():
    n = 0
    for z in ZHOUS:
        for (x, y) in pts_of[z]:
            p = Point(x, y)
            if states[z].buffer(0.004).contains(p):
                continue
            need = states[z].distance(p)
            disk = p.buffer(min(0.7, max(0.12, need + 0.08)))
            for o in ZHOUS:
                if o != z and states[o].intersects(disk):
                    states[o] = states[o].buffer(0).difference(disk).buffer(0)
            states[z] = unary_union([states[z], disk]).buffer(0)
            n += 1
    return n


def clear_overlap():
    n = 0
    for i, a in enumerate(ZHOUS):
        for b in ZHOUS[i + 1:]:
            inter = states[a].buffer(0).intersection(states[b].buffer(0)).buffer(0)
            ps = poly_parts(inter)
            if not ps:
                continue
            minx, miny, maxx, maxy = inter.bounds
            step = 0.01
            y = miny
            while y < maxy:
                x = minx
                while x < maxx:
                    cell = box(x, y, x + step, y + step)
                    piece = cell.intersection(inter)
                    if not piece.is_empty and piece.area > 1e-12:
                        c = piece.centroid
                        # 若这一格里就有县点，直接判给该县点所属州——
                        # 否则会与 fix_points 互相拉锯（回收→被消重切走→再回收，永不收敛）
                        owner = None
                        for zz in ZHOUS:
                            if any(piece.buffer(1e-6).contains(Point(px, py))
                                   for (px, py) in pts_of[zz]):
                                owner = zz
                                break
                        if owner is None:
                            owner = a if seed_pts[a].distance(c) <= seed_pts[b].distance(c) else b
                        if owner == a:
                            states[b] = states[b].buffer(0).difference(piece).buffer(0)
                        else:
                            states[a] = states[a].buffer(0).difference(piece).buffer(0)
                    x += step
                y += step
            n += 1
    return n


for _k in range(5):
    nf = fix_points()
    nov = clear_overlap()
    ins = sum(1 for z in ZHOUS for (x, y) in pts_of[z]
              if states[z].buffer(0.004).contains(Point(x, y)))
    print('  收尾 %d：回收 %d 点，消重 %d 对，界内 %d/%d' % (_k + 1, nf, nov, ins, len(county)))
    if nf == 0 and nov == 0:
        break

# ── 6. 输出 ────────────────────────────────────────────────────────────────
def thin(ring, step=0.012):
    if len(ring) < 4:
        return ring
    out = [ring[0]]
    for p in ring[1:-1]:
        if math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) >= step:
            out.append(p)
    return out


# 碎环处理：网格消重会在州界上切出细长碎片（豫州曾出现 4 个 7~12 点的飞地环，
# 面积 0.001~0.003°² 却插进兖州，造成 0.15°² 重叠）。
# 只保留「面积 ≥ 主块 3% 或 ≥0.02°²」的环，其余并入最近的邻州（真正相邻的那个）。
MIN_FRAC, MIN_ABS = 0.03, 0.02
absorbed = 0
for z in ZHOUS:
    ps = sorted(parts_of(states[z].buffer(0)), key=lambda q: -q.area)
    if not ps:
        continue
    main_area = ps[0].area
    keep, drop = [ps[0]], []
    for q in ps[1:]:
        if q.area >= max(MIN_ABS, main_area * MIN_FRAC):
            keep.append(q)
        else:
            drop.append(q)
    for q in drop:
        # 找最近的其他州并入
        best, bd = None, None
        for o in ZHOUS:
            if o == z:
                continue
            d = states[o].distance(q)
            if bd is None or d < bd:
                bd, best = d, o
        if best is not None:
            states[best] = unary_union([states[best], q]).buffer(0)
            absorbed += 1
    states[z] = unary_union(keep).buffer(0)
print('碎环并入邻州：%d 块' % absorbed)

out = {}
for z in ZHOUS:
    rings = []
    # 简化容差必须很小：两州边界各自独立简化后可能互相跨越
    simp = states[z].simplify(0.0008, preserve_topology=True)
    for p in sorted(parts_of(simp), key=lambda q: -q.area):
        r = thin([[round(x, 4), round(y, 4)] for x, y in p.exterior.coords])
        if len(r) >= 4:
            rings.append(r)
    out[z] = rings

# 输出后回写校验：simplify + thin 仍可能削掉边界薄层，导致个别县点跑到界外。
# 这里直接在「输出坐标」上做最后一遍回收，保证落盘文件自洽。
def ring_polys(rings):
    return [Polygon(r) for r in rings if len(r) >= 4]


for _t in range(4):
    P = {z: unary_union([p.buffer(0) for p in ring_polys(out[z])]) for z in ZHOUS}
    broke = [(z, x, y) for z in ZHOUS for (x, y) in pts_of[z]
             if not P[z].buffer(0.006).contains(Point(x, y))]
    if not broke:
        break
    for (z, x, y) in broke:
        p = Point(x, y)
        need = P[z].distance(p)
        disk = p.buffer(min(0.75, max(0.10, need + 0.06)))
        # 从邻州最新环里挖掉，并把圆盘补进本州
        for o in ZHOUS:
            if o == z:
                continue
            op = unary_union([q.buffer(0) for q in ring_polys(out[o])])
            if op.intersects(disk):
                op = op.difference(disk).buffer(0)
                parts = [q for q in (op.geoms if hasattr(op, 'geoms') else [op])
                         if q.geom_type == 'Polygon' and q.area > 1e-5]
                out[o] = [thin([[round(a, 4), round(b, 4)] for a, b in q.exterior.coords])
                          for q in sorted(parts, key=lambda q: -q.area)]
        zp = unary_union([q.buffer(0) for q in ring_polys(out[z])] + [disk]).buffer(0)
        parts = [q for q in (zp.geoms if hasattr(zp, 'geoms') else [zp])
                 if q.geom_type == 'Polygon' and q.area > 1e-5]
        out[z] = [thin([[round(a, 4), round(b, 4)] for a, b in q.exterior.coords])
                  for q in sorted(parts, key=lambda q: -q.area)]
    print('  回写修正 %d：处理 %d 点' % (_t + 1, len(broke)))
    # 回写的圆盘会与邻州重叠，就地清一遍（县点优先，不削点点）
    for i, a in enumerate(ZHOUS):
        for b in ZHOUS[i + 1:]:
            pa = unary_union([q.buffer(0) for q in ring_polys(out[a])])
            pb = unary_union([q.buffer(0) for q in ring_polys(out[b])])
            inter = pa.intersection(pb).buffer(0)
            if inter.area < 1e-9:
                continue
            for q in (inter.geoms if hasattr(inter, 'geoms') else [inter]):
                if q.geom_type != 'Polygon' or q.area < 1e-9:
                    continue
                has_a = any(q.buffer(1e-9).contains(Point(px, py)) for (px, py) in pts_of[a])
                has_b = any(q.buffer(1e-9).contains(Point(px, py)) for (px, py) in pts_of[b])
                if has_a and not has_b:
                    pa, pb = pa, pb.difference(q).buffer(0)
                elif has_b and not has_a:
                    pa, pb = pa.difference(q).buffer(0), pb
                else:
                    c = q.representative_point()
                    if seed_pts[a].distance(c) <= seed_pts[b].distance(c):
                        pb = pb.difference(q).buffer(0)
                    else:
                        pa = pa.difference(q).buffer(0)
            for tgt, geom in ((a, pa), (b, pb)):
                parts = [q for q in (geom.geoms if hasattr(geom, 'geoms') else [geom])
                         if q.geom_type == 'Polygon' and q.area > 1e-5]
                out[tgt] = [thin([[round(x, 4), round(y, 4)] for x, y in q.exterior.coords])
                            for q in sorted(parts, key=lambda q: -q.area)]

# 飞地纠偏：回写会在州上切出孤立小块（兖州曾出现 50 点的二级环插进豫州，
# 造成 0.10°² 重叠）。面积 < 主块 5% 的环直接并入「包含/最近」的邻州。
for _e in range(3):
    moved = 0
    for z in list(ZHOUS):
        polys = sorted(ring_polys(out[z]), key=lambda q: -q.area)
        if len(polys) < 2:
            continue
        main = polys[0]
        keep = [main]
        for q in polys[1:]:
            if q.area >= main.area * 0.05:
                keep.append(q)
                continue
            c = q.representative_point()
            owner = None
            for o in ZHOUS:
                if o == z:
                    continue
                op = unary_union([r_.buffer(0) for r_ in ring_polys(out[o])])
                if op.contains(c) or op.buffer(0.02).contains(c):
                    owner = o
                    break
            if owner is None:
                keep.append(q)
                continue
            op = unary_union([r_.buffer(0) for r_ in ring_polys(out[owner])] + [q]).buffer(0)
            parts = [p_ for p_ in (op.geoms if hasattr(op, 'geoms') else [op])
                     if p_.geom_type == 'Polygon' and p_.area > 1e-5]
            out[owner] = [thin([[round(x, 4), round(y, 4)] for x, y in p_.exterior.coords])
                          for p_ in sorted(parts, key=lambda p_: -p_.area)]
            moved += 1
        out[z] = [thin([[round(x, 4), round(y, 4)] for x, y in q.exterior.coords])
                  for q in keep]
    print('  飞地纠偏 %d：并入 %d 块' % (_e + 1, moved))
    if not moved:
        break

json.dump(out, io.open(os.path.join(ROOT, 'build/zhoupoly_refit.json'), 'w', encoding='utf-8'),
          ensure_ascii=False)

# ── 自检 ───────────────────────────────────────────────────────────────────
P = {z: unary_union([Polygon(r).buffer(0) for r in rs]) for z, rs in out.items()}
print('\n各州面积：' + ' '.join('%s=%.1f' % (z, P[z].area) for z in ZHOUS))
ok = 0
bad = []
for z in ZHOUS:
    ins = sum(1 for (x, y) in pts_of[z] if P[z].buffer(0.006).contains(Point(x, y)))
    ok += ins
    if ins < len(pts_of[z]):
        bad.append((z, ins, len(pts_of[z])))
print('县点在界内：%d/%d' % (ok, len(county)))
if bad:
    print('  不足：', bad)
U = unary_union(list(P.values()))
D = 0.08
gap = U.buffer(D).buffer(-D).difference(U)
gs = parts_of(gap)
print('州间缝隙：%d 块，%.4f°²（最大 %.4f°²）'
      % (len(gs), sum(g.area for g in gs), max([g.area for g in gs] or [0])))
ov = []
for i, a in enumerate(ZHOUS):
    for b in ZHOUS[i + 1:]:
        ar = P[a].intersection(P[b]).area
        if ar > 1e-4:
            ov.append((a, b, round(ar, 4)))
print('州间重叠：%d 处 %s' % (len(ov), ov[:6]))
print('总顶点：%d' % sum(len(r) for rs in out.values() for r in rs))
print('完成 → build/zhoupoly_refit.json')
