#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
读三国 构建管线（P1-A：多章 + 词表规则引擎）

输入
  data/source/chNNN.txt        原文（纯正文，不含回目/站点简介）
  data/chapters.json           章目索引
  data/persons_*.json          人物卡
  data/places-seed.csv         地名种子
  data/places-additions.json   地名增量
  data/lexicon-rules.json      词表规则（deny / drop / guard）
  data/event_battle_*.json     事件与战役

输出
  build/chapters/chNNN.json    每回正文 + 锚点
  build/persons/*.json         人物卡（含全书提及次数）
  build/persons_index.json     人物库索引（阵营/身份/年份可筛）
  build/places.json            地名（含像素坐标）
  build/book.json              全书索引
  build/audit/*.json           审计数据
  app/reader.html              阅读器（数据内联，规避 file:// CORS）
  app/map_test.html            地图试验页
"""
import csv, json, io, os, glob, math, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
BUILD = os.path.join(ROOT, 'build')
APP = os.path.join(ROOT, 'app')

# ---------- 0. 图像坐标系（非 GIS） ----------
# 谭图扫描件到位后只改 CANVAS 与 base_image，业务代码与数据零改动
CANVAS = {
    'w': 1400, 'h': 1200,
    'lng0': 97.0, 'lng1': 126.0, 'lat0': 18.0, 'lat1': 44.0,
    'name': 'P2-R 真实地理底图（NE 10m + DEM 地形晕渲 + 汉县点位）',
    'tile_sheet': 'p2-ne-real',
    'base_image': None,
}
_MIDLAT = math.radians((CANVAS['lat0'] + CANVAS['lat1']) / 2)
_COS = math.cos(_MIDLAT)
_K = min(CANVAS['w'] / ((CANVAS['lng1'] - CANVAS['lng0']) * _COS),
         CANVAS['h'] / (CANVAS['lat1'] - CANVAS['lat0']))
_OFF_X = (CANVAS['w'] - (CANVAS['lng1'] - CANVAS['lng0']) * _COS * _K) / 2


def project(lng, lat):
    return round((lng - CANVAS['lng0']) * _COS * _K + _OFF_X, 1), round((CANVAS['lat1'] - lat) * _K, 1)


def clip_line(pts, pad=0.05):
    """把经纬折线裁剪到画布范围（外扩 pad），返回若干段折线（LineString 相交拆段）。
    原始河流/海岸数据经纬范围（95-130E/16-46N）超出画布，直接投影会画出画布外。"""
    from shapely.geometry import LineString, box
    ln = LineString(pts)
    res = ln.intersection(box(CANVAS['lng0'] - pad, CANVAS['lat0'] - pad,
                              CANVAS['lng1'] + pad, CANVAS['lat1'] + pad))
    segs = list(res.geoms) if hasattr(res, 'geoms') else ([] if res.is_empty else [res])
    return [list(s.coords) for s in segs
            if s.geom_type == 'LineString' and len(s.coords) > 1]


# 示意底图要素（经纬度）。谭图到位后这些退化为可选叠加层。
BASE_GEO = {
    'coast': [[108.2,21.6],[109.8,21.4],[110.6,21.2],[112.0,21.7],[113.5,22.2],[114.3,22.5],[115.5,22.8],
              [116.7,23.4],[117.6,23.9],[118.6,24.6],[119.6,25.4],[119.9,26.3],[120.5,27.3],[121.3,28.3],
              [121.9,29.4],[121.7,30.4],[121.9,31.5],[121.2,32.2],[120.3,33.2],[119.6,34.3],[119.3,35.0],
              [119.5,35.5],[120.4,36.1],[121.6,36.9],[122.4,37.4],[121.0,37.9],[119.9,37.3],[118.9,38.0],
              [117.8,38.9],[119.7,40.0],[121.1,40.8]],
    'liaodong': [[121.6,40.9],[122.3,39.9],[121.3,38.9]],
    'rivers': [
        {'name': '黄河', 'color': '#b08a5a', 'w': 2.6,
         'pts': [[103.8,36.1],[105.2,37.5],[106.3,38.5],[107.4,40.7],[109.8,40.6],[111.2,40.3],[111.1,39.4],
                 [110.6,35.7],[110.3,34.5],[111.2,34.8],[112.4,34.8],[113.6,34.9],[114.3,34.8],[115.0,35.7],
                 [116.0,36.4],[117.0,36.7],[118.9,37.8]]},
        {'name': '长江', 'color': '#6f8fa3', 'w': 3.0,
         'pts': [[104.6,28.8],[105.4,28.9],[106.5,29.6],[107.4,29.7],[108.4,30.8],[109.5,31.0],[111.3,30.7],
                 [112.2,30.3],[114.3,30.6],[116.0,29.7],[117.0,30.5],[118.8,32.1],[119.4,32.2],[120.3,31.9],[121.5,31.4]]},
        {'name': '汉水', 'color': '#6f8fa3', 'w': 2.0,
         'pts': [[107.0,33.1],[109.5,32.7],[112.1,32.0],[113.5,31.2],[114.3,30.6]]},
    ],
    'zhou': [['幽州',116.4,39.9],['冀州',115.0,37.6],['并州',112.4,38.2],['青州',118.4,36.7],['兖州',115.9,35.4],
             ['司隶',112.0,34.4],['豫州',114.6,33.4],['徐州',117.6,34.4],['凉州',102.8,37.6],['益州',104.6,30.2],
             ['荆州',112.0,30.0],['扬州',118.2,31.0],['交州',110.0,23.6]],
}


def _junpoly_client():
    """郡界多边形（scripts/build_junpoly.py 产出的 build/junpoly.json，已是像素坐标）。

    每项：{n:郡名, z:所属州, s:[x,y]治所, p:[[x,y]...]主环, e:[环...]飞地}。
    字段名压到 1 字符，104 个郡控制在 ~30KB；缺失时返回空数组（前端自动跳过郡界层）。
    """
    f = os.path.join(ROOT, 'build', 'junpoly.json')
    if not os.path.exists(f):
        print('  ! 缺 build/junpoly.json，郡界层将不渲染（先跑 scripts/build_junpoly.py）')
        return []
    raw = json.load(io.open(f, encoding='utf-8'))
    out = []
    for j in raw:
        p = [[round(x, 1), round(y, 1)] for x, y in j['pts']]
        if len(p) < 3:
            continue
        out.append({'n': j['name'], 'z': j['zhou'], 's': [round(j['seat'][0], 1), round(j['seat'][1], 1)],
                    'p': p, 'e': [[[round(x, 1), round(y, 1)] for x, y in r] for r in j.get('extra') or []]})
    return out


def _regionpoly_client():
    """跨区域地理分区（scripts/build_regionpoly.py 产出，像素坐标）。
    {n:名, p:主环, e:飞地}；缺失时返回空数组，前端点击该类地名就不画分区高亮。"""
    f = os.path.join(ROOT, 'build', 'regionpoly.json')
    if not os.path.exists(f):
        print('  ! 缺 build/regionpoly.json，跨区域地理高亮不可用（先跑 scripts/build_regionpoly.py）')
        return []
    raw = json.load(io.open(f, encoding='utf-8'))
    return [{'n': rp['n'],
             'p': [[round(x, 1), round(y, 1)] for x, y in rp['pts']],
             'e': [[[round(x, 1), round(y, 1)] for x, y in ring] for ring in (rp.get('e') or [])]}
            for rp in raw]


def _zhoupoly_refit():
    """沿海州界贴合版（scripts/refit_zhoupoly.py 产出）。
    概化州界的沿海段与底图精确海岸线之间有空隙/入海，贴合后视觉严丝合缝；
    内陆州原样保留。缺失文件时返回 None（回退原始 zhoupoly）。"""
    f = os.path.join(ROOT, 'build', 'zhoupoly_refit.json')
    if not os.path.exists(f):
        return None
    raw = json.load(io.open(f, encoding='utf-8'))
    # ★ 2026-10：同一州的多个环（主环 + 飞地/离岛）必须合并成**一个条目**。
    #   前端 renderPlaces() 按 `zPaths[i*2] / zPaths[i*2+1]` 配对 zhouPoly 的
    #   path（每州 2 条：晕底 + 虚线），再以 name 建索引。若把环拆成多个条目，
    #   (a) zPoly.set(name) 同键被后一个环覆盖，只剩最后一个环能高亮；
    #   (b) i*2 下标与 path 实际数量错位，张冠李戴——多环州（交州 4 环、
    #   益州 3 环、凉州/徐/荆/豫各 2 环）点州名时边界线不高亮就是这个原因。
    #   合并后 pts 写成「多环数组」，dPoly 支持嵌套自动拼多个子路径。
    out = []
    # ★ 2026-10：凉州州界西段本随敦煌延伸到画布外（lng<97）。用户定案：随敦煌郡
    #   删除一并截除，州界止于画布西缘（lng 97–126 / lat 18–44），与裁剪后的郡面同口径。
    from shapely.geometry import Polygon as _ZPg, box as _ZBox
    _CB = _ZBox(97.0, 18.0, 126.0, 44.0)
    for name, rings in raw.items():
        if name == '凉州':
            rr = []
            for r in rings:
                if len(r) < 4:
                    continue
                g = _ZPg(r).buffer(0).intersection(_CB)
                for h in (g.geoms if hasattr(g, 'geoms') else [g]):
                    if h.geom_type == 'Polygon' and h.area > 1e-6:
                        rr.append([[round(x, 4), round(y, 4)] for x, y in h.exterior.coords])
            if not rr:
                continue
        else:
            rr = [r for r in rings if len(r) >= 4]
            if not rr:
                continue
        out.append({'name': name, 'pts': rr if len(rr) > 1 else rr[0]})
    return out


def geo_for_client():
    """把底图要素投影成像素，前端直接画，不再算投影"""
    def pl(pts):
        # pts 可能是单环 [[lng,lat],…]，也可能是多环 [[[lng,lat],…],…]
        # （同一州的主环 + 飞地，见 _zhoupoly_refit）
        if pts and isinstance(pts[0][0], (list, tuple)):
            return [pl(r) for r in pts]
        return [[x, y] for x, y in (project(a, b) for a, b in pts)]
    real = os.path.join(ROOT, 'data', 'geo-real.json')
    if os.path.exists(real):
        g = json.load(io.open(real, encoding='utf-8'))
        counties = []
        cf = os.path.join(ROOT, 'data', 'counties-han.json')
        if os.path.exists(cf):
            for c in json.load(io.open(cf, encoding='utf-8'))['counties']:
                # 画布外（敦煌以西等）裁剪
                if not (CANVAS['lng0'] <= c['lng'] <= CANVAS['lng1']
                        and CANVAS['lat0'] <= c['lat'] <= CANVAS['lat1']):
                    continue
                x, y = project(c['lng'], c['lat'])
                counties.append({'name': c['n'], 'x': x, 'y': y,
                                 'tier': c['t'], 'adm': c['a'], 'zhou': c['p']})
        zrefit = _zhoupoly_refit()
        # 河流/海岸：裁剪到画布范围（原始数据经纬越界 95-130E/16-46N）
        rivers = []
        for r in g['rivers']:
            for seg in clip_line(r['pts']):
                p = [project(a, b) for a, b in seg]
                if len(p) > 1:
                    rivers.append({'name': r['name'], 'color': r['color'], 'w': r['w'], 'pts': p})
        coast = []
        for s in g['coast']:
            for seg in clip_line(s):
                p = [project(a, b) for a, b in seg]
                if len(p) > 1:
                    coast.append(p)
        return {
            'coast': coast,
            'rivers': rivers,
            'lakes': [{'name': l['name'], 'pts': pl(l['pts'])} for l in g.get('lakes', [])],
            'zhou': [{'name': n, 'x': project(a, b)[0], 'y': project(a, b)[1]} for n, a, b in g['zhou']],
            'zhoupoly': [{'name': z['name'], 'pts': pl(z['pts'])} for z in (zrefit or g.get('zhoupoly', []))],
            'junpoly': _junpoly_client(),
            'regionpoly': _regionpoly_client(),
            'counties': counties,
            'terrain': 'assets/terrain.jpg',
            'real': True,
        }
    return {
        'coast': [pl(BASE_GEO['coast']), pl(BASE_GEO['liaodong'])],
        'rivers': [{'name': r['name'], 'color': r['color'], 'w': r['w'], 'pts': pl(r['pts'])} for r in BASE_GEO['rivers']],
        'zhou': [{'name': n, 'x': project(a, b)[0], 'y': project(a, b)[1]} for n, a, b in BASE_GEO['zhou']],
        'real': False,
    }


# ---------- 1. 词表规则 ----------
class RuleSet:
    """把 lexicon-rules.json 编译成查询结构。

    三类操作：
      deny  该表面形式全书禁用（进 / 让 / 吴）
      drop  从某实体移除该表面形式（荆州 不归江陵）
      guard 给某实体的某表面形式加上下文闸门
            mode=always  只要不被 block 拦住就匹配
            mode=guarded 必须 allow_prev / allow_next 命中才匹配
    """

    def __init__(self, raw):
        self.deny = set()
        self.drops = set()          # (type, id, surface)
        self.guards = {}            # (type, id, surface) -> rule
        for r in raw.get('rules', []):
            op = r['op']
            if op == 'deny':
                self.deny.add(r['surface'])
            elif op == 'drop':
                self.drops.add((r['type'], r['id'], r['surface']))
            elif op == 'guard':
                self.guards[(r['type'], r['id'], r['surface'])] = r
            else:
                raise ValueError('未知规则操作: ' + op)

    def allow(self, etype, eid, surface, text, start, end):
        rule = self.guards.get((etype, eid, surface))
        if rule is None:
            return True
        # 单字模式：前一字须为标点/空白/言语动词（或段首）**且**后接词命中 allow_next。
        # 两个条件缺一不可，所以『坚守』『操练』『允许』不会命中；只写 OR 会把它们全放进来的。
        # 「言语动词」是第三类前置条件（P1-C）：『卓问肃曰』的『肃』前是『问』而非标点，
        # 按旧规则漏链。放宽前置、但后置仍必须命中言语动词，两条并存。
        if rule.get('mode') == 'single':
            if start == 0:
                pass
            elif text[start - 1] in (rule.get('allow_prev') or []):
                pass
            elif text[start - 1] in (rule.get('allow_prev_verbs') or []):
                pass
            else:
                return False
            after = text[end:]
            return any(after.startswith(w) for w in (rule.get('allow_next') or []))
        before = text[:start]
        after = text[end:]
        # 阻断串支持多字（『司隶校尉』必须能拦住『司隶』，只比首字会漏）
        for s in (rule.get('block_prev') or []):
            if before.endswith(s):
                return False
        for s in (rule.get('block_next') or []):
            if after.startswith(s):
                return False
        if rule.get('mode', 'always') == 'always':
            return True
        prev = text[start - 1] if start > 0 else ''
        nxt = text[end] if end < len(text) else ''
        return bool(prev and prev in (rule.get('allow_prev') or [])) or \
               bool(nxt and nxt in (rule.get('allow_next') or []))


def load_rules():
    raw = json.load(io.open(os.path.join(DATA, 'lexicon-rules.json'), encoding='utf-8'))
    return RuleSet(raw), raw


def apply_single_char(persons, rules, raw):
    """按 lexicon-rules.json 的 single_char 配置生成单字单称规则。

    只对「姓名末字唯一对应一个人物」的字自动启用（实测 106 个末字里 6 个歧义、14 个禁用）。
    返回 {单字: person_id}，供 build_lexicon 把单字注入词典。
    """
    cfg = raw.get('single_char') or {}
    out = {}
    if not cfg.get('auto_from_person_name'):
        return out
    blocked = set(rules.deny) | {d['char'] for d in cfg.get('disable', [])}
    last = {}
    for p in persons:
        nm = p['name']
        if len(nm) >= 2:
            last.setdefault(nm[-1], []).append(p['id'])
    for ch, e in ((x['char'], x) for x in cfg.get('allow_extra', [])):
        last.setdefault(ch, [e['id']])

    for ch, ids in last.items():
        if ch in blocked or len(ids) != 1:
            continue
        pid = ids[0]
        rules.guards[('person', pid, ch)] = {
            'op': 'guard', 'mode': 'single', 'type': 'person', 'id': pid, 'surface': ch,
            'allow_prev': cfg['require_prev'], 'allow_next': cfg['require_next'],
            'allow_prev_verbs': cfg.get('require_prev_verbs') or [],
            'evidence': 'single_char 自动生成：名末字单称，前接标点/言语动词且后接动词才链接',
        }
        out[ch] = pid
    return out


def resolve_anaphora(text, hits, cand_map, cfg):
    """同段回指消歧（P1-C）。

    解决 single_char 通道解决不了的两类字：
      ① 末字对应两人以上（良→颜良/蒯良、嵩→皇甫嵩/曹嵩）
      ② 末字唯一但该字本身是高频动词/名词（表→上表、信→书信）

    判据三条同时成立才链接，缺一即弃：
      1. 前一字为标点/闭合引号/段首 —— 「上表曰」「具表曰」因前接实字而自动出局
      2. 后接言语类动词 —— 「表为荆州刺史」因后接『为』而自动出局
      3. 同段之内，该字之前刚出现过结尾相同的**全称**，且最近的只有一个
         —— 这条是本通道与字符规则的本质区别：判据不是字面歧义，而是眼前的上下文

    只在本段内回指（window=passage）。跨段回指需要篇章级共指，误配代价远高于漏链，
    留到 P2「最近全称回指」统一做。
    """
    if not cfg.get('enabled'):
        return []
    chars = set(cfg.get('chars') or []) - set(cfg.get('exclude') or [])
    prev_ok = set(cfg.get('require_prev') or [])
    prev_verbs = set(cfg.get('require_prev_verbs') or [])
    next_ok = cfg.get('require_next') or []
    conf = (cfg.get('notes') or {}).get('confidence', 0.88)

    covered = [(h[0], h[1]) for h in hits]
    added = []
    for i, c in enumerate(text):
        if c not in chars or c not in cand_map:
            continue
        if i and text[i - 1] not in prev_ok and text[i - 1] not in prev_verbs:
            continue                                  # 条件 1（标点或言语动词）
        after = text[i + 1:]
        if not any(after.startswith(w) for w in next_ok):   # 条件 2
            continue
        if any(not (i + 1 <= a or b <= i) for a, b in covered):   # 已被更长的形式占用
            continue

        # 条件 3：在本段前文里找「以此字结尾的全称」，取最近的一个
        best, best_pos, tie = None, -1, False
        for pid, full in cand_map[c]:
            pos = text.rfind(full, 0, i)
            if pos < 0:
                continue
            if pos > best_pos:
                best, best_pos, tie = (pid, full), pos, False
            elif pos == best_pos:
                tie = True
        if best is None or tie:
            continue

        added.append((i, i + 1, c, 'person', best[0], conf, best[1]))
        covered.append((i, i + 1))
    return added


# ---------- 2. 载入 ----------
def load_chapter_meta():
    return json.load(io.open(os.path.join(DATA, 'chapters.json'), encoding='utf-8'))['chapters']


def load_chapter_text(no):
    path = os.path.join(DATA, 'source', 'ch%03d.txt' % no)
    text = io.open(path, encoding='utf-8').read()
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)   # 去掉站点插入的 markdown 链接
    return [p.strip() for p in text.split('\n\n') if p.strip()]


EMPIRE_FIDS = {'wei', 'shu', 'wu', 'jin'}


def _normalize_tenures(p):
    """人物时间片规范化（2026-10-29 定案）：
    1) 帝国势力（魏蜀吴晋）不设「君主」身份：同一人同势力的君主片并入皇帝片
       （皇帝片起年提前、称号拼接；无皇帝片则直接改标皇帝）。
    2) 亲族只收录「非本势力国君」的国君亲族：若同一人在该势力已有君主/皇帝片，
       其亲族片改标「其他」（保留称帝前经历，不再计入亲族组）。
    """
    ts = p.get('tenure') or []
    by_f = {}
    for t in ts:
        by_f.setdefault(t.get('faction_id'), []).append(t)
    for fid, arr in by_f.items():
        if fid not in EMPIRE_FIDS:
            continue
        lords = [t for t in arr if t.get('role') == '君主']
        if not lords:
            continue
        emps = [t for t in arr if t.get('role') == '皇帝']
        if emps:
            e = emps[0]
            for l in lords:
                e['start_year'] = min(e['start_year'], l['start_year'])
                if l.get('title'):
                    e['title'] = (l['title'] + '；' + (e.get('title') or '')).lstrip('；')
                ts.remove(l)
        else:
            for l in lords:
                l['role'] = '皇帝'
    ruler_f = {t.get('faction_id') for t in ts if t.get('role') in ('君主', '皇帝')}
    for t in ts:
        if t.get('role') == '亲族' and t.get('faction_id') in ruler_f:
            t['role'] = '其他'
    return p


def load_persons():
    persons, seen = [], set()
    for f in sorted(glob.glob(os.path.join(DATA, 'persons_*.json'))):
        for p in json.load(io.open(f, encoding='utf-8'))['persons']:
            if p['id'] in seen:
                print('  ! 人物 id 重复，跳过:', p['id'], 'in', os.path.basename(f))
                continue
            p['_src'] = os.path.basename(f)
            _normalize_tenures(p)
            seen.add(p['id'])
            persons.append(p)
    return persons


def load_places():
    places = {}
    with io.open(os.path.join(DATA, 'places-seed.csv'), encoding='utf-8-sig') as f:
        for r0 in csv.DictReader(f):
            r = {(k.lstrip('\ufeff').strip() if isinstance(k, str) else k): v for k, v in r0.items()}
            pid = r['id'].strip()
            aliases = [a.strip() for a in r['别名'].replace('；', ',').replace('、', ',').split(',')
                       if a.strip() and a.strip() != '—']
            places[pid] = {
                'id': pid, 'name': r['古名'].strip(), 'aliases': aliases,
                'type': r['类型'].strip(), 'modern_name': r['今地'].strip(),
                'province': r['省份'].strip(),
                'lng': float(r['经度']) if r['经度'] else None,
                'lat': float(r['纬度']) if r['纬度'] else None,
                'ancient_admin': r['三国时州郡'].strip(),
                'first_chapter': int(r['首现回目']) if r['首现回目'] else None,
                'coord_precision': r['坐标精度'].strip(), 'coord_note': r['备注'].strip(),
            }
    add = json.load(io.open(os.path.join(DATA, 'places-additions.json'), encoding='utf-8'))
    for p in add['places']:
        p.setdefault('note', '')
        places[p['id']] = p
    return places


EXTRA_PLACE_ALIASES = {'qiao_xian': ['谯郡']}
EXCLUDE_PLACE_IDS = {'jian_ning'}   # 与年号撞名（建宁二年）


def build_lexicon(persons, places, rules, single_map=None):
    """返回 {(surface): [(type, id)]}，规则已在此时过滤掉 deny/drop"""
    lex, dropped = {}, []
    for p in persons:
        for s in p.get('match_surfaces', []):
            if s in rules.deny:
                dropped.append((s, 'person', p['id'], 'deny'))
                continue
            if ('person', p['id'], s) in rules.drops:
                dropped.append((s, 'person', p['id'], 'drop'))
                continue
            lex.setdefault(s, []).append(('person', p['id']))
    for pid, pl in places.items():
        if pid in EXCLUDE_PLACE_IDS:
            continue
        for s in {pl['name']} | set(pl.get('aliases') or []) | set(EXTRA_PLACE_ALIASES.get(pid, [])):
            if not s:
                continue
            if s in rules.deny:
                dropped.append((s, 'place', pid, 'deny'))
                continue
            if ('place', pid, s) in rules.drops:
                dropped.append((s, 'place', pid, 'drop'))
                continue
            lst = lex.setdefault(s, [])
            if ('place', pid) not in lst:
                lst.append(('place', pid))
    # 单字单称注入（末字唯一的人物）。与上面的全称/别称共存于同一 surface，
    # 匹配时由 allow() 决定用全称还是单称。
    for ch, pid in (single_map or {}).items():
        lst = lex.setdefault(ch, [])
        if ('person', pid) not in lst:
            lst.append(('person', pid))
    return lex, dropped


def match_paragraph(text, by_len, rules):
    """贪心最长匹配。候选被规则拦下时继续尝试更短的形式（如『中山靖王』拦下『靖』）。"""
    out = []
    i, n = 0, len(text)
    max_len = max(by_len) if by_len else 1
    while i < n:
        hit = None
        for L in range(min(max_len, n - i), 0, -1):
            cands = by_len.get(L)
            if not cands:
                continue
            seg = text[i:i + L]
            for (etype, eid) in cands.get(seg, ()):
                if rules.allow(etype, eid, seg, text, i, i + L):
                    hit = (i, i + L, seg, etype, eid)
                    break
            if hit:
                break
        if hit:
            out.append(hit)
            i = hit[1]
        else:
            i += 1
    return out


FACTION_META = {
    'han': ('东汉', '#8a7a5c'), 'warlord': ('群雄', '#7d7d7d'), 'wei': ('曹魏', '#2f5673'),
    'wu': ('孙吴', '#3f6b4f'), 'shu': ('蜀汉', '#9c2b1f'), 'jin': ('晋', '#6b4e7d'),
    'barbarian': ('异族', '#8a6a3a'), 'mystic': ('神怪', '#5d4a72'),
}
# 顺序与 entity-schema.json 的 enums.role_imperial / identity_priority 保持一致：
# 皇帝 > 追谥 > 君主 > 权臣 > 客君 > 亲族 > 文臣/武将 > 其他；
# 女眷不与上述竞争，单列在末段之前；「客君」（前朝君主降封）单列于其他之前。
ROLE_ORDER = ['皇帝', '追谥', '君主', '权臣', '亲族', '文臣', '武将', '女眷', '客君', '其他']


def main():
    meta = load_chapter_meta()
    persons = load_persons()
    places = load_places()
    rules, raw_rules = load_rules()
    single_map = apply_single_char(persons, rules, raw_rules)
    lex, dropped = build_lexicon(persons, places, rules, single_map)

    # 回指通道的候选表：{末字: [(person_id, 全称), ...]}，只收 anaphora.chars 里列的字
    ana_cfg = raw_rules.get('anaphora') or {}
    ana_chars = set(ana_cfg.get('chars') or []) - set(ana_cfg.get('exclude') or [])
    cand_map = {}
    for p in persons:
        nm = p['name']
        if len(nm) >= 2 and nm[-1] in ana_chars:
            cand_map.setdefault(nm[-1], []).append((p['id'], nm))

    by_len = {}
    for s, lst in lex.items():
        by_len.setdefault(len(s), {}).setdefault(s, []).extend(lst)

    os.makedirs(os.path.join(BUILD, 'chapters'), exist_ok=True)
    os.makedirs(os.path.join(BUILD, 'persons'), exist_ok=True)
    os.makedirs(os.path.join(BUILD, 'audit'), exist_ok=True)
    # 清理陈旧人物卡：合并去重/删卡后旧文件会留在磁盘上，导致目录数与数据不一致
    _live = {p['id'] for p in persons}
    for _old in glob.glob(os.path.join(BUILD, 'persons', '*.json')):
        if os.path.basename(_old)[:-5] not in _live:
            os.remove(_old)

    person_cnt = {p['id']: 0 for p in persons}
    place_cnt, place_chs = {}, {}
    chapters_out, all_passages = [], {}
    mentions_all = []

    for m in meta:
        paras = load_chapter_text(m['no'])
        passages, mentions = [], []
        for seq, text in enumerate(paras, 1):
            pid = m['no'] * 1000 + seq
            passages.append({'id': pid, 'seq': seq, 'text': text})
            hits = match_paragraph(text, by_len, rules)
            for h in hits:
                s, e, surface, etype, eid = h[0], h[1], h[2], h[3], h[4]
                mentions.append({'passage_id': pid, 'start': s, 'end': e, 'surface': surface,
                                 'entity_type': etype, 'entity_id': eid, 'source': 'dictionary',
                                 'confidence': 0.99, 'is_weak_link': False, 'reviewed': False})
                if etype == 'person':
                    person_cnt[eid] += 1
                else:
                    place_cnt[eid] = place_cnt.get(eid, 0) + 1
                    place_chs.setdefault(eid, set()).add(m['no'])
            # 词典匹配之后再补回指，两者不重叠：回指只填空位
            for (s, e, surface, etype, eid, conf, basis) in resolve_anaphora(text, hits, cand_map, ana_cfg):
                mentions.append({'passage_id': pid, 'start': s, 'end': e, 'surface': surface,
                                 'entity_type': etype, 'entity_id': eid, 'source': 'anaphora',
                                 'confidence': conf, 'is_weak_link': True, 'reviewed': False,
                                 'anaphora_basis': basis})
                # ★ resolve_anaphora 目前只产 person，但这里不能默认：一旦回指扩到
                #   地名（「其城」「此地」），person_cnt[eid] 会直接 KeyError。
                #   与上方词典分支共用同一套计数口径。
                if etype == 'person':
                    person_cnt[eid] += 1
                else:
                    place_cnt[eid] = place_cnt.get(eid, 0) + 1
                    place_chs.setdefault(eid, set()).add(m['no'])
        # 回指补进来的是乱序的，阅读器与覆盖率脚本都假设按 start 递增
        mentions.sort(key=lambda x: (x['passage_id'], x['start']))
        ch = {'chapter': {'id': m['no'], 'no': m['no'], 'title': m['title'],
                          'char_count': sum(len(p['text']) for p in passages),
                          'passage_count': len(passages), 'mention_count': len(mentions)},
              'passages': passages, 'mentions': mentions}
        json.dump(ch, io.open(os.path.join(BUILD, 'chapters', 'ch%03d.json' % m['no']), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        all_passages[m['no']] = passages
        mentions_all.extend(mentions)
        chapters_out.append({'no': m['no'], 'title': m['title'], 'status': m.get('status', 'annotated'),
                             'char_count': ch['chapter']['char_count'], 'mention_count': len(mentions),
                             'person_mentions': sum(1 for x in mentions if x['entity_type'] == 'person'),
                             'place_mentions': sum(1 for x in mentions if x['entity_type'] == 'place')})

    # 人物卡 + 索引
    for p in persons:
        card = {k: v for k, v in p.items() if not k.startswith('_') and k != 'match_surfaces'}
        card['mention_count'] = person_cnt.get(p['id'], 0)
        json.dump(card, io.open(os.path.join(BUILD, 'persons', p['id'] + '.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)

    # 地名投影
    for pid, pl in places.items():
        if pl.get('lng') is not None and pl.get('lat') is not None:
            pl['pixel_x'], pl['pixel_y'] = project(pl['lng'], pl['lat'])
            pl['tile_sheet'] = CANVAS['tile_sheet']
        else:
            pl['pixel_x'] = pl['pixel_y'] = pl['tile_sheet'] = None
        pl['mention_count'] = place_cnt.get(pid, 0)
        pl['chapters'] = sorted(place_chs.get(pid, []))
    places_out = sorted(places.values(), key=lambda p: (p.get('first_chapter') or 999, p['name']))
    json.dump(places_out, io.open(os.path.join(BUILD, 'places.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    # 地名三级归属（州—郡—县）：由 scripts/build_place_hierarchy.py 生成，缺失即报错，避免静默降级
    hpath = os.path.join(DATA, 'places-hierarchy.json')
    if not os.path.exists(hpath):
        raise SystemExit('缺少 data/places-hierarchy.json，请先运行 scripts/build_place_hierarchy.py')
    place_tree = json.load(io.open(hpath, encoding='utf-8'))
    ids = {p['id'] for p in places_out}
    # __seat_*：合成的州治县条目；__jun_*：合成的郡行（无点位卡，只用于亮郡界）
    missing = [it['id'] for it in place_tree['items']
               if it['id'] not in ids and not str(it['id']).startswith(('__seat_', '__jun_'))]
    if missing:
        raise SystemExit('places-hierarchy.json 含未知地名 id：%s' % missing[:5])

    # 事件与战役
    events_all, battles_all = [], []
    for f in sorted(glob.glob(os.path.join(DATA, 'event_battle_*.json'))):
        eb = json.load(io.open(f, encoding='utf-8'))
        for b in eb['battles']:
            for n in b['front_line']:
                n['pixel_x'], n['pixel_y'] = project(n['lng'], n['lat'])
            b['place_name'] = places.get(b['place_id'], {}).get('name', b['place_id'])
            assert len(b['front_line']) >= 3, b['id']
            assert all(b['front_line'][i]['time'] <= b['front_line'][i + 1]['time'] for i in range(len(b['front_line']) - 1)), b['id']
            battles_all.append(b)
        events_all.extend(eb['events'])
    os.makedirs(os.path.join(BUILD, 'battles'), exist_ok=True)
    os.makedirs(os.path.join(BUILD, 'events'), exist_ok=True)
    for b in battles_all:
        json.dump(b, io.open(os.path.join(BUILD, 'battles', b['id'] + '.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for ev in events_all:
        ev['battle_ids'] = [b['id'] for b in battles_all if b['event_id'] == ev['id']]
        json.dump(ev, io.open(os.path.join(BUILD, 'events', ev['id'] + '.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    # 全书索引
    book = {
        'book': {'title': '三国演义', 'author': '罗贯中', 'edition': '毛本 120 回', 'chapters_loaded': len(chapters_out)},
        'chapters': chapters_out,
        'stats': {
            'char_count': sum(c['char_count'] for c in chapters_out),
            'passage_count': sum(len(ps) for ps in all_passages.values()),
            'mention_count': len(mentions_all),
            'person_mentions': sum(1 for m in mentions_all if m['entity_type'] == 'person'),
            'place_mentions': sum(1 for m in mentions_all if m['entity_type'] == 'place'),
            'person_cards': len(persons),
            'place_total': len(places),
            'places_linked': len(place_cnt),
            'event_count': len(events_all),
            'battle_count': len(battles_all),
            'front_line_nodes': sum(len(b['front_line']) for b in battles_all),
            'lexicon_surfaces': len(lex),
            'rules_applied': len(raw_rules.get('rules', [])),
            'surfaces_blocked': len(dropped),
        },
        'canvas': CANVAS,
    }
    json.dump(book, io.open(os.path.join(BUILD, 'book.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    # 审计数据：按表面形式聚合，供 audit_mentions 复查
    audit = {}
    for m in mentions_all:
        k = '%s|%s|%s' % (m['entity_type'], m['entity_id'], m['surface'])
        a = audit.setdefault(k, {'entity_type': m['entity_type'], 'entity_id': m['entity_id'],
                                 'surface': m['surface'], 'count': 0, 'samples': []})
        a['count'] += 1
        if len(a['samples']) < 6:
            ps = all_passages[m['passage_id'] // 1000]
            text = next(p['text'] for p in ps if p['id'] == m['passage_id'])
            a['samples'].append({'ch': m['passage_id'] // 1000,
                                 'ctx': text[max(0, m['start'] - 10):m['start']] + '【' + m['surface'] + '】' + text[m['end']:m['end'] + 10]})
    json.dump({'surfaces': sorted(audit.values(), key=lambda x: -x['count']),
               'blocked': [{'surface': s, 'type': t, 'id': i, 'reason': r} for s, t, i, r in dropped]},
              io.open(os.path.join(BUILD, 'audit', 'surfaces.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    # 大势时间轴（13 州归属快照 × 逐年展开 × 在位者 × 当年事件）
    # 不让大势数据拖垮主构建，但**也不许静默**：失败时写一枚 .error 标记，
    # verify.py 会据此报 FAIL（内联 power=null + 前端降级提示两条断言）。
    # 2026-10 就是这么让大势页空白了很久而所有检查全 PASS 的。
    POWER_ERR = os.path.join(BUILD, 'power.error')
    try:
        import build_power
        power = build_power.build(persons, events_all)
        if os.path.exists(POWER_ERR):
            os.remove(POWER_ERR)
    except Exception as ex:                     # 不让大势数据拖垮主构建
        print('  ! 大势数据生成失败:', ex)
        print('    → 大势视图将整页空白；原因已写入 build/power.error，verify 会报错')
        io.open(POWER_ERR, 'w', encoding='utf-8').write('%s: %s\n' % (ex.__class__.__name__, ex))
        power = None

    # 前端数据
    reader_data = {
        'book': book['book'], 'chapters': chapters_out, 'stats': book['stats'],
        'canvas': CANVAS, 'geo': geo_for_client(),
        'passages': all_passages,
        'mentions': mentions_all,
        # 2026-10：内联人物补 mention_count（此前只在 build/persons 单卡里加，
        # 人物卡「提及 N 处」一直显示 0）
        'persons': {p['id']: dict({k: v for k, v in p.items() if not k.startswith('_') and k != 'match_surfaces'},
                                  mention_count=person_cnt.get(p['id'], 0)) for p in persons},
        'places': {p['id']: p for p in places_out},
        'place_tree': place_tree,
        'events': events_all, 'battles': battles_all,
        'factions': [{'id': k, 'name': v[0], 'color': v[1]} for k, v in FACTION_META.items()],
        'roles': ROLE_ORDER,
        'power': power,
        'scale_by_type': SCALE_BY_TYPE,
    }
    _write_app('reader_template.html', 'reader.html', reader_data)

    # 地图试验页
    map_data = {
        'canvas': CANVAS, 'geo': geo_for_client(),
        'places': [{'id': p['id'], 'name': p['name'], 'type': p['type'], 'x': p['pixel_x'], 'y': p['pixel_y'],
                    'lng': p['lng'], 'lat': p['lat'], 'modern': p.get('modern_name', ''),
                    'adm': p.get('ancient_admin', ''), 'prec': p.get('coord_precision', ''),
                    'ch': p.get('first_chapter'), 'zoom': zoom_for(p)} for p in places_out if p['pixel_x'] is not None],
        'battles': [{'id': b['id'], 'name': b['name'], 'event_id': b['event_id'], 'year': b['year'],
                     'date_text': b.get('date_text', ''), 'place_name': b['place_name'], 'summary': b['summary'],
                     'nodes': [{'seq': n['time_seq'], 'kind': n['kind'], 'label': n['label'], 'desc': n['desc'],
                                'x': n['pixel_x'], 'y': n['pixel_y']} for n in b['front_line']]} for b in battles_all],
        'events': [{'id': e['id'], 'name': e['name'], 'kind': e['kind'], 'summary': e['summary']} for e in events_all],
        'scale_by_type': SCALE_BY_TYPE,
    }
    _write_app('map_test_template.html', 'map_test.html', map_data)

    print('构建完成 %d 回' % len(chapters_out))
    print(json.dumps(book['stats'], ensure_ascii=False, indent=1))
    if dropped:
        print('\n被规则拦下的表面形式:')
        for s, t, i, r in dropped:
            print('  %-4s %-6s %-10s %s' % (s, t, i, r))


SCALE_BY_TYPE = {'都城': 2.6, '州域': 1.5, '郡治': 2.8, '重镇': 2.8, '城': 3.2, '县': 3.2,
                 '关隘': 3.4, '渡口': 3.0, '要津': 3.0, '战场': 3.0, '山': 3.0, '原': 3.0,
                 '水系': 1.2, '宫殿': 3.6, '陵墓': 3.6}


def zoom_for(p):
    return SCALE_BY_TYPE.get(p.get('type', ''), 3.0)


def _write_app(tpl_name, out_name, data):
    """模板 + 地图内核 + 数据 → app/xxx.html（数据内联，规避 file:// 的 CORS 限制）。

    地图内核 app/map_core.js 全项目只有一份，两个页面共用同一个占位符注入，
    从机制上杜绝「改了一处另一处没改」的双轨漂移。
    """
    core = io.open(os.path.join(APP, 'map_core.js'), encoding='utf-8').read()
    tpl = io.open(os.path.join(APP, tpl_name), encoding='utf-8').read()
    if '/*__MAPCORE__*/' not in tpl:
        raise SystemExit('模板缺少 /*__MAPCORE__*/ 占位符：' + tpl_name)
    # 已生成头像清单：只对存在的头像插 <img>，避免缺图时成批 404 请求拖慢加载
    avs = sorted(os.path.basename(p)[:-4] for p in
                 glob.glob(os.path.join(APP, 'assets', 'avatars', '*.png')))
    html = (tpl.replace('/*__MAPCORE__*/', core)
               .replace('/*__AVATARS__*/[]', json.dumps(avs))
               .replace('/*__DATA__*/null', json.dumps(data, ensure_ascii=False)))
    io.open(os.path.join(APP, out_name), 'w', encoding='utf-8').write(html)


if __name__ == '__main__':
    main()
