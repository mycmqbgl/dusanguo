# -*- coding: utf-8 -*-
"""P2 谭图配准 · 底图数据处理（P2-R 细化版）

数据源：
  data/ne/ne_10m_coastline.geojson            Natural Earth 10m 海岸线
  data/ne/ne_10m_rivers_lake_centerlines.geojson  10m 河流
  data/ne/ne_10m_lakes.geojson                10m 湖泊

处理：
  1. 裁剪到画布范围外扩（95–130E / 16–46N）
  2. Douglas-Peucker 简化（海岸 0.012°，大河 0.01°，小河 0.006°——比 50m 版细一倍以上）
  3. 河流白名单筛选 + 中文名映射（10m 命名），同名河支持多段（如郁水=西江+郁江+北江+东江）
  4. 手工修正与东汉不符的现代河道：
     - 黄河下游改东汉故道（荥阳—濮阳—聊城—沧州入海）
     - 补 10m 数据缺的历史名川：泗水、济水、洛水、淝水、滹沱、资水、湟水、淯水、岷水上游
  5. 湖泊白名单（太湖/巢湖/洞庭/西海）+ 手工补古湖（巨野泽/滇池/洱海/居延泽）；
     跳过彭蠡（汉代彭蠡在江北、非现代鄱阳湖位置）、洪泽（唐代后形成）
输出 data/geo-real.json（经纬度折线/多边形，build.py 负责投影）。
"""
import json, io, math, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NE = os.path.join(ROOT, 'data', 'ne')
BBOX = (95.0, 16.0, 130.0, 46.0)

# ---------------------------------------------------------------- 简化/裁剪
def dp(pts, tol):
    if len(pts) < 3:
        return pts
    def d(p, a, b):
        ax, ay = a; bx, by = b; px, py = p
        dx, dy = bx - ax, by - ay
        if dx == dy == 0:
            return math.hypot(px - ax, py - ay)
        t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        return math.hypot(px - (ax + t * dx), py - (ay + t * dy))
    dmax, idx = 0, 0
    for i in range(1, len(pts) - 1):
        dist = d(pts[i], pts[0], pts[-1])
        if dist > dmax:
            dmax, idx = dist, i
    if dmax > tol:
        left, right = dp(pts[:idx + 1], tol), dp(pts[idx:], tol)
        return left[:-1] + right
    return [pts[0], pts[-1]]

def in_bbox(p):
    return BBOX[0] <= p[0] <= BBOX[2] and BBOX[1] <= p[1] <= BBOX[3]

def seg_len(pts):
    """折线长度（经度按 cos31° 折算）"""
    return sum(math.hypot((pts[i + 1][0] - pts[i][0]) * 0.86, pts[i + 1][1] - pts[i][1])
               for i in range(len(pts) - 1))

def dist(a, b):
    return math.hypot((a[0] - b[0]) * 0.86, a[1] - b[1])

def densify(pts, step=0.12, wiggle=0.0):
    """沿折线每 step（纬度度）插值加密；wiggle>0 时叠加确定性微起伏
    （两个不同波长的正弦，模拟海岸/河岸的自然弯曲，避免长直弦观感）"""
    if len(pts) < 2:
        return [list(p) for p in pts]
    out = [list(pts[0])]
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        d = math.hypot(dx * 0.86, dy)
        n = max(1, int(d / step))
        px, py = -dy, dx * 0.86                    # 左法线
        pl = math.hypot(px, py) or 1.0
        for j in range(1, n + 1):
            t = j / n
            w = 0.0
            if wiggle:
                gt = (i + t)
                w = wiggle * (0.6 * math.sin(gt * 9.0) + 0.4 * math.sin(gt * 23.0 + 1.7))
            out.append([a[0] + dx * t + px / pl * w, a[1] + dy * t + py / pl * w])
    return out

def smooth(pts, n=10):
    """Catmull-Rom 细分：手工折线 → 平滑曲线（消除直线段观感）"""
    if len(pts) < 3:
        return [list(p) for p in pts]
    P = [pts[0]] + [list(p) for p in pts] + [pts[-1]]
    out = [[round(pts[0][0], 3), round(pts[0][1], 3)]]
    for i in range(len(P) - 3):
        p0, p1, p2, p3 = P[i], P[i + 1], P[i + 2], P[i + 3]
        for j in range(1, n + 1):
            t = j / n; t2 = t * t; t3 = t2 * t
            x = 0.5 * (2 * p1[0] + (-p0[0] + p2[0]) * t
                       + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * (2 * p1[1] + (-p0[1] + p2[1]) * t
                       + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            out.append([round(x, 3), round(y, 3)])
    return out

def chain(segs, tol=0.08):
    """把同一河流的多段按端点远近首尾相接，得到连续干流"""
    if not segs:
        return []
    segs = [list(s) for s in segs]
    segs.sort(key=lambda s: -seg_len(s))
    line = segs.pop(0)
    while segs:
        best, bi, rev = None, -1, False
        for i, s in enumerate(segs):
            dh, dt = dist(line[-1], s[0]), dist(line[-1], s[-1])
            dmin = min(dh, dt)
            if dmin < tol and (best is None or dmin < best):
                best, bi, rev = dmin, i, dt < dh
        if bi < 0:
            break
        s = segs.pop(bi)
        line += (s[::-1] if rev else s)[1:]
    return line

def clip_line(coords):
    segs, cur = [], []
    for p in coords:
        if in_bbox(p):
            cur.append([round(p[0], 3), round(p[1], 3)])
        elif cur:
            if len(cur) >= 2:
                segs.append(cur)
            cur = []
    if len(cur) >= 2:
        segs.append(cur)
    return segs

# ---------------------------------------------------------------- 海岸线
# 东汉海岸修正：1128 年黄河南夺淮河与长江口东延，是两千年来最大的两处海岸淤进。
# zones: (名, box(x0,y0,x1,y1), 手工汉代海岸控制点) —— 手工点首尾用折线与区域
# 边界的实际交点衔接（平滑后无缝），整段落入区域的小段（崇明等沙洲小岛）直接
# 丢弃：东汉尚未成陆。
COAST_ZONES = [
  ('渤海湾', (117.0, 36.9, 119.65, 39.7), [
   [[119.3,37.45],[118.9,37.5],[118.55,37.7],[118.3,38.0],[118.05,38.3],[117.85,38.55],
    [117.65,38.8],[117.5,39.05],[117.35,39.3],[117.28,39.5]]]),
  ('苏北', (119.35, 32.3, 121.0, 35.1), [
   [[119.6,34.75],[119.7,34.4],[119.78,34.0],[119.83,33.5],[119.88,33.0],[119.93,32.7],
    [120.02,32.5]]]),
  # 长三角：巨长海岸线在江阴折返（河口头），南岸/北岸各一段手工线
  ('长三角', (120.2, 30.2, 122.3, 32.8), [
   [[120.45,30.85],[120.6,31.15],[120.62,31.5],[120.62,31.75]],        # 南岸：冈身（嘉定—奉贤一线）
   [[120.3,32.1],[120.4,32.3],[120.5,32.45],[120.65,32.55]]]),         # 北岸：泰兴—如皋—海安西
]

def _in_box(p, box):
    return box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3]

def sub_coast_zone(pts, box, hands):
    """折线在矩形区域内的部分 → 手工汉代海岸线。
    巨长的大陆海岸线会在区域内多次进出（海湾/岛链/河口折返），取所有 ≥60 点的
    连续穿越段，按长度降序配给 hands（长江口南岸/北岸各配一条）；其余小段保留
    （海湾弯守现代形状）；整段都在区域内的小段（崇明等沙洲小岛）丢弃。"""
    def inb(p):
        return _in_box(p, box)
    if all(inb(p) for p in pts):
        return []
    runs, i = [], 0
    while i < len(pts):
        if inb(pts[i]):
            j = i
            while j + 1 < len(pts) and inb(pts[j + 1]):
                j += 1
            runs.append((i, j))
            i = j + 1
        else:
            i += 1
    if not runs:
        return [pts]
    runs = sorted((r for r in runs if r[1] - r[0] + 1 >= 60), key=lambda r: -(r[1] - r[0]))
    runs = runs[:len(hands)]
    if not runs:
        return [pts]
    runs.sort()
    out, prev = [], 0
    for k, (a, b) in enumerate(runs):
        out += pts[prev:a]
        hand = hands[min(k, len(hands) - 1)]
        out += smooth(densify([pts[a - 1]] + hand + [pts[b + 1]], 0.12, wiggle=0.028), 6)[1:] if a > 0 and b + 1 < len(pts) \
            else [list(q) for q in hand]
        prev = b + 1
    out += pts[prev:]
    return [out]

def build_coast():
    d = json.load(io.open(os.path.join(NE, 'ne_10m_coastline.geojson'), encoding='utf-8'))
    segs = []
    for ft in d['features']:
        g = ft['geometry']
        lines = [g['coordinates']] if g['type'] == 'LineString' else g['coordinates']
        for ln in lines:
            segs += clip_line(ln)
    for name, box, hands in COAST_ZONES:
        nxt = []
        n_island = 0
        for s in segs:
            r = sub_coast_zone(s, box, hands)
            for x in r:
                nxt.append(x)
            if not r:
                n_island += 1
        print('海岸修正[%s]：%d 小段丢弃' % (name, n_island))
        segs = nxt
    out = [dp(s, 0.006) for s in segs]
    out = [s for s in out if len(s) >= 3]
    for name, box, _ in COAST_ZONES:     # 断言：拼接区内无异常长跳（域外原生稀疏不管）
        for seg in out:
            for i in range(len(seg) - 1):
                a, b = seg[i], seg[i + 1]
                if _in_box(a, box) and _in_box(b, box):
                    d = math.hypot((b[0] - a[0]) * 0.86, b[1] - a[1])
                    assert d < 0.6, '海岸线异常长跳 %.2f° at %s [%s]' % (d, a, name)
    return out

# ---------------------------------------------------------------- 河流
# NE 10m name → (中文名, 线宽, 最东经过滤(None=不过滤))
RIVER_MAP = {
    'Jinsha': ('泸水', 1.6, None),        # 金沙江，古称泸水（五月渡泸）
    'Yalong': ('若水', 1.2, None),
    'Nu': ('怒水', 1.4, None), 'Salween': ('怒水', 1.4, None),
    'Lancang': ('澜沧水', 1.4, None), 'Mekong': ('澜沧水', 1.4, None),
    'Hong': ('富良江', 1.4, None),
    'Chang Jiang': ('长江', 3.0, None),
    'Yangtze': ('长江', 3.0, None),      # NE 10m 长江干流分段命名为 Yangtze
    'Han': ('汉水', 2.2, 120.0),          # 排除朝鲜半岛同名的汉江
    'Yuan': ('沅水', 1.6, None), 'Xiang': ('湘水', 1.6, None),
    'Wu': ('乌江', 1.4, None),
    'Nanpan': ('盘江', 1.2, None), 'Hongshui': ('盘江', 1.2, None),
    'Jialing': ('阆水', 1.4, None),
    'Dadu': ('大渡', 1.2, None),
    'Gan': ('赣水', 1.8, None), 'Tuo': ('沱水', 1.2, None),
    'Wei': ('渭水', 1.8, None), 'Fen': ('汾水', 1.6, None),
    'Liao': ('辽水', 1.8, None), 'Xiliao': ('西辽水', 1.4, None),
    'Songhua': ('粟末水', 1.2, None),
    'Min': ('岷水', 1.4, 106.0),          # 排除福建闽江（NE 同名 Min）
    'Xi': ('郁水', 1.8, None), 'Yu': ('郁水', 1.8, None),
    'Bei': ('郁水', 1.4, None), 'Dong': ('郁水', 1.2, None),
    'Ou': ('瓯水', 1.2, None), 'Fuchun': ('浙江', 1.4, None),
    'Qin': ('沁水', 1.4, None), 'Zhang': ('漳水', 1.6, None),
    'Jing': ('泾水', 1.4, None), 'Yi': ('沂水', 1.2, None),
    'Ying': ('颍水', 1.2, None), 'Dan': ('丹水', 1.2, None),
    'Sanggan': ('桑干水', 1.2, None), 'Daling': ('白狼水', 1.2, None),
    'Yalu': ('马訾水', 1.2, None),
    'Luan': ('濡水', 1.6, None),          # 滦河，右北平/辽西
    'Shandian': ('濡水', 1.0, None),      # 闪电河（濡水上游）
    'Xar Moron': ('饶乐水', 1.2, None),   # 西拉木伦河，乌桓/鲜卑
    'Tao’er': ('太鲁水', 1.0, None),      # 洮儿河，东部鲜卑
    'Di’er Songhua': ('粟末水', 1.2, None),
    'Erdao': ('粟末水', 1.0, None),
    'Yongding': ('㶟水', 1.4, None),      # 永定河，汉称治水/㶟水，蓟城所倚
    'Wuding': ('奢延水', 1.0, None),      # 无定河，上郡
    'You': ('郁水', 1.2, None), 'Zuo': ('郁水', 1.0, None),
    'Xun': ('郁水', 1.2, None), 'Rong': ('郁水', 1.0, None),
    'Mei': ('赣水', 1.0, None),
    'Huai': ('淮水', 2.2, None),
}

WATER = '#6f8fa3'   # 江河湖海统一水体色，主次靠线宽区分

# 东汉黄河下游故道（禹河）：荥阳以东—濮阳—聊城—德州—沧州—天津南入渤海。
# 控制点只约束走向，输出前做 Catmull-Rom 平滑，避免出现直线段。
HUANG_HAN = [
    [114.83, 35.02], [115.05, 35.35], [115.30, 35.62], [115.60, 35.95], [115.95, 36.42],
    [116.18, 36.92], [116.42, 37.32], [116.72, 37.85], [116.95, 38.25], [117.08, 38.62],
    [117.22, 38.92], [117.40, 39.02],
]

HAND_RIVERS = {
    # 汝水（汝南郡所倚，袁绍本籍）
    '汝水': {'w': 1.5, 'pts': [
        [112.45, 34.05], [112.9, 33.95], [113.45, 33.85], [113.95, 33.6], [114.3, 33.3],
        [114.6, 32.98], [114.95, 32.78], [115.3, 32.6], [115.6, 32.42],
    ]},
    # 涡水（谯—涡阳—怀远入淮，曹操本籍水系）
    '涡水': {'w': 1.4, 'pts': [
        [114.15, 34.72], [114.35, 34.35], [114.55, 34.08], [114.9, 33.98], [115.3, 33.88],
        [115.75, 33.72], [116.2, 33.62], [116.62, 33.38], [117.0, 33.1], [117.25, 32.95],
    ]},
    # 10m 数据缺的历史名川
    '泗水': {'color': '#6f8fa3', 'w': 1.6, 'pts': [
        [117.2, 35.65], [117.0, 35.6], [116.6, 35.4], [116.8, 35.1], [116.9, 34.75],
        [117.2, 34.6], [117.6, 34.45], [118.0, 34.3], [118.3, 33.9], [118.6, 33.8],
    ]},
    # 济水：荥阳—封丘—定陶—巨野泽—泰山北—千乘入海（四渎之一，官渡一带水系）
    '济水': {'color': '#6f8fa3', 'w': 1.5, 'pts': [
        [113.45, 34.95], [113.8, 35.15], [114.4, 35.25], [115.0, 35.35], [115.5, 35.4],
        [116.0, 35.35], [116.2, 35.35], [116.5, 36.0], [116.55, 36.5], [117.0, 36.7],
        [117.5, 36.9], [118.0, 37.1], [118.45, 37.35], [118.85, 37.5],
    ]},
    '洛水': {'color': '#6f8fa3', 'w': 1.4, 'pts': [
        [109.8, 34.15], [110.9, 34.35], [111.9, 34.5], [112.4, 34.7], [112.9, 34.75], [113.0, 34.8],
    ]},
    # 淝水（施水）：合肥—寿春入淮，合肥之战的关键水系
    '淝水': {'color': '#6f8fa3', 'w': 1.2, 'pts': [
        [117.3, 31.85], [117.2, 32.1], [117.05, 32.3], [116.9, 32.45], [116.78, 32.55],
    ]},
    '滹沱水': {'color': '#6f8fa3', 'w': 1.2, 'pts': [
        [112.9, 38.45], [113.6, 38.35], [114.4, 38.28], [115.0, 38.15], [115.6, 38.15], [116.2, 38.3],
    ]},
    '资水': {'color': '#6f8fa3', 'w': 1.2, 'pts': [
        [111.0, 26.3], [111.4, 27.0], [111.5, 27.6], [112.0, 28.2], [112.25, 28.5],
    ]},
    '湟水': {'color': '#6f8fa3', 'w': 1.2, 'pts': [
        [101.4, 36.75], [101.9, 36.7], [102.4, 36.55], [102.9, 36.45], [103.5, 36.35],
    ]},
    # 淯水（白河）：宛城所在水系
    '淯水': {'color': '#6f8fa3', 'w': 1.1, 'pts': [
        [112.1, 33.55], [112.35, 33.25], [112.5, 33.0], [112.55, 32.85],
    ]},
    # 岷江上游（都江堰—成都—彭山），接 NE 段（乐山以下）
    '岷水': {'color': '#6f8fa3', 'w': 1.4, 'pts': [
        [103.65, 31.35], [103.6, 31.0], [103.7, 30.6], [103.85, 30.2], [103.75, 29.55],
    ]},
}

def build_huang(feats):
    """黄河：NE 真实河道（源区—河套—晋陕—潼关—荥阳）+ 平滑的东汉故道下游。
    丢弃 1855 年后的现代下游（郑州以东走济南入海），改走禹河故道。"""
    segs = []
    for ft in feats:
        p = ft['properties']; g = ft['geometry']
        if p.get('name') != 'Huang' or p.get('featurecla') != 'River':
            continue
        lines = [g['coordinates']] if g['type'] == 'LineString' else g['coordinates']
        for ln in lines:
            for s in clip_line(ln):
                if len(s) < 6:
                    continue
                if min(q[0] for q in s) > 114.6 and max(q[1] for q in s) > 36.5:
                    continue      # 现代下游（济南—东营）
                segs.append([list(q) for q in s])
    line = chain(segs, 0.16)
    if not line:
        return smooth([[98.0, 35.1]] + HUANG_HAN, 10)
    k = min(range(len(line)), key=lambda i: dist(line[i], HUANG_HAN[0]))
    up = dp(line[:k + 1], 0.006)
    down = smooth(HUANG_HAN, 10)
    return up + down[1:]

def build_rivers():
    feats = list(json.load(io.open(os.path.join(NE, 'ne_10m_rivers_lake_centerlines.geojson'),
                                   encoding='utf-8'))['features'])
    huang = build_huang(feats)
    got = {}    # 中文名 → [(长度, pts)]
    auto = []   # 无古称的长河：只画线不标名
    for ft in feats:
        p = ft['properties']; g = ft['geometry']
        if p.get('featurecla') != 'River':
            continue
        name = p.get('name')
        if name == 'Huang':
            continue
        zh, w, maxlng = RIVER_MAP.get(name, (None, 1.0, None))
        lines = [g['coordinates']] if g['type'] == 'LineString' else g['coordinates']
        for ln in lines:
            for s in clip_line(ln):
                if len(s) < 6:
                    continue
                L = seg_len(s)
                if maxlng is not None and max(q[0] for q in s) > maxlng:
                    if L >= 2.0:              # 同名异地河（如福建闽江）：画线但不用该古称
                        auto.append((L, dp(s, 0.014)))
                    continue
                if zh is None:
                    if L >= 2.0:
                        auto.append((L, dp(s, 0.014)))
                else:
                    got.setdefault(zh, []).append((L, dp(s, 0.008 if w >= 1.5 else 0.006)))
    out = [{'name': '黄河', 'color': WATER, 'w': 2.8, 'pts': huang}]
    for zh, meta in HAND_RIVERS.items():
        if zh == '岷水':
            continue                      # 岷水与 NE 段合并，单独处理
        out.append({'name': zh, 'color': WATER, 'w': meta['w'], 'pts': smooth(meta['pts'], 8)})
    for zh, segs in got.items():
        segs.sort(key=lambda x: -x[0])
        w = next(v[1] for k, v in RIVER_MAP.items() if v[0] == zh)
        if zh == '长江':
            # 干流在 NE 里被切成 Chang Jiang + Yangtze 多段，首尾相接成一条连续线；
            # 东汉口门在镇江—扬州（今江阴以东为宽阔口内水域），截断并小幅入海
            line = chain([s for _, s in segs], 0.12)
            line = [q for q in line if q[0] <= 120.35] + [[120.45, 31.9], [120.6, 31.78]]
            out.append({'name': '长江', 'color': WATER, 'w': w, 'pts': dp(line, 0.007)})
        elif zh == '淮水':
            for L2, s2 in segs[:6]:
                s3 = [q for q in s2 if q[0] <= 119.72]
                if s3 and len(s3) >= 6:
                    out.append({'name': zh, 'color': WATER, 'w': w,
                                'pts': s3 + [[119.8, 34.05], [119.9, 33.95]] if s3[-1][0] > 119.4 else s3})
        elif zh == '岷水':
            hand = smooth(HAND_RIVERS['岷水']['pts'], 8)
            ne = next((s for _, s in segs
                       if dist(s[0], hand[-1]) < 0.6 or dist(s[-1], hand[-1]) < 0.6), None)
            if ne is not None:
                ne = ne if dist(ne[0], hand[-1]) <= dist(ne[-1], hand[-1]) else ne[::-1]
                out.append({'name': '岷水', 'color': WATER, 'w': w, 'pts': hand + ne[1:]})
            else:
                out.append({'name': '岷水', 'color': WATER, 'w': w, 'pts': hand})
        else:
            for L, s in segs[:6]:         # 每条河最多 6 段，防止碎片刷屏
                out.append({'name': zh, 'color': WATER, 'w': w, 'pts': s})
    auto.sort(key=lambda x: -x[0])
    for L, s in auto[:45]:                # 无古称的长河补密（不标名）
        out.append({'name': '', 'color': WATER, 'w': 1.0, 'pts': s})
    return out

# ---------------------------------------------------------------- 湖泊
LAKE_MAP = {
    'Tai Hu': '太湖', 'Chao Hu': '巢湖', 'Dongting Hu': '洞庭', 'Qinghai Hu': '西海',
}
HAND_LAKES = {
    '巨野泽': [[115.95, 35.15], [116.25, 35.2], [116.42, 35.4], [116.3, 35.55], [116.0, 35.5], [115.88, 35.3]],
    '滇池':   [[102.62, 24.72], [102.72, 24.85], [102.7, 24.98], [102.63, 24.95], [102.58, 24.82]],
    '洱海':   [[100.12, 25.62], [100.24, 25.75], [100.2, 25.98], [100.12, 25.9], [100.08, 25.72]],
    '居延泽': [[101.05, 41.72], [101.35, 41.78], [101.42, 42.05], [101.2, 42.12], [101.0, 41.95]],
    '大陆泽': [[114.80, 37.22], [115.05, 37.25], [115.10, 37.40], [114.86, 37.42], [114.74, 37.31]],
    '昆明池': [[108.68, 34.18], [108.84, 34.19], [108.85, 34.27], [108.70, 34.27]],
    '芍陂':   [[116.52, 32.28], [116.70, 32.30], [116.73, 32.40], [116.56, 32.43], [116.46, 32.35]],
    '圃田泽': [[113.92, 34.66], [114.14, 34.68], [114.17, 34.79], [113.98, 34.81], [113.86, 34.74]],
}

def build_lakes():
    d = json.load(io.open(os.path.join(NE, 'ne_10m_lakes.geojson'), encoding='utf-8'))
    out = []
    for ft in d['features']:
        p = ft['properties']; g = ft['geometry']
        name = p.get('name')
        if name not in LAKE_MAP or p.get('featurecla') not in ('Lake', 'Alkaline Lake', 'Reservoir'):
            continue
        polys = [g['coordinates']] if g['type'] == 'Polygon' else g['coordinates']
        for poly in polys:
            ring = poly[0]
            segs = clip_line(ring)
            for s in segs:
                if len(s) >= 8:
                    out.append({'name': LAKE_MAP[name], 'pts': dp(s, 0.012)})
    for zh, pts in HAND_LAKES.items():
        out.append({'name': zh, 'pts': pts})
    return out

# ---------------------------------------------------------------- 州名标注
ZHOU = [['幽州', 116.4, 40.6], ['冀州', 115.0, 37.6], ['并州', 112.4, 38.2], ['青州', 118.8, 36.6],
        ['兖州', 115.9, 35.4], ['司隶', 111.6, 34.9], ['豫州', 115.0, 33.2], ['徐州', 117.6, 34.3],
        ['凉州', 102.0, 38.0], ['益州', 103.8, 30.0], ['荆州', 112.0, 30.0], ['扬州', 118.6, 30.8],
        ['交州', 108.5, 21.8], ['西域', 86.0, 40.0]]

# ---------------------------------------------------------------- 十三州州界
# 东汉十三州示意多边形（按谭图 196–201 幅走向手工概化，非精确界线）。
HAND_ZHOU = {
 # 说明：控制点按谭图州界走向概化，尽量贴着「山河」走（州界多沿山脊/大河）。
 # 拓扑约定：相邻州的公共边界使用同一串控制点（两州环内坐标完全一致，
 # 方向相反），经 arc 化平滑后共用同一条曲线 → 州界贴合无缝。
 '司隶': [[110.4,37.2],[111.0,37.0],[111.3,36.4],[111.1,35.8],[111.5,35.3],[111.2,34.9],
          [110.6,34.7],[110.3,34.5],[110.7,34.1],[111.3,33.8],[112.2,33.4],[111.3,33.3],
          [110.4,33.4],[109.6,33.5],[108.8,33.6],[108.0,33.7],[107.2,33.8],[106.6,34.2],
          [105.4,34.0],[105.2,35.0],[105.8,35.6],[106.4,36.2],[107.0,36.8],[107.6,37.4],
          [108.6,36.9],[109.6,37.1]],
 '豫州': [[113.9,34.6],[114.9,34.5],[115.9,34.5],[116.7,34.4],[117.4,34.2],[117.9,34.6],
          [117.7,33.8],[117.4,33.0],[117.4,32.5],[116.6,32.4],[115.6,32.3],[114.8,32.3],
          [114.0,32.4],[113.7,32.9],[113.6,33.5],[113.9,33.9]],
 '兖州': [[113.9,34.6],[114.7,34.7],[115.5,35.0],[116.3,35.2],[116.9,35.5],[117.6,35.9],
          [118.1,35.6],[118.3,35.0],[117.9,34.6],[117.4,34.2],[116.7,34.4],[115.9,34.5],
          [114.9,34.5]],
 '徐州': [[117.9,34.6],[118.5,34.7],[119.2,34.9],[119.9,35.2],[120.6,35.3],[120.9,34.6],
          [120.6,33.8],[119.9,33.2],[119.0,32.9],[118.4,32.7],[117.6,32.5],[117.4,33.0],
          [117.7,33.8],[117.9,34.6]],
 '青州': [[116.9,36.5],[117.3,37.0],[117.6,37.5],[118.6,37.7],[119.6,37.8],[120.6,37.8],
          [121.6,37.7],[122.6,37.4],[122.6,36.9],[121.4,36.6],[120.4,36.1],[119.6,35.8],
          [118.9,35.6],[118.3,35.5],[117.6,35.9],[117.1,36.2]],
 '冀州': [[113.9,35.9],[114.6,36.2],[115.4,36.5],[116.2,36.6],[116.9,36.5],[117.4,37.0],
          [117.6,37.5],[117.9,38.5],[119.0,39.9],[118.0,39.6],[117.2,39.4],[116.4,39.2],
          [115.6,38.9],[114.8,38.5],[113.9,38.2],[113.9,37.6],[113.8,36.9],[113.9,36.3]],
 '幽州': [[113.9,38.2],[114.4,38.7],[114.8,39.3],[114.6,40.0],[113.9,40.6],[114.5,41.2],
          [115.6,41.6],[116.6,42.2],[117.5,42.6],[118.6,43.2],[119.8,43.4],[121.0,43.0],
          [122.4,43.2],[123.8,43.5],[125.0,43.0],[124.9,41.8],[124.4,40.9],[123.6,40.0],
          [122.2,39.7],[121.2,39.4],[120.2,40.0],[119.0,39.9],[118.0,39.6],[117.2,39.4],
          [116.4,39.2],[115.6,38.9],[114.8,38.5]],
 '并州': [[110.4,37.2],[111.0,37.6],[111.8,37.9],[112.4,38.4],[113.0,39.0],[113.6,39.9],
          [113.0,40.6],[112.0,41.0],[111.0,41.2],[110.0,40.9],[109.2,40.4],[108.2,39.7],
          [107.9,38.6],[107.6,37.4],[108.6,36.9],[109.6,37.1]],
 '凉州': [[100.2,40.6],[101.2,41.0],[102.4,41.2],[103.6,41.2],[104.6,40.6],[105.4,40.2],
          [106.4,39.6],[107.4,39.2],[107.9,38.6],[107.6,37.4],[107.0,36.8],[106.4,36.2],
          [105.8,35.6],[105.2,35.0],[105.4,34.0],[103.8,33.4],[102.9,33.0],[101.8,33.2],
          [100.8,33.8],[99.8,34.4],[98.8,35.2],[97.8,35.9],[96.6,36.4],[95.4,37.4],
          [95.2,38.6],[96.2,39.6],[97.4,40.2]],
 '益州': [[103.8,33.4],[105.4,34.0],[106.6,34.2],[107.2,33.8],[108.0,33.7],[108.8,33.6],
          [109.6,33.5],[110.4,33.4],[110.8,32.6],[110.4,31.8],[110.0,31.0],[109.8,30.2],
          [109.2,29.4],[108.4,28.6],[108.0,27.6],[107.7,25.6],[107.2,22.6],[106.0,24.6],
          [104.6,26.4],[103.4,25.4],[102.2,24.6],[101.0,24.4],[99.8,25.0],[98.6,25.8],
          [97.6,27.0],[97.2,28.4],[97.2,30.0],[97.35,31.8],[97.45,33.8],[97.8,35.9],
          [98.8,35.2],[99.8,34.4],[100.8,33.8],[101.8,33.2],[102.9,33.0]],
 '荆州': [[111.4,33.3],[112.2,33.4],[113.6,33.5],[113.7,32.9],[114.0,32.4],[114.6,31.9],
          [115.0,31.2],[115.4,30.4],[115.6,29.6],[115.0,28.6],[114.2,27.4],[113.2,26.2],
          [112.2,25.2],[111.2,24.6],[110.0,24.2],[109.0,23.6],[108.0,23.0],[107.2,22.6],
          [107.7,25.6],[108.0,27.6],[108.4,28.6],[109.2,29.4],[109.8,30.2],[110.0,31.0],
          [110.4,31.8],[110.8,32.6]],
 '扬州': [[116.6,32.4],[117.4,32.4],[118.2,32.6],[119.0,32.8],[119.8,32.4],[120.6,32.2],
          [121.4,31.8],[121.8,30.8],[121.2,29.8],[120.2,28.6],[119.2,27.4],[118.2,26.4],
          [117.0,25.8],[116.0,26.4],[114.2,27.4],[115.0,28.6],[115.6,29.6],[114.8,30.6],
          [115.6,31.0],[116.0,31.8]],
 '交州': [[111.2,24.6],[112.0,25.0],[113.0,25.2],[113.8,24.8],[115.0,24.2],[116.2,23.4],
          [116.0,22.6],[114.8,22.2],[113.6,22.0],[112.4,21.6],[111.2,21.4],[110.0,21.0],
          [109.0,20.4],[108.2,19.4],[107.6,18.2],[107.0,17.0],[106.4,16.2],[105.6,16.4],
          [105.2,17.6],[104.8,18.8],[105.0,20.0],[105.4,21.2],[106.2,22.2],[107.2,22.6],
          [108.0,23.0],[109.0,23.6],[110.0,24.2]],
}

def smooth_closed(pts, n=6):
    """闭合 Catmull-Rom 细分：消除州界的直线段观感（首尾环绕取控制点）"""
    m = len(pts)
    if m < 4:
        return [list(p) for p in pts]
    out = []
    for i in range(m):
        p0, p1, p2, p3 = pts[(i - 1) % m], pts[i], pts[(i + 1) % m], pts[(i + 2) % m]
        for j in range(n):
            t = j / n; t2 = t * t; t3 = t2 * t
            x = 0.5 * (2 * p1[0] + (-p0[0] + p2[0]) * t
                       + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * (2 * p1[1] + (-p0[1] + p2[1]) * t
                       + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            out.append([round(x, 3), round(y, 3)])
    out.append(out[0])
    return out

def _align_zhou_pts(rings, tol=0.25):
    """跨州近似重合的控制点（手工误差 ≤ tol）合并到共同坐标（均值），
    使相邻州公共边界的端点精确一致。返回对齐后的环（并去连续重复点）。"""
    items = []
    for n, ps in rings.items():
        for i, p in enumerate(ps):
            items.append((n, i, p[0], p[1]))
    parent = list(range(len(items)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for a in range(len(items)):
        for b in range(a + 1, len(items)):
            if items[a][0] == items[b][0]:
                continue
            dx = items[a][2] - items[b][2]
            dy = items[a][3] - items[b][3]
            if dx * dx + dy * dy < tol * tol:
                ra, rb = find(a), find(b)
                if ra != rb:
                    parent[ra] = rb
    groups = {}
    for a in range(len(items)):
        groups.setdefault(find(a), []).append(a)
    aligned = {n: [None] * len(ps) for n, ps in rings.items()}
    for g in groups.values():
        cx = round(sum(items[a][2] for a in g) / len(g), 3)
        cy = round(sum(items[a][3] for a in g) / len(g), 3)
        for a in g:
            aligned[items[a][0]][items[a][1]] = [cx, cy]
    for n, ps in aligned.items():
        dedup = [ps[0]]
        for p in ps[1:]:
            if p != dedup[-1]:
                dedup.append(p)
        if len(dedup) > 1 and dedup[0] == dedup[-1]:
            dedup.pop()
        aligned[n] = dedup
    return aligned


def _smooth_open(pts, n=6):
    """开放 Catmull-Rom：段起点精确保留（t=0 恒等），末端节点由下一段起点补上，
    供拓扑拼接（相邻州正反引用同一条弧，坐标逐点一致）。"""
    m = len(pts)
    if m < 3:
        return [list(pts[0])]   # 退化段只输出起点，末端由下一段起点补上
    ext = ([[2 * pts[0][0] - pts[1][0], 2 * pts[0][1] - pts[1][1]]]
           + [list(p) for p in pts]
           + [[2 * pts[-1][0] - pts[-2][0], 2 * pts[-1][1] - pts[-2][1]]])
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for j in range(n):
            t = j / n; t2 = t * t; t3 = t2 * t
            x = 0.5 * (2 * p1[0] + (-p0[0] + p2[0]) * t
                       + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * (2 * p1[1] + (-p0[1] + p2[1]) * t
                       + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            out.append([round(x, 3), round(y, 3)])
    return out


def _split_ring(pts, shared):
    """环按共享节点切段 → [(u, v, seg_pts 含端点), ...]；
    无共享节点 → 单闭合段；仅 1 个共享节点 → 自闭合段。"""
    m = len(pts)
    keys = [tuple(p) for p in pts]
    idxs = [i for i, k in enumerate(keys) if k in shared]
    if not idxs:
        return [(None, None, list(pts) + [list(pts[0])])]
    if len(idxs) == 1:
        i = idxs[0]
        seg = [pts[j % m] for j in range(i, i + m)] + [pts[i]]
        return [(keys[i], keys[i], seg)]
    segs = []
    stops = idxs + [idxs[0] + m]
    for a, b in zip(stops, stops[1:]):
        segs.append((keys[a], keys[b % m], [pts[j % m] for j in range(a, b + 1)]))
    return segs


def build_zhoupoly():
    """拓扑共享州界：
    1) 控制点跨州对齐（合并手工误差）；
    2) 每州环按共享节点拆段，同端点对的段归并（校验/取密路径）；
    3) 同属两州的相邻段合并为完整边界弧（度 2 节点消解）；
    4) 每弧独立平滑一次，两州正反引用同一份结果 → 公共边界逐点一致。"""
    aligned = _align_zhou_pts(HAND_ZHOU, tol=0.25)
    cnt = {}
    for ps in aligned.values():
        for p in ps:
            cnt[tuple(p)] = cnt.get(tuple(p), 0) + 1
    shared = {k for k, c in cnt.items() if c >= 2}
    segs = []   # {'a','b','pts','users','closed','dead','into'}
    zseq = {}   # zhou -> [seg index,...] 环序
    for n, ps in aligned.items():
        m = len(ps)
        keys = [tuple(p) for p in ps]
        idxs = [i for i, k in enumerate(keys) if k in shared]
        seq = []
        if not idxs:
            segs.append({'a': None, 'b': None, 'users': {n}, 'closed': True,
                         'pts': [list(p) for p in ps] + [list(ps[0])], 'dead': False, 'into': None})
            seq.append(len(segs) - 1)
        elif len(idxs) == 1:
            i = idxs[0]
            seg = [ps[j % m] for j in range(i, i + m)] + [ps[i]]
            segs.append({'a': keys[i], 'b': keys[i], 'users': {n}, 'closed': True,
                         'pts': seg, 'dead': False, 'into': None})
            seq.append(len(segs) - 1)
        else:
            stops = idxs + [idxs[0] + m]
            for a, b in zip(stops, stops[1:]):
                segs.append({'a': keys[a], 'b': keys[b % m], 'users': {n}, 'closed': False,
                             'pts': [ps[j % m] for j in range(a, b + 1)], 'dead': False, 'into': None})
                seq.append(len(segs) - 1)
        zseq[n] = seq
    # 归并同端点对：路径一致→共用；不一致→取更密路径
    reg = {}
    for si, s in enumerate(segs):
        if s['closed']:
            continue
        k = tuple(sorted([s['a'], s['b']]))
        if k not in reg:
            reg[k] = si
            continue
        cur, new = segs[reg[k]], s
        same = new['pts'] if tuple(cur['pts'][0]) == tuple(new['pts'][0]) else list(reversed(new['pts']))
        if [list(p) for p in cur['pts']] != [list(p) for p in same]:
            if len(new['pts']) > len(cur['pts']):
                print('  弧 %s↔%s：取更密路径' % (str(k[0][:6]), str(k[1][:6])))
                cur['pts'] = same
            else:
                print('  弧 %s↔%s：保留既有路径' % (str(k[0][:6]), str(k[1][:6])))
        cur['users'] |= new['users']
        new['dead'] = True
        new['into'] = reg[k]
    for n, seq in zseq.items():
        redir = [s['into'] if s['into'] is not None else si
                 for si, s in ((i, segs[i]) for i in seq)]
        dedup = []
        for si in redir:
            if dedup and dedup[-1] == si:
                continue
            dedup.append(si)
        zseq[n] = dedup
    # 弧合并：users 相同且几何相接的相邻段合并（消解度 2 节点）
    changed = True
    while changed:
        changed = False
        for n, seq in zseq.items():
            seq = [s for s in seq if not segs[s]['dead']]
            zseq[n] = seq
            i = 0
            while len(seq) > 1 and i < len(seq):
                A, B = segs[seq[i]], segs[seq[(i + 1) % len(seq)]]
                if A['closed'] or B['closed'] or A['users'] != B['users']:
                    i += 1
                    continue
                if A['b'] == B['a']:
                    A['pts'] = A['pts'] + B['pts'][1:]
                    A['b'] = B['b']
                elif A['a'] == B['b']:
                    A['pts'] = B['pts'] + A['pts'][1:]
                    A['a'] = B['a']
                else:
                    i += 1
                    continue
                B['dead'] = True
                B['into'] = seq[i]
                seq.pop(i + 1 if i + 1 < len(seq) else 0)
                changed = True
    for n, seq in zseq.items():
        redir = [s['into'] if (s['into'] is not None and segs[s['into']] is not s) else si
                 for si, s in ((i, segs[i]) for i in seq)]
        dedup = []
        for si in redir:
            if dedup and dedup[-1] == si:
                continue
            dedup.append(si)
        zseq[n] = dedup
    # 平滑与拼接：每州按几何链动态排序其弧集（弧含起点不含末端，末端由下段起点补上）
    live = [s for s in segs if not s['dead']]
    sm = {}
    for s in live:
        sm[id(s)] = _smooth_open(s['pts'], 6) if not s['closed'] else smooth_closed(s['pts'], 6)
    out = []
    for n in HAND_ZHOU:
        pool = [s for s in live if n in s['users']]
        assert pool, n
        pts = []
        cur = tuple(pool[0]['pts'][0])
        start = cur
        remaining = list(pool)
        while remaining:
            cand = [i for i, s in enumerate(remaining)
                    if tuple(s['pts'][0]) == cur or tuple(s['pts'][-1]) == cur]
            if not cand:
                raise AssertionError('%s 州界弧断链于 %s' % (n, str(cur)))
            if len(cand) > 1:   # 环起点两向皆可（或歧义）：优先正向，环闭合断言兜底
                fwd = [i for i in cand if tuple(remaining[i]['pts'][0]) == cur]
                cand = fwd or cand
            s = remaining.pop(cand[0])
            a = sm[id(s)]
            if tuple(s['pts'][0]) == cur:
                pts.extend(a)
                cur = tuple(s['pts'][-1])
            else:
                pts.append(list(s['pts'][-1]))
                pts.extend([list(p) for p in reversed(a)][:-1])
                cur = tuple(s['pts'][0])
        assert cur == start, n + ' 环不闭合'
        pts.append(list(pts[0]))
        out.append({'name': n, 'pts': pts})
    # 自检：无连续重复；相邻州共享坐标点足够多；多边形无自交
    for z in out:
        assert all(z['pts'][i] != z['pts'][i + 1] for i in range(len(z['pts']) - 1)), z['name']
    try:
        from shapely.geometry import Polygon
        for z in out:
            p = Polygon(z['pts'])
            assert p.is_simple, '%s 州界自交（非简单多边形）' % z['name']
    except ImportError:
        pass
    seen = {}
    for z in out:
        for p in z['pts']:
            seen[tuple(p)] = seen.get(tuple(p), 0) + 1
    nshare = sum(1 for c in seen.values() if c >= 2)
    narc = sum(1 for s in live if len(s['users']) >= 2)
    print('  边界弧 %d 条（公共 %d）→ 州界共享坐标点 %d' % (len(live), narc, nshare))
    assert nshare > 300, '拓扑共享失败，公共边界未贴合'
    return out

def main():
    coast = build_coast()
    rivers = build_rivers()
    lakes = build_lakes()
    zhoupoly = build_zhoupoly()
    out = {'source': 'Natural Earth 10m + 东汉河道/古湖手工修正',
           'note': '黄河下游为东汉故道（禹河）；泗济洛淝滹资湟淯为 10m 数据缺失的手工补线；湖泊跳过彭蠡/洪泽（位置或形成年代与东汉不符），巨野泽/滇池/洱海/居延泽为手工示意；州界为谭图走向手工概化',
           'coast': coast, 'rivers': rivers, 'lakes': lakes, 'zhou': ZHOU, 'zhoupoly': zhoupoly}
    p = os.path.join(ROOT, 'data', 'geo-real.json')
    io.open(p, 'w', encoding='utf-8').write(json.dumps(out, ensure_ascii=False))
    npts = sum(len(s) for s in coast) + sum(len(r['pts']) for r in rivers) \
         + sum(len(l['pts']) for l in lakes) + sum(len(z['pts']) for z in zhoupoly)
    print('海岸段 %d（%d 点）｜河流 %d 段 %d 名（%d 点）｜湖泊 %d（%d 点）｜州界 %d 州（%d 点）｜合计 %d 点 → %s'
          % (len(coast), sum(len(s) for s in coast),
             len(rivers), len(set(r['name'] for r in rivers)), sum(len(r['pts']) for r in rivers),
             len(lakes), sum(len(l['pts']) for l in lakes),
             len(zhoupoly), sum(len(z['pts']) for z in zhoupoly), npts, p))

if __name__ == '__main__':
    main()
