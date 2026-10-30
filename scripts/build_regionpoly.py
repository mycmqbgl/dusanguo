#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成「跨区域地理」分区多边形（画布像素坐标）→ build/regionpoly.json。

江东/淮南这类地理分区没有精确边界，用相关郡面（junpoly.json）并集近似：
  江东 = 扬州的 吴郡 + 会稽郡 + 丹阳郡 + 豫章郡   （长江下游南岸，孙策所平江东六郡的主体）
  淮南 = 扬州的 九江郡 + 庐江郡                 （淮河以南、长江以北）
依赖 scripts/build_junpoly.py 先跑出 build/junpoly.json。
注意：junpoly 的 pts 已是画布像素坐标（build_junpoly 内部投影），这里直接取用，勿再投影。
输出：[{n:名, pts:[[x,y]...], e:[[...]]}]（主环 + 飞地环）
"""
import json, io, os, re
from collections import defaultdict
from shapely.geometry import Polygon
from shapely.ops import unary_union

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def prj(lng, lat):
    return (round(lng, 1), round(lat, 1))   # junpoly 已是像素坐标，恒等透传

REGIONS = {
    # —— 跨郡（同州内）地理名词 ——
    # 江东（孙氏故地/演义口径）：含豫章全境及其析置的鄱阳、庐陵——
    # 不含鄱阳时它会把豫章与吴会隔开，并集断成两块
    '江东':   [('扬州', j) for j in ['吴郡', '会稽郡', '丹阳郡', '豫章郡', '鄱阳郡', '庐陵郡', '临川郡']],
    '淮南':   [('扬州', j) for j in ['九江郡', '庐江郡']],
    '关中':   [('司隶', j) for j in ['京兆尹', '左冯翊', '右扶风', '弘农郡']],
    '陇右':   [('凉州', j) for j in ['陇西郡', '汉阳郡', '金城郡', '安定郡', '广魏郡']],
    '河西':   [('凉州', j) for j in ['武威郡', '张掖郡', '张掖居延属国', '酒泉郡', '敦煌郡']],
    '荆襄':   [('荆州', j) for j in ['南阳郡', '南郡', '江夏郡', '襄阳郡', '新野郡']],
    '巴蜀':   [('益州', j) for j in ['巴郡', '巴东郡', '巴西郡', '梓潼郡', '蜀郡', '广汉郡',
                                     '广汉属国', '犍为郡', '江阳郡']],
    '南中':   [('益州', j) for j in ['牂柯郡', '益州郡', '永昌郡', '越嶲郡', '建宁郡', '朱提郡']],
    '辽东':   [('幽州', j) for j in ['辽东郡', '玄菟郡', '乐浪郡']],
    # —— 跨州地理名词 ——
    '河北':   ([('冀州', j) for j in ['魏郡', '巨鹿郡', '常山国', '中山国', '安平国', '河间国',
                                      '清河国', '渤海郡', '赵国']]
               + [('并州', j) for j in ['上党郡', '太原郡', '上郡', '西河郡', '雁门郡',
                                        '云中郡', '定襄郡', '五原郡', '朔方郡']]
               + [('幽州', j) for j in ['涿郡', '广阳郡', '代郡', '上谷郡', '渔阳郡',
                                        '右北平郡', '辽西郡']]),
    '中原':   ([('豫州', j) for j in ['颍川郡', '汝南郡', '梁国', '沛国', '陈国', '鲁国']]
               + [('兖州', j) for j in ['陈留郡', '东郡', '济阴郡', '山阳郡', '泰山郡',
                                        '东平国', '济北国', '任城国']]
               + [('司隶', '河南尹')]),
}

jun = json.load(open(os.path.join(ROOT, 'build/junpoly.json'), encoding='utf-8'))
by_name = defaultdict(list)
for j in jun:
    by_name[(j['zhou'], j['name'])].append(j)

out = []
for rn, spec in REGIONS.items():
    polys = []
    for zjn in spec:
        for j in by_name.get(zjn, []):
            rings = [j['pts']] + (j.get('extra') or [])
            for r in rings:
                if len(r) >= 3:
                    p = Polygon(r)
                    if p.is_valid and p.area > 0:
                        polys.append(p)
    if not polys:
        print('!! 无郡面可并：', rn); continue
    u = unary_union(polys).buffer(0)
    # 形态学闭合：跨州相邻郡面经逐面 simplify 后留有 ≤0.4px 的发丝裂缝，
    # 会让并集在拓扑上断成数块（前端看起来"地区裂开"）。先膨胀再收缩填缝。
    u = u.buffer(2.5).buffer(-2.5)
    gs = sorted([g for g in (u.geoms if hasattr(u, 'geoms') else [u]) if g.geom_type == 'Polygon'],
                key=lambda g: -g.area)
    main = gs[0]
    pts = [list(prj(*c)) for c in main.simplify(0.8, preserve_topology=True).exterior.coords]
    extra = [[list(prj(*c)) for c in g.simplify(0.8, preserve_topology=True).exterior.coords]
             for g in gs[1:3] if g.area > 200]
    out.append({'n': rn, 'pts': pts, 'e': extra})
    print(rn, '主环点数', len(pts), '飞地', len(extra))

json.dump(out, io.open(os.path.join(ROOT, 'build/regionpoly.json'), 'w', encoding='utf-8'),
          ensure_ascii=False)
print('完成 → build/regionpoly.json')
