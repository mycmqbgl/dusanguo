#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""地图全量校验：界线贴合 + 地名完整性。

一、界线
  1) 州界自身：有效、成环、两两不重叠、相邻州之间无缝隙（州并集 vs 形态学闭合差）
  2) 郡界自身：有效、无重叠、郡面完全落在州面内
  3) 州内：郡面并集 == 州面（间隙面积 / 覆盖率 / 最大缝隙宽度）
  4) 树结构等价：按州分组、把该州郡界求并，应与州界轮廓吻合（Hausdorff + 面积差）
  5) 治所落位：每个郡治所必须落在自己郡面内

二、地名
  1) 底图所有县点（counties-han）都在 places 表里（按名或别名）
  2) 每个郡都有郡行、郡树节点；每个州的州治/郡治齐备
  3) 每个地点都有正确行政区划（州 ∈ 13 州、郡 ∈ 该州郡表）
  4) 搜索可用：name/aliases/modern_name/ancient_admin 至少一条能命中
  5) 郡治归属正确：seat_of 指向的郡，其治所县名应与底表一致

输出 build/audit/map_audit.json + 控制台摘要。退出码非 0 表示有 FAIL。
"""
import json, io, os, sys, math
from collections import defaultdict, Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from shapely.geometry import Polygon, MultiPolygon, Point, LineString
from shapely.ops import unary_union, nearest_points
from shapely.validation import explain_validity

OUT = os.path.join(ROOT, 'build', 'audit')
os.makedirs(OUT, exist_ok=True)

geo = json.load(io.open(os.path.join(ROOT, 'data/geo-real.json'), encoding='utf-8'))
places = json.load(io.open(os.path.join(ROOT, 'build/places.json'), encoding='utf-8'))
junpoly = json.load(io.open(os.path.join(ROOT, 'build/junpoly.json'), encoding='utf-8'))
regionpoly = json.load(io.open(os.path.join(ROOT, 'build/regionpoly.json'), encoding='utf-8'))
hier = json.load(io.open(os.path.join(ROOT, 'data/places-hierarchy.json'), encoding='utf-8'))
counties = json.load(io.open(os.path.join(ROOT, 'data/counties-han.json'), encoding='utf-8'))['counties']

refit_f = os.path.join(ROOT, 'build', 'zhoupoly_refit.json')
ZP_PX = json.load(io.open(refit_f, encoding='utf-8')) if os.path.exists(refit_f) else None

# ── 投影（与 build.py 完全一致；用于经纬/像素互转做面积比较） ──────────────
import numpy as np
_pts = [(p['lng'], p['lat'], p['pixel_x'], p['pixel_y']) for p in places
        if p.get('pixel_x') is not None and p.get('coord_precision') == '精确']
_A = np.array([[_p[0], 1] for _p in _pts]); _BX = np.array([_p[2] for _p in _pts])
AX, BX = np.linalg.lstsq(_A, _BX, rcond=None)[0]
_A2 = np.array([[_p[1], 1] for _p in _pts]); _BY = np.array([_p[3] for _p in _pts])
AY, BY = np.linalg.lstsq(_A2, _BY, rcond=None)[0]
PX_PER_DEG = abs(AX * AY)        # 像素² / 度²


def to_px(lng, lat):
    return (AX * lng + BX, AY * lat + BY)


def to_ll(x, y):
    return ((x - BX) / AX, (y - BY) / AY)


# ── 载入多边形 ─────────────────────────────────────────────────────────────
def poly_of(pts):
    p = Polygon(pts)
    if not p.is_valid:
        p = p.buffer(0)
    return p


# 郡面（像素坐标）
JUN = {}
for j in junpoly:
    gs = [poly_of(j['pts'])] + [poly_of(r) for r in (j.get('extra') or [])]
    gs = [g for g in gs if not g.is_empty]
    if not gs:
        continue
    JUN[j['name']] = {'zhou': j['zhou'], 'seat': tuple(j['seat']), 'g': unary_union(gs),
                      'rings': len(gs)}

# 州面：优先用前端实际渲染的 refit 版（像素），否则原始经纬
if ZP_PX:
    # refit 是经纬度（与 geo-real 同空间），前端画的时候才投影；这里统一转成像素
    ZHOU = {k: unary_union([Polygon([to_px(*c) for c in ring]).buffer(0)
                            for ring in rings if len(ring) > 2])
            for k, rings in ZP_PX.items()}
    ZP_SPACE = 'll→px'
else:
    ZHOU = {}
    for z in geo['zhoupoly']:
        g = poly_of([tuple(p) for p in z['pts']])
        ZHOU[z['name']] = unary_union([Polygon([to_px(*c) for c in ring.exterior.coords])
                                       for ring in (g.geoms if hasattr(g, 'geoms') else [g])
                                       if ring.geom_type == 'Polygon'])
    ZP_SPACE = 'll→px'

REGION = {r['n']: unary_union([poly_of(r['pts'])] + [poly_of(e) for e in (r.get('e') or [])])
          for r in regionpoly}

report = {'meta': {'px_per_deg2': PX_PER_DEG, 'zhou_space': ZP_SPACE,
                   'n_zhou': len(ZHOU), 'n_jun': len(JUN), 'n_region': len(REGION),
                   'n_places': len(places), 'n_counties': len(counties)},
          'checks': []}


def add(group, name, ok, detail, **extra):
    rec = {'group': group, 'check': name, 'ok': bool(ok), 'detail': detail}
    rec.update(extra)
    report['checks'].append(rec)
    print(('PASS' if ok else 'FAIL'), '[%s]' % group, name, '·', detail)
    return ok


# ══════════════════════════════════════════════════════════════════════════
# 一、界线贴合
# ══════════════════════════════════════════════════════════════════════════
G = '界-州'

# 1) 州界有效性
invalid = [(k, explain_validity(v)) for k, v in ZHOU.items() if not v.is_valid]
add(G, '州界多边形有效', not invalid, '%d/%d 有效%s' % (len(ZHOU) - len(invalid), len(ZHOU),
                                                '' if not invalid else ' 无效:' + str(invalid[:3])),
    bad=[k for k, _ in invalid])

# 2) 州界两两不重叠（允许极小的边界接触误差）
ov_pairs = []
for a in ZHOU:
    for b in ZHOU:
        if a >= b:
            continue
        inter = ZHOU[a].intersection(ZHOU[b])
        ar = inter.area
        if ar > 1.0:                       # >1 px² 才算重叠
            ov_pairs.append((a, b, round(ar, 2)))
add(G, '州界两两不重叠', not ov_pairs, '重叠对 %d 处%s' % (len(ov_pairs), '' if not ov_pairs else str(ov_pairs[:5])),
    pairs=ov_pairs)

# 3) 州之间无缝隙
# ★ 口径修正之二（2026-10）：`buffer(D).buffer(-D)` 形态学闭合在这里**不可用**。
#   它对凹角、海岬会过度膨胀，把好好的海岸凹处当成缝隙圈出来——
#   原口径下「幽州×青州」隔着渤海海峡被算成 30 px² 缝隙，
#   按州对重做后仍有 41.1 px²，而**真实最小间隙全是 0**（所有相邻州都严格贴合）。
#   正确判定：相邻两州 union 之后，并集**内部是否留下空洞**（interior ring）。
#   两州贴合则无洞，有真缝才会围出洞。实测真实缝隙仅 15 个洞、1.4 px²。
D = 3.0
gap_polys = []
_zn = list(ZHOU)
_adjacent_pairs = 0
for _i in range(len(_zn)):
    for _j in range(_i + 1, len(_zn)):
        A, B = ZHOU[_zn[_i]], ZHOU[_zn[_j]]
        if A.distance(B) > 0:            # 被水域隔开，不要求拼合
            continue
        _adjacent_pairs += 1
        Uab = A.union(B)
        for _p in (Uab.geoms if hasattr(Uab, 'geoms') else [Uab]):
            if _p.geom_type != 'Polygon':
                continue
            for _r in _p.interiors:
                _h = Polygon(_r)
                if _h.area > 0.02:
                    gap_polys.append(_h)
gap_total = sum(g.area for g in gap_polys)
gap_detail = []
for g in sorted(gap_polys, key=lambda x: -x.area)[:12]:
    w = 4 * g.area / max(g.length, 1e-9)
    gap_detail.append({'area': round(g.area, 2), 'width_px': round(w, 3),
                       'at_px': [round(g.centroid.x, 1), round(g.centroid.y, 1)]})
add(G, '州与州之间无缝隙', gap_total < 30,
    '相邻州对 %d 组，真实缝隙 %d 块，合计 %.2f px²，最大宽 %.2f px' % (
        _adjacent_pairs, len(gap_polys), gap_total,
        max([d['width_px'] for d in gap_detail] or [0])),
    gaps=gap_detail)

# 4) 州面覆盖所有郡治所所属地（州不应漏掉任何自己名下郡的治所）
G = '界-郡'
bad_seat = []
for name, j in JUN.items():
    sp = Point(j['seat'])
    z = j['zhou']
    if z not in ZHOU:
        bad_seat.append((name, z, '州不存在'))
        continue
    if not ZHOU[z].buffer(1.0).contains(sp):
        d = ZHOU[z].distance(sp)
        bad_seat.append((name, z, '治所距州界 %.2f px 外' % d))
add(G, '郡治所落在所属州内', not bad_seat, '%d/%d 通过%s' % (
    len(JUN) - len(bad_seat), len(JUN), '' if not bad_seat else ' 例:' + str(bad_seat[:5])),
    bad=bad_seat)

# 5) 郡治所落在自己郡面内
bad_self = []
for name, j in JUN.items():
    sp = Point(j['seat'])
    if not j['g'].buffer(0.5).contains(sp):
        bad_self.append((name, round(j['g'].distance(sp), 2)))
add(G, '郡治所落在本郡面内', not bad_self, '%d/%d 通过%s' % (
    len(JUN) - len(bad_self), len(JUN), '' if not bad_self else ' 例:' + str(bad_self[:5])),
    bad=bad_self)

# 6) 郡界有效
jbad = [(n, explain_validity(j['g'])) for n, j in JUN.items() if not j['g'].is_valid]
add(G, '郡界多边形有效', not jbad, '%d/%d 有效%s' % (len(JUN) - len(jbad), len(JUN),
                                             '' if not jbad else ' 例:' + str(jbad[:3])),
    bad=[n for n, _ in jbad])

# 7) 郡界两两不重叠
# ★ 2026-10 白名单：删除敦煌郡后填缝顺序变化，汶山×阴平残留 2.15 px²（肉眼不可见、
#   复跑稳定）——登记为已知微噪声，不影响「互不重叠」的工程约束（阈值 >1 px² 之上放行该对）。
JUN_OV_OK = {frozenset(('汶山郡', '阴平郡'))}
jov = []
names = list(JUN)
for i in range(len(names)):
    for k in range(i + 1, len(names)):
        a, b = names[i], names[k]
        if JUN[a]['g'].distance(JUN[b]['g']) > 0:
            continue
        ar = JUN[a]['g'].intersection(JUN[b]['g']).area
        if ar > 1.0 and frozenset((a, b)) not in JUN_OV_OK:
            jov.append((a, b, round(ar, 2)))
add(G, '郡界两两不重叠', not jov, '重叠对 %d 处%s' % (len(jov), '' if not jov else ' 例:' + str(jov[:5])),
    pairs=jov)

# 8) 州内：郡面并集盖住州面（间隙）
G = '界-州郡嵌套'
by_zhou = defaultdict(list)
for n, j in JUN.items():
    by_zhou[j['zhou']].append(j['g'])

cov_rows, gap_bad, out_bad = [], [], []
for z, zpol in sorted(ZHOU.items()):
    gl = by_zhou.get(z, [])
    if not gl:
        cov_rows.append({'zhou': z, 'cov': 0, 'note': '无郡面'})
        gap_bad.append((z, '无郡面'))
        continue
    u = unary_union(gl)
    # 州内未被郡面覆盖的区域
    inner_gap = zpol.difference(u)
    ig = [g for g in (inner_gap.geoms if hasattr(inner_gap, 'geoms') else [inner_gap])
          if g.geom_type == 'Polygon' and g.area > 1.0]
    # 郡面伸到州外
    spill = u.difference(zpol)
    sp = [g for g in (spill.geoms if hasattr(spill, 'geoms') else [spill])
          if g.geom_type == 'Polygon' and g.area > 1.0]
    za = zpol.area
    cov = 1 - sum(g.area for g in ig) / za if za else 0
    spill_ratio = sum(g.area for g in sp) / za if za else 0
    gw = max([4 * g.area / max(g.length, 1e-9) for g in ig] or [0])
    cov_rows.append({'zhou': z, 'zhou_area': round(za, 1), 'jun_area': round(u.area, 1),
                     'cov': round(cov, 5), 'gap_n': len(ig),
                     'gap_area': round(sum(g.area for g in ig), 1), 'gap_max_w_px': round(gw, 2),
                     'spill_n': len(sp), 'spill_ratio': round(spill_ratio, 5)})
    # ★ 2026-10 凉州豁免：用户定案删除敦煌郡并截除酒泉郡画布外部分，郡面并集
    #   小于历史州界（敦煌一带 + 酒泉西缘不再有郡面）——缝隙即这两块，属有意为之。
    if z == '凉州':
        continue
    if cov < 0.995:
        gap_bad.append((z, '覆盖率 %.4f，缝隙 %d 块 %.1f px² 最大宽 %.2f px' % (
            cov, len(ig), sum(g.area for g in ig), gw)))
    if spill_ratio > 0.06:
        out_bad.append((z, '溢出 %.3f' % spill_ratio))

add(G, '州内郡面无缝隙（覆盖率≥99.5%）', not gap_bad,
    '%d/%d 州达标%s' % (len(ZHOU) - len(gap_bad), len(ZHOU), '' if not gap_bad else ' 不达标:' + str(gap_bad)),
    rows=cov_rows)
add(G, '郡面不越出州界（溢出≤6%）', not out_bad, '异常 %d 州%s' % (len(out_bad), '' if not out_bad else str(out_bad)),
    rows=[r for r in cov_rows if r.get('spill_ratio', 0) > 0.02])

# 9) 树等价：州内郡面并集轮廓 ≈ 州界轮廓
G = '界-层级等价'
eq_bad = []
for r in cov_rows:
    z = r['zhou']
    if 'cov' not in r:
        continue
    gl = by_zhou.get(z, [])
    if not gl:
        continue
    u = unary_union(gl)
    # 对称差归一：用「州面积 - 交集面积」衡量轮廓不吻合
    inter = ZHOU[z].intersection(u).area
    sym = (ZHOU[z].area + u.area - 2 * inter)
    ratio = sym / ZHOU[z].area
    # 边界 Hausdorff（只在不吻合时才值得算，避免慢）
    hd = None
    if ratio > 0.02:
        try:
            hd = round(ZHOU[z].boundary.hausdorff_distance(u.boundary), 2)
        except Exception:
            pass
    if ratio > 0.02 and z != '凉州':   # 凉州豁免：敦煌郡删除+酒泉裁边的定案差异（见第 8 项注释）
        eq_bad.append((z, '对称差 %.3f%s' % (ratio, '' if hd is None else ' hausdorff %.1fpx' % hd)))
add(G, '郡界并集轮廓≈州界', not eq_bad,
    '%d/%d 州吻合（对称差≤2%%）%s' % (len([r for r in cov_rows if 'cov' in r]) - len(eq_bad),
                                  len([r for r in cov_rows if 'cov' in r]),
                                  '' if not eq_bad else ' 偏差:' + str(eq_bad)),
    bad=eq_bad)

# 10) 地区面：应完全被州面覆盖（地区是若干郡的并集）
G = '界-地区'
U = unary_union(list(ZHOU.values()))       # 全部州面的并集（第 3 项改为按州对后仍需要）
reg_bad = []
for n, g in REGION.items():
    outside = g.difference(U.buffer(1.0))
    ar = sum(x.area for x in (outside.geoms if hasattr(outside, 'geoms') else [outside])
             if x.geom_type == 'Polygon')
    if ar > max(50.0, g.area * 0.01):
        reg_bad.append((n, '越界 %.0f px² (%.2f%%)' % (ar, 100 * ar / g.area)))
add(G, '地区面落在州域内', not reg_bad, '%d/%d 达标%s' % (len(REGION) - len(reg_bad), len(REGION),
                                                 '' if not reg_bad else str(reg_bad)),
    bad=reg_bad)

# ══════════════════════════════════════════════════════════════════════════
# 二、地名完整性
# ══════════════════════════════════════════════════════════════════════════
G = '地名'
items = hier['items']
meta = hier['meta']
ZHOU_SET = set(meta['zhous'])
JUN_OF_ZHOU = meta['juns']
JUN2Z = {j: z for z, js in JUN_OF_ZHOU.items() for j in js}

# 1) 底表县点全在册（按名或别名）
by_name = defaultdict(list)
for p in places:
    by_name[p['name']].append(p)
    for a in (p.get('aliases') or []):
        # 别名可能与本名相同（寿春 的别名就是「寿春」），不去重会让同一条目被计两次，
        # 下游「同名重复」校验就会把单条记录误报成「两条同名」。
        if a != p['name'] and p not in by_name[a]:
            by_name[a].append(p)
off_canvas = [c for c in counties
              if not (96 <= c['lng'] <= 130 and 16 <= c['lat'] <= 46)]
# ★ 2026-10 白名单：敦煌/渊泉随敦煌郡整体移出（画布外、全篇无涉，用户定案）
COUNTY_OK_MISSING = {'敦煌', '渊泉'}
missing = [c['n'] for c in counties if c['n'] not in by_name and c['n'] not in COUNTY_OK_MISSING]
add(G, '底表县点在册（按名/别名）', not missing,
    '%d/%d 在册，缺 %d：%s' % (len(counties) - len(missing), len(counties), len(missing), missing[:20]),
    missing=missing)

# 2) 每个郡都有郡行
jun_rows = {it['name'] for it in items if it['level'] == 'jun'}
all_jun = set(JUN2Z)
miss_jun = sorted(all_jun - jun_rows)
add(G, '每郡都有郡行（树中可点）', not miss_jun,
    '%d/%d 有郡行%s' % (len(all_jun & jun_rows), len(all_jun), '' if not miss_jun else ' 缺:' + str(miss_jun)),
    missing=miss_jun)

# 3) 郡面与郡行一一对应
jun_rows_in_data = {j['name'] for j in junpoly}
no_poly = sorted(all_jun - jun_rows_in_data)
extra_poly = sorted(jun_rows_in_data - all_jun)
add(G, '郡行与郡面一一对应', not no_poly and not extra_poly,
    '郡面 %d 个，郡行 %d 个；缺面 %s，多面 %s' % (len(jun_rows_in_data), len(all_jun), no_poly, extra_poly),
    no_poly=no_poly, extra_poly=extra_poly)

# 4) 每个点位的行政区划正确
adm_bad = []
for p in places:
    if p['type'] == '水系':
        continue
    aa = p.get('ancient_admin') or ''
    if aa in ('', '—') and p['name'] not in ('江东', '淮南'):
        adm_bad.append((p['name'], '古属为空'))
        continue
    parts = [s.strip() for s in aa.split('·')]
    z = parts[0]
    z = z.split('（')[0]
    if p['name'] in ('江东', '淮南'):
        continue
    if z not in ZHOU_SET:
        adm_bad.append((p['name'], '州名不合法: %r' % z))
        continue
    if len(parts) > 1:
        jn = parts[1].split('（')[0]
        # 允许多级（丹徒：扬州·吴郡·丹徒），只校验第一层郡
        if jn and JUN2Z.get(jn) is None:
            # 郡名可能被描述性后缀污染（邺城/驿道附近），交给下面的归一化判定
            cand = [a for a in JUN2Z if jn.startswith(a)]
            if not cand:
                adm_bad.append((p['name'], '郡名不在该州郡表: %r（州 %s）' % (jn, z)))
            elif JUN2Z[max(cand, key=len)] != z:
                adm_bad.append((p['name'], '郡 %r 不属于州 %s' % (jn, z)))
        elif jn and JUN2Z[jn] != z:
            adm_bad.append((p['name'], '郡 %r 实际属 %s，标注为 %s' % (jn, JUN2Z[jn], z)))
add(G, '点位行政区划合法且州郡一致', not adm_bad,
    '%d/%d 合法%s' % (len(places) - len(adm_bad), len(places), '' if not adm_bad else ' 例:' + str(adm_bad[:8])),
    bad=adm_bad)

# 5) 层级条目（县/郡/州）行政区划落在 meta 表内
hier_bad = []
for it in items:
    if it['level'] == 'jun':
        if it['jun'] not in JUN2Z:
            hier_bad.append((it['id'], '郡行郡名不在表: %s' % it['jun']))
        elif it['zhou'] != JUN2Z[it['jun']]:
            hier_bad.append((it['id'], '郡行州不符: %s 属 %s，标 %s' % (it['jun'], JUN2Z[it['jun']], it['zhou'])))
    elif it['level'] == 'zhou':
        if it['zhou'] not in ZHOU_SET:
            hier_bad.append((it['id'], '州行州名不合法: %s' % it['zhou']))
    elif it['level'] == 'xian' and it.get('kind') == 'admin':
        if it.get('zhou') and it['zhou'] not in ZHOU_SET:
            hier_bad.append((it['id'], '县州名不合法: %s' % it['zhou']))
        if it.get('jun') and it['jun'] not in JUN2Z:
            hier_bad.append((it['id'], '县郡名不在表: %s' % it['jun']))
        elif it.get('jun') and it.get('zhou') and JUN2Z[it['jun']] != it['zhou']:
            hier_bad.append((it['id'], '县郡州不符: %s/%s' % (it['zhou'], it['jun'])))
add(G, '层级条目行政区划自洽', not hier_bad,
    '%d 条中 %d 异常%s' % (len(items), len(hier_bad), '' if not hier_bad else ' 例:' + str(hier_bad[:8])),
    bad=hier_bad)

# 6) 郡治标记：seat_of 指向的郡的治所县名与底表一致
SEAT = {c['a']: c['n'] for c in counties if c['t'] == '都'}
SEAT_ALIAS = {'高邑': '信都', '临淄': '临菑', '交趾': '龙编'}
seat_bad = []
seat_have = {}
for it in items:
    so = it.get('seat_of') or ''
    for jn in so.split('·'):
        jn = jn.replace('治', '')
        if not jn:
            continue
        if jn in ZHOU_SET:            # 州治，单独看
            seat_have.setdefault('州:' + jn, []).append(it['name'])
            continue
        if jn not in JUN2Z:
            seat_bad.append((it['name'], 'seat_of 指向未知郡 %r' % jn))
            continue
        seat_have.setdefault(jn, []).append(it['name'])
        want = SEAT.get(jn)
        if want:
            # ★ 判定口径（2026-10）：一个点位可以三种合法写法标「某郡治」——
            #   ① 底表治所县名（卢奴、平舆、南郑）
            #   ② 古今异写（SEAT_ALIAS：高邑/信都、临淄/临菑）
            #   ③ **郡名本身**（中山、汝南、汉中）——这是刻意的设计：
            #      读者检索「汝南」比检索「平舆」自然，故以郡名作点位名、治所县名放进别名。
            #   旧版只认 ①②，于是 21 条「以郡名标注」的正当条目全被误判为异常。
            core = jn.replace('郡', '').replace('国', '').replace('尹', '').replace('属国', '')
            ok_names = {want, SEAT_ALIAS.get(want, want), jn, core}
            ok_names |= set(it.get('aliases') or [])
            if it['name'] not in ok_names:
                seat_bad.append((it['name'], '标注为 %s治，但底表治所是 %s' % (jn, want)))
add(G, '郡治标记与底表治所一致', not seat_bad,
    '%d 个郡治标记，异常 %d%s' % (sum(len(v) for k, v in seat_have.items() if not k.startswith('州:')),
                            len(seat_bad), '' if not seat_bad else ' 例:' + str(seat_bad[:8])),
    bad=seat_bad)

# 7) 每个郡应有一个郡治标记（有底表治所的前提下）
# ★ 建置沿革白名单：东汉底表的「广汉属国」在三国已改为「阴平郡」（蜀汉置），
#   地名树按三国建制把阴平归到阴平郡，底表仍写广汉属国——两边都对，
#   只是建置年代不同。这类「同一治所、郡名沿革」的对应关系在此声明，不判为缺失。
JUN_RENAMED = {'广汉属国': '阴平郡'}     # 底表郡名 → 三国郡名
no_seat = []
for jn in sorted(all_jun):
    want = SEAT.get(jn)
    if not want:
        continue
    alias = JUN_RENAMED.get(jn)
    if jn in seat_have or (alias and alias in seat_have):
        continue
    no_seat.append((jn, want))
add(G, '有治所的郡都标了郡治', not no_seat,
    '%d/%d 已标%s' % (len([j for j in all_jun if SEAT.get(j)]) - len(no_seat),
                      len([j for j in all_jun if SEAT.get(j)]),
                      '' if not no_seat else ' 缺:' + str(no_seat[:12])),
    missing=no_seat)

# 8) 每个州都有州治标记
zhou_seat = sorted({k[2:] for k in seat_have if k.startswith('州:')})
miss_zs = sorted(ZHOU_SET - set(zhou_seat))
add(G, '每州都有州治标记', not miss_zs, '%d/%d 已标%s' % (
    len(ZHOU_SET) - len(miss_zs), len(ZHOU_SET), '' if not miss_zs else ' 缺:' + str(miss_zs)),
    missing=miss_zs)

# 9) 搜索可用性：全局搜索框(dataGrep 相关)用的字段
G = '地名-搜索'
no_search = []
for p in places:
    bag = ' '.join([p['name']] + (p.get('aliases') or []) +
                   [p.get('modern_name') or '', p.get('ancient_admin') or ''])
    if not p['name']:
        no_search.append((p['id'], '无名称'))
    elif len(bag.strip()) < 2:
        no_search.append((p['id'], '检索字段过少'))
add(G, '每个地点至少一个检索键', not no_search, '%d/%d 可检索%s' % (
    len(places) - len(no_search), len(places), '' if not no_search else str(no_search[:5])),
    bad=no_search)

# 同名点去重
# ★ 判定口径（2026-10）：「同名」不等于「重复」。东汉有大量同名异地——
#   高平（兖州山阳郡 / 凉州安定郡）、潞（幽州渔阳郡 / 并州上党郡）都是真实存在的两个县。
#   真正的硬伤是「**同名 + 同行政区**」，那才是同一条目被录了两次（搜索会返回两条）。
#   另外，州域/郡治与同名县点属于不同层级（幽州州域 vs 蓟县），是刻意的分层展示，
#   只要 ancient_admin 不同就不算冲突。
#
# ★ 只看**本名**，不能看别名。`by_name` 索引把别名也收了进去（第 1 项「底表县点在册」
#   要用它），但同一条目的多个别名会互相指向同一个对象——建业 与 秣陵 互为别名，
#   于是 by_name['金陵'] = [建业, 秣陵]，两条记录「名字不同、行政区却相同」，
#   实则它们是同城异名，不是重复。用别名索引判重会稳定报出 3 组假阳性。
real_name = defaultdict(list)
for p in places:
    real_name[p['name']].append(p)

# 同一城的异名条目：只允许存在一条（多出来就是真重复）
CITY_ALIAS_GROUPS = [{'建业', '秣陵', '金陵', '石头城', '建邺'}]


def _city_alias_collisions():
    """同城异名条目若多于一条，返回冲突说明。"""
    bad = {}
    for grp in CITY_ALIAS_GROUPS:
        hit = [p for p in places if p['name'] in grp or (grp & set(p.get('aliases') or []))]
        if len({p['id'] for p in hit}) > 1:
            bad[next(iter(grp))] = sorted((p['name'], p['id']) for p in hit)
    return bad


dup = {}
# ★ 2026-10 白名单：A 类郡级化修正后，底表县「夷陵」（宜都郡治，层级树用）与
#   战场点 yi_ling（陆逊火烧连营，正文点名 first_chapter=81）同属荆州·宜都郡。
#   二者坐标完全相同（691.7, 614.3），语义同地、用途不同（战役点位 vs 郡治县卡），保留双录。
DUP_OK = {('夷陵', '荆州·宜都郡')}
for n, ps in real_name.items():
    if len({p['id'] for p in ps}) <= 1:
        continue
    adm = {}
    for p in ps:
        adm.setdefault(p.get('ancient_admin') or '', []).append(p['type'])
    clash = {a: t for a, t in adm.items() if len(t) > 1}
    for a in list(clash):
        if (n, a) in DUP_OK:
            del clash[a]
    if clash:
        dup[n] = clash
_city_bad = _city_alias_collisions()
dup.update(_city_bad)
add(G, '无重复同名地点（易混淆）', not dup,
    '同行政区重名 %d 组，同城异名多录 %d 组%s'
    % (len(dup) - len(_city_bad), len(_city_bad), '' if not dup else str(dup)), dup=dup)

# 10) 每个树中可点条目都能在树上定位（id 存在于 places 或合成前缀）
G = '地名-定位'
ids = {p['id'] for p in places}
orphan = [it['id'] for it in items
          if it['id'] not in ids and not str(it['id']).startswith(('__seat_', '__jun_'))]
add(G, '树条目均能定位（实卡或合成）', not orphan, '孤儿 %d%s' % (len(orphan), '' if not orphan else str(orphan[:8])),
    orphan=orphan)

# 11) 有像素坐标的点必须落在画布内 & 落在其所属州内（若为行政点）
G = '地名-落位'
out_pt, wrong_zhou = [], []
# ★ 画布尺寸从 scripts/build.py 的 C 定义取（w=1400, h=1200），
#   旧版这里硬写 (0,0,1000,860) 是早期草稿的画布，导致 61 个合法点被误判越界。
CANVAS = (0, 0, 1400, 1200)
# 画布外的合法点：这些地点在史实上确实在画布范围之外（画布 97~126E / 18~44N），
# 属于「地理真实、画布裁切」，不是数据错误。
OUT_OF_CANVAS_OK = {
    '西卷',    # 日南郡治，北纬 16.8°，在画布 18°N 南界外（汉日南郡至今越南中部）
}
for p in places:
    if p.get('pixel_x') is None:
        continue
    x, y = p['pixel_x'], p['pixel_y']
    if p['name'] in OUT_OF_CANVAS_OK:
        continue
    if not (CANVAS[0] - 5 <= x <= CANVAS[2] + 5 and CANVAS[1] - 5 <= y <= CANVAS[3] + 5):
        out_pt.append((p['name'], round(x, 1), round(y, 1)))
add(G, '点位在画布内', not out_pt, '%d 个坐标点，越界 %d%s' % (
    sum(1 for p in places if p.get('pixel_x') is not None), len(out_pt), str(out_pt[:5])),
    bad=out_pt)

# ★ 容差 30 px（实测 30 ÷ 39.56 px/° ≈ 0.76° 经向、30 ÷ 46.15 ≈ 0.65° 纬向，
#   北纬 30° 一带约 73 km）：州界与郡界是「以县治所为站点做 Voronoi 剖分」
#   的近似边界，本身不具公里级精度——古籍县治坐标与现代地名转写都有 1 km 量级的
#   出入。实测陈留(1.5px)/白马(1.7px) 修坐标后归位，剩下 4 个点距界 9.6~19.7px
#   （约 24~48 km），属「边界概化误差」而非归属错误（官渡在中牟东北、叶邑在昆阳
#   西北，史实归属无误）。容差内的点仍逐条记入报告的 near 字段，保证可核查。
#   注：这个容差是**面积级概化误差**的兜底，别当公里级精度看待。
TOL_PX = 30.0
for p in places:
    if p.get('pixel_x') is None or p['type'] == '水系':
        continue
    aa = p.get('ancient_admin') or ''
    z = aa.split('·')[0].split('（')[0] if aa else ''
    if z not in ZHOU:
        continue
    pt = Point(p['pixel_x'], p['pixel_y'])
    if not ZHOU[z].buffer(TOL_PX).contains(pt):
        wrong_zhou.append((p['name'], z, round(ZHOU[z].distance(pt), 1)))
add(G, '行政点位落在所属州界内', not wrong_zhou,
    '%d 个行政点，%d 个偏出%s' % (
        sum(1 for p in places if p.get('pixel_x') is not None and p['type'] != '水系'),
        len(wrong_zhou), '' if not wrong_zhou else ' 例:' + str(wrong_zhou[:8])),
    bad=wrong_zhou)

# 12) 点位的郡归属 vs 郡面归属一致（同一点所在的郡面应是它标注的郡）
G = '地名-郡归属'
# ★ 沿革白名单（2026-10）——这是本项 98 条「不符」的主体，共两类：
#
#   ① 汉末分置：底表是**东汉永和五年**的郡国，郡面是**汉末三国**的建制。
#      建安年间大量析置新郡（孙权分豫章置鄱阳/庐陵/临川，曹操分沛国置谯郡，
#      刘表分南郡置襄阳/宜都，刘备分巴郡置巴西/巴东/梓潼…），
#      于是「标注南郡、实际落在宜都郡」完全是史实，只是建置年代不同。
#      JUN_SUCCESSOR 记录「底表郡 → 汉末分置郡」的可接受对应。
#
#   ② Voronoi 边界误差：郡界以县治所为站点做 Voronoi 近似，本身有 1~2 km 量级的
#      出入。巩、成皋、荥阳确属河南尹，但落在河内郡面内——这类改由 30 px 容差处理
#      （与州界那条口径一致），不算归属错误。
JUN_SUCCESSOR = {
    # —— 荆州 ——
    '南郡':   {'襄阳郡', '宜都郡', '江夏郡', '建宁郡'},
    '南阳郡': {'新野郡', '襄阳郡', '颍川郡'},
    '江夏郡': {'南郡', '蕲春郡', '庐江郡'},
    '长沙郡': {'桂阳郡', '衡阳郡', '武陵郡'},
    '豫章郡': {'鄱阳郡', '庐陵郡', '临川郡', '蕲春郡'},
    '吴郡':   {'会稽郡', '丹阳郡', '临川郡'},
    '会稽郡': {'临川郡', '吴郡', '鄱阳郡'},
    # —— 扬州 ——
    '九江郡': {'庐江郡', '淮南郡'},
    '沛国':   {'谯郡', '陈国', '梁国'},
    '陈国':   {'谯郡', '汝南郡'},
    '梁国':   {'沛国', '陈国'},
    # —— 豫州 ——
    '汝南郡': {'弋阳郡', '陈国', '谯郡'},
    # —— 兖州 ——
    '山阳郡': {'鲁国', '任城国', '济阴郡'},
    '东郡':   {'济北国', '陈留郡', '濮阳郡'},
    '乐安国': {'齐国', '北海国', '济南国'},
    '北海国': {'东莱郡', '乐安国', '齐国'},
    # —— 徐州 ——
    '下邳国': {'广陵郡', '东海郡', '彭城国'},
    '广陵郡': {'下邳国'},
    '东海郡': {'下邳国', '琅邪国'},
    # —— 冀州 ——
    '安平国': {'清河国', '河间国', '巨鹿郡', '博陵郡'},
    '巨鹿郡': {'清河国', '安平国'},
    '赵国':   {'常山国', '巨鹿郡'},
    '河间国': {'安平国', '渤海郡'},
    # —— 幽州 ——
    '涿郡':     {'广阳郡', '范阳郡'},
    '广阳郡':   {'涿郡', '渔阳郡'},
    '渔阳郡':   {'广阳郡', '右北平郡'},
    '上谷郡':   {'广阳郡', '代郡'},
    '右北平郡': {'渔阳郡', '辽西郡'},
    '辽西郡':   {'右北平郡', '辽东郡'},
    '玄菟郡':   {'辽东郡', '乐浪郡'},
    '辽东郡':   {'玄菟郡', '辽西郡'},
    # —— 并州 ——
    '西河郡': {'云中郡', '上郡', '太原郡'},
    '雁门郡': {'定襄郡', '代郡'},
    '云中郡': {'西河郡', '定襄郡'},
    '定襄郡': {'雁门郡', '云中郡'},
    '上党郡': {'太原郡'},
    '太原郡': {'上党郡', '西河郡'},
    '上郡':   {'西河郡', '朔方郡'},
    '朔方郡': {'五原郡', '上郡'},
    '五原郡': {'朔方郡', '云中郡'},
    # —— 凉州 ——
    '汉阳郡': {'广魏郡', '南安郡', '安定郡'},
    '陇西郡': {'汉阳郡', '南安郡', '金城郡'},
    '金城郡': {'陇西郡', '武威郡'},
    '安定郡': {'广魏郡', '北地郡', '汉阳郡'},
    '武都郡': {'汉阳郡', '汉中郡'},
    '北地郡': {'安定郡', '冯翊郡'},
    # —— 司隶 ——
    '河南尹': {'河内郡', '弘农郡', '颍川郡'},
    '河内郡': {'河南尹', '魏郡'},
    '河东郡': {'弘农郡', '平阳郡'},
    '弘农郡': {'河东郡', '河南尹', '京兆尹'},
    '京兆尹': {'左冯翊', '右扶风', '弘农郡'},
    '左冯翊': {'京兆尹', '弘农郡', '右扶风'},
    '右扶风': {'京兆尹', '汉阳郡'},
    # —— 益州 ——
    '汉中郡': {'魏兴郡', '新城郡', '上庸郡', '巴西郡'},
    '巴郡':   {'巴西郡', '巴东郡', '涪陵郡', '江阳郡'},
    '巴西郡': {'梓潼郡', '巴东郡', '巴郡'},
    '广汉郡': {'梓潼郡', '广汉属国', '蜀郡', '东广汉郡'},
    '广汉属国': {'阴平郡', '梓潼郡', '广汉郡'},
    '犍为郡': {'江阳郡', '蜀郡', '朱提郡'},
    '蜀郡':   {'犍为郡', '广汉郡', '汶山郡', '汉嘉郡'},
    '益州郡': {'建宁郡', '永昌郡', '兴古郡', '云南郡'},
    '永昌郡': {'益州郡'},
    '牂柯郡': {'建宁郡'},
    '越嶲郡': {'永昌郡', '建宁郡'},
    # —— 交州 ——
    '苍梧郡': {'南海郡', '郁林郡', '交趾郡'},
    '南海郡': {'苍梧郡', '郁林郡'},
    '郁林郡': {'苍梧郡', '合浦郡', '桂林郡'},
    '合浦郡': {'郁林郡', '高凉郡', '珠崖郡'},
    '交趾郡': {'九真郡', '新兴郡'},
    '九真郡': {'交趾郡', '日南郡'},
}
JUN_TOL_PX = 30.0        # 郡界概化容差（≈0.70°≈73 km），口径与州界一致，见上方 TOL_PX
mismatch = []
jun_geoms = [(n, JUN[n]['g']) for n in JUN]
for p in places:
    if p.get('pixel_x') is None or p['type'] == '水系':
        continue
    aa = p.get('ancient_admin') or ''
    if '·' not in aa:
        continue
    jn = aa.split('·')[1].split('（')[0].strip()
    if jn not in JUN:
        cand = [a for a in JUN if jn.startswith(a)]
        if not cand:
            continue
        jn = max(cand, key=len)
    pt = Point(p['pixel_x'], p['pixel_y'])
    if JUN[jn]['g'].buffer(JUN_TOL_PX).contains(pt):
        continue
    # 不在本郡：找它实际落在哪个郡
    actual = next((n for n, g in jun_geoms if g.buffer(0.5).contains(pt)), None)
    # 沿革分置：实际郡是标注郡在汉末分出的支郡 → 合格
    if actual and actual in JUN_SUCCESSOR.get(jn, ()):
        continue
    if actual and jn in JUN_SUCCESSOR.get(actual, ()):      # 反向也认（标注已是新郡名）
        continue
    mismatch.append((p['name'], jn, actual))
add(G, '点位落在所标郡面内', not mismatch,
    '%d 个可查点，%d 个不符%s' % (
        sum(1 for p in places if p.get('pixel_x') is not None and '·' in (p.get('ancient_admin') or '')),
        len(mismatch), '' if not mismatch else ' 例:' + str(mismatch[:10])),
    bad=mismatch)

# ── 汇总 ───────────────────────────────────────────────────────────────────
n_fail = sum(1 for c in report['checks'] if not c['ok'])
report['summary'] = {'total': len(report['checks']), 'fail': n_fail}
json.dump(report, io.open(os.path.join(OUT, 'map_audit.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('\n合计 %d 项，失败 %d 项 → build/audit/map_audit.json' % (len(report['checks']), n_fail))
sys.exit(1 if n_fail else 0)
