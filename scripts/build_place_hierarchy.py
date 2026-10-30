#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""地名三级（州—郡—县）数据补齐 + 治所标记。

输出：data/places-hierarchy.json   {items:[{id, name, type, zhou, jun, level, seat_of}], meta:{...}}
- level: zhou / jun / xian ；非行政地名一律归 level=xian 且 kind='nonadmin'
- zhou / jun 用底表 data/counties-han.json 的州名、郡国名（与底图注记同源）
- 州治：州名同名点位（徐州、冀州…）或州内 tier=都 的县点
- 郡治：郡国名同名点位，或郡国内 tier=都 的县点
"""
import json, io, os, re, collections

import sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geo_const import EXTRA_JUN  # noqa: E402  —— 与 build_junpoly.py 同一份口径

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
places = json.load(open(os.path.join(ROOT, 'build/places.json'), encoding='utf-8'))
counties = json.load(open(os.path.join(ROOT, 'data/counties-han.json'), encoding='utf-8'))['counties']

ZHOU = collections.OrderedDict()          # 州 → 郡 list（保持底表出现顺序）
for c in counties:
    ZHOU.setdefault(c['p'], [])
    if c['a'] not in ZHOU[c['p']]:
        ZHOU[c['p']].append(c['a'])
# ★ 2026-10：敦煌郡不在画布内（lng<97）且全篇演义无涉，移出州郡树
#   （与 build_junpoly 的 DROP_JUN、places-additions 删行同步；县点位无正文引用）
ZHOU['凉州'] = [a for a in ZHOU.get('凉州', []) if a != '敦煌郡']
ADM2Z = {a: z for z, ls in ZHOU.items() for a in ls}
SEAT = {c['a']: c['n'] for c in counties if c['t'] == '都'}   # 郡 → 治所县名

# 东汉以后新置、但正文实际用到的郡——名单见 scripts/geo_const.py（含治所经纬）。
# 底表 101 郡国为顺帝永和五年（140）口径，不含这些；若只按永和旧制归属，
# 正文里的地名（如第 82 回「蜀兵已至宜都下寨」）会找不到所属郡。
# 例：宜都郡——正文出现 4 次（第 50、82 回），东汉末分南郡置，治夷陵。
ADM2Z.update(EXTRA_JUN)
# 治所县名的异写/后出称法 → 底表写法（东汉底表用古写：临菑、瘿陶、卢奴…）
SEAT_ALIAS = {
    '高邑': '信都',      # 冀州治（常山郡高邑，东汉属常山，此处按演义称法归冀州治）
    '临淄': '临菑',      # 青州治（齐国临菑）
    '交趾': '龙编',      # 交州治（交趾郡龙编）
    '西凉': None, '江左': None, '荆襄': None, '淮南郡': None, '司隶校尉部': None,
}
# 归属缺失的点位补全（依据《三国演义》语境与东汉郡国。
# ★ 2026-10 修正：三江口/七星坛原写「扬州·丹阳郡」——丹阳郡在长江以南（宛陵、泾县一带），
#   而这两个点都在鄂县/赤壁的江北江夏郡境内，按郡面实测均落江夏郡，故改归荆州·江夏郡。
#   彝陵原写南郡，但汉末吴已分南郡置宜都郡（夷陵即其治），seed 的 yi_ling 也标宜都郡，
#   底表 c_荆州_南郡_夷陵 才是永和旧制；此处按汉末实况归宜都郡。
#   巴丘原写南郡，实际在洞庭湖入江口（今岳阳），郡面实测落长沙郡。
FILL = {
    '彝陵': '荆州·宜都郡', '巴丘': '荆州·长沙郡', '油江口': '荆州·南郡',
    '陆口': '荆州·江夏郡', '樊口': '荆州·江夏郡', '三江口': '荆州·江夏郡',
    '汉津': '荆州·南郡', '七星坛': '荆州·江夏郡',
}
# 跨州水系：不属于单一州郡，保留为非行政县级条目
NA = {'长江', '黄河', '汉水'}

name2p = collections.defaultdict(list)
for p in places:
    name2p[p['name']].append(p)

def norm_adm(p):
    aa = FILL.get(p['name']) or p.get('ancient_admin') or ''
    if not aa or aa in ('—',):
        return None, None
    z = aa.split('·')[0]
    z = re.sub(r'（.*?）$', '', z)
    jun = aa.split('·')[1] if '·' in aa else None
    if jun == '襄阳':
        jun = '南郡'
    if jun:
        jun = re.sub(r'[（(].*?[）)]$', '', jun)     # 去「驿道附近」等括注
        jun = re.sub(r'(东|西|南|北|以?东|以?西|以?南|以?北)(境|界)?$', '', jun)
        # 只认底表里的真实郡国；「魏郡邺城」「巨鹿郡界」这类复合描述要拆
        if jun not in ADM2Z:
            cand = [a for a in ADM2Z if jun.startswith(a)]
            jun = max(cand, key=len) if cand else None
        # 郡必须真属于该州：底表查不到或归属不符 → 弃郡留州
        if jun and ADM2Z.get(jun) != z:
            jun = None
    return z, jun

items = []
SEAT_JUN = set()        # 已由同名点位充当郡治的郡（其郡行稍后统一补）
for p in places:
    z, jun = norm_adm(p)
    if p['name'] in NA:
        z, jun = None, None
    # 跨区域地理：江东、淮南这类是「地理分区」而非「行政州」。
    # 与州分层展示（level='region'），不参与州界高亮、不冒充州节点；
    # zhou 仅保留「大体属哪个州」的参考值，前端在独立分组内呈现。
    REGION = {'江东': '扬州', '淮南': '扬州'}
    if p['name'] in REGION:
        items.append({'id': p['id'], 'name': p['name'], 'type': p['type'],
                      'zhou': None, 'jun': None, 'region_of': REGION[p['name']],
                      'level': 'region', 'kind': 'alias', 'seat_of': None,
                      'aliases': p.get('aliases') or []})
        continue
    if p['type'] == '州域' or p['name'] in ZHOU:
        items.append({'id': p['id'], 'name': p['name'], 'type': p['type'],
                      'zhou': p['name'] if p['name'] in ZHOU else z, 'jun': None,
                      'level': 'zhou', 'kind': 'admin', 'seat_of': None,
                      'aliases': p.get('aliases') or []})
        continue
    # 郡级：名字就是郡国名（涿郡/吴郡…）或与郡名同字（颍川/巨鹿/中山… 郡治县与郡同名）
    # 关键：郡本身是「行政区」，县点是「地点」。同名时不能合并成一条——
    # 郡行（无卡，点它亮郡界）与郡治县行（有卡，点它落红点）必须拆开：
    #   郡  → 合成条目 id='__jun_<郡名>'，无像素坐标，seat_of=None
    #   县  → 沿用原点位，level='xian'，seat_of='<郡>治'
    bare = re.sub(r'[郡国]$', '', p['name'])
    hit = next((a for a in ADM2Z if re.sub(r'[郡国]$', '', a) == bare), None)
    if hit:
        items.append({'id': p['id'], 'name': p['name'], 'type': p['type'],
                      'zhou': ADM2Z[hit], 'jun': hit,
                      'level': 'xian', 'kind': 'admin', 'seat_of': hit + '治',
                      'pixel_x': p.get('pixel_x'), 'pixel_y': p.get('pixel_y'),
                      'aliases': p.get('aliases') or []})
        SEAT_JUN.add(hit)          # 该郡已有实卡郡治，稍后只需补郡行
        continue
    # 县级（含非行政地名）
    admin = p['type'] in ('郡治', '县', '州治')     # 行政县级：都城/城 等仍视作非行政地名
    items.append({'id': p['id'], 'name': p['name'], 'type': p['type'],
                  'zhou': z, 'jun': jun,
                  'level': 'xian', 'kind': 'admin' if admin else 'nonadmin', 'seat_of': None,
                  # ★ 县级也要带别名：州治/郡治循环按 `x['name'] in _want or (_want & aliases)`
                  #   找目标条目，缺 aliases 时「汝南」这类以郡名在册、治所县名放在别名的
                  #   条目永远匹配不上，州治徽标就挂不上去。原先只有郡级/州级/region
                  #   三种分支带了 aliases，县级漏了。
                  'aliases': p.get('aliases') or [],
                  'lng': p.get('lng'), 'lat': p.get('lat'),
                  'pixel_x': p.get('pixel_x'), 'pixel_y': p.get('pixel_y')})

# ---- 治所标记：先按「名字=州/郡名」，再按「州/郡内 tier=都 的县点」 ----
# 州治：徽标只标在州治县点（列在其所属郡下），州名行不再标——
# 「冀州」后面挂「州治」语义不通，州治是县（信都/姑臧…）不是州。
# 州治县不在 places 种子里时（阳翟/信都/姑臧/宛陵/龙编），用底表县坐标合成条目。
# 与 build_regionpoly 相同的经纬→像素拟合（places 精确点最小二乘）
import numpy as np
_pts = [(p['lng'], p['lat'], p['pixel_x'], p['pixel_y']) for p in places
        if p.get('pixel_x') is not None and p.get('coord_precision') == '精确']
A = np.array([[_p[0], 1] for _p in _pts]); BX = np.array([_p[2] for _p in _pts])
AX, BXS = np.linalg.lstsq(A, BX, rcond=None)[0]
A2 = np.array([[_p[1], 1] for _p in _pts]); BY = np.array([_p[3] for _p in _pts])
AY, BYS = np.linalg.lstsq(A2, BY, rcond=None)[0]

seat_items = []
# 汉末州治「迁移」覆盖表：底表（永和五年）的州治与汉末实况不同，且部分州治
# 所在的郡在底表里不存在（襄阳郡、谯郡是汉末新置）。仅靠「本州各郡 tier=都」
# 找州治会漏掉这几个州，于是「每州都有州治标记」永远差 3 个。
# 这里按《后汉书·郡国志》及汉末实况显式给出：
#   扬州 → 寿春（袁术据淮南后州治迁寿春；旧治历阳/阴陵）
#   荆州 → 襄阳（刘表徙治襄阳；旧治汉寿）
#   豫州 → 平舆（汝南郡平舆，刺史部常驻）
ZHOU_SEAT_OVERRIDE = {'扬州': '寿春', '荆州': '襄阳', '豫州': '平舆'}
for it in items:
    if it['level'] == 'zhou':
        nm = it['name']
        if nm not in ZHOU:      # 非州名（跨区域地理已单列 region，不进本循环）
            continue
        # 治所县名：优先用覆盖表，否则取本州各郡国的 tier=都 县名
        _ov = ZHOU_SEAT_OVERRIDE.get(nm)
        if _ov:
            seats = {_ov}
        else:
            seats = {SEAT.get(a) for a in ZHOU[nm]}
        al = set(it.get('aliases') or [])
        hit = al & seats                                  # 别名即州治（如 兖州·昌邑、徐州·彭城）
        seat_alias = None
        if not hit:
            for a in al:
                v = SEAT_ALIAS.get(a)
                if v and v in seats:
                    hit = {v}; seat_alias = a             # 保留读者熟悉的称法
                    break
        if not hit:
            continue
        county = sorted(hit)[0]                            # 底表写法：信都/临菑/龙编…
        # 治所县所在郡（底表 tier=都）
        cj = next((c['a'] for c in counties if c['p'] == nm and c['t'] == '都' and c['n'] == county), None)
        # 在册县点：直接把州治徽标挪过去（保留原有郡治徽标，用「·」连接）
        # ★ 匹配要含别名：州治县常以「郡名」形式在册（汝南 的别名里有 平舆），
        #   只比 name 会找不到，于是豫州永远缺州治徽标。
        _want = {county} | ({seat_alias} if seat_alias else set())
        tgt = [x for x in items if x['level'] == 'xian' and x['zhou'] == nm
               and (x['name'] in _want or (_want & set(x.get('aliases') or [])))]
        tgt.sort(key=lambda x: x['name'] != seat_alias)    # 优先用演义称法那条
        if tgt:
            tgt[0]['seat_of'] = (tgt[0]['seat_of'] + '·' + nm + '治') if tgt[0]['seat_of'] else nm + '治'
            continue
        # 不在册：合成州治县条目（坐标取底表县位，投影成像素），挂在治所郡下
        cc = next((c for c in counties if c['p'] == nm and c['t'] == '都' and c['n'] == county), None)
        if cc is None or cj is None:
            continue
        px = round(AX * cc['lng'] + BXS, 1)
        py = round(AY * cc['lat'] + BYS, 1)
        seat_items.append({'id': '__seat_' + nm, 'name': seat_alias or county,
                           'type': '州治', 'zhou': nm, 'jun': cj, 'level': 'xian',
                           'kind': 'admin', 'seat_of': nm + '治',
                           'lng': cc['lng'], 'lat': cc['lat'],
                           'pixel_x': px, 'pixel_y': py,
                           'modern_name': '', 'mention_count': 0, 'first_chapter': None})
items.extend(seat_items)
# 郡治：郡名同名点位已标 level=jun 的，若该郡县点在册且 tier=都，则给县点标郡治
# ★ 2026-10：这里原来写的是 `if tgt and not tgt[0]['seat_of']`——
#   但州治是**先**标的，一个县同时是州治和郡治时（蓟=幽州治+广阳郡治、
#   彭城=徐州治+彭城国治、雒阳=司隶治+河南尹治、临菑=青州治+齐国治、
#   龙编=交州治+交趾郡治、阴平=益州治+广汉属国治），郡治这一步就被跳过，
#   于是「有治所的郡都标了郡治」永远差这 6 个。改为用「·」拼接两枚徽标。
for z, juns in ZHOU.items():
    for a in juns:
        seat = SEAT.get(a)
        if not seat: continue
        tgt = [x for x in items if x['zhou'] == z and x['jun'] == a and x['name'] == seat and x['level'] == 'xian']
        if not tgt:
            continue
        cur = tgt[0].get('seat_of') or ''
        tags = [t for t in cur.split('·') if t]
        mine = a + '治'
        if mine not in tags:
            tags.append(mine)
            tgt[0]['seat_of'] = '·'.join(tags)

# 修正：所有郡国都要有独立郡行（无卡，点它亮郡界，不落红点）。
# 名字用底表郡国全名（颍川郡/中山国/京兆尹…），与底图 junpoly 注记同源。
_jun_rows = []
for z, ls in ZHOU.items():
    for a in ls:
        _jun_rows.append(a)
for a in EXTRA_JUN:
    if a not in _jun_rows:
        _jun_rows.append(a)
for a in _jun_rows:
    z = ADM2Z.get(a)
    if not z:
        continue
    items.append({'id': '__jun_' + a, 'name': a, 'type': '郡', 'zhou': z, 'jun': a,
                  'level': 'jun', 'kind': 'admin', 'seat_of': None})

_all_juns = {}
for z, ls in ZHOU.items():
    _all_juns[z] = sorted(set(ls) | {a for a, zz in EXTRA_JUN.items() if zz == z})
out = {'meta': {'zhous': list(ZHOU.keys()), 'juns': _all_juns,
                'note': '三级归属：州来自 places.ancient_admin 与 counties-han 州名；郡来自 ancient_admin 第二段或郡名同名点位；非行政地名归 level=xian, kind=nonadmin。'},
       'items': items}
io.open(os.path.join(ROOT, 'data/places-hierarchy.json'), 'w', encoding='utf-8').write(
    json.dumps(out, ensure_ascii=False, indent=1))

# ---- 自检 ----
c = collections.Counter((it['level'], it['kind']) for it in items)
print('分布:', dict(c))
bad = [it['name'] for it in items if it['level'] in ('jun','xian') and not it['jun']]
print('缺郡归属:', bad)
seat = [(it['name'], it['seat_of']) for it in items if it['seat_of']]
print('治所标记', len(seat), seat[:30])
EOF_OUT = None
