# -*- coding: utf-8 -*-
"""大势时间轴数据整理（郡级版）。

输入  data/power.json（42 势力 + 28 个快照年的郡级归属，人手维护）
      build/junpoly.json（124 郡多边形，像素坐标）
      persons（build.py 里已加载校验的人物卡，取 tenure 时间片）
      events（事件表，取 start_year）
输出  build/power.json（供阅读器「大势」视图直接渲染），
      同时被 build.py 内联进 reader.html。

设计要点：
- 归属到郡（124 郡），每快照每郡恰一主；势力边界由前端用郡多边形拓扑实时算出
  （共享边两侧归属不同即画界），本脚本不做并集面。
- labels：用 shapely 预计算每快照每势力的注记锚点（势力多边形最大连通块的
  representative point），前端只管摆字，不算几何。
- zhou_labels：13 州的注记锚点（州域质心），静态，底图州界虚线旁标小字。
- 中间年份取「小于等于该年的最近快照」，回传真实快照年 from。
"""
import json
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
BUILD = os.path.join(ROOT, 'build')

LORDSHIP_ROLES = ('皇帝', '追谥', '君主', '权臣')

# 画布外的郡（敦煌）——口径与 build_junpoly.py / audit_power.py 共用同一份，
# 释义见 scripts/geo_const.py。原先这里、audit_power.py 各写一份、build_junpoly.py
# 又写 DROP_JUN，三处一旦不同步就是「构建静默降级、页面整页空白」。
from geo_const import OFFCANVAS_JUN  # noqa: E402


def load_src():
    return json.load(io.open(os.path.join(DATA, 'power.json'), encoding='utf-8'))


def _load_junpoly():
    p = os.path.join(BUILD, 'junpoly.json')
    if not os.path.exists(p):
        return []
    return json.load(io.open(p, encoding='utf-8'))


def _polygons(rec):
    """郡面 → shapely 多边形列表（pts 为主环，extra 为飞地/岛环）。"""
    from shapely.geometry import Polygon
    out = []
    rings = [rec['pts']] + [e for e in (rec.get('extra') or []) if len(e) >= 3]
    for r in rings:
        try:
            g = Polygon(r)
            if not g.is_valid:
                g = g.buffer(0)
            if g.area > 0:
                out.append(g)
        except Exception:
            pass
    return out


def _validate(src, jun_names):
    errs = []
    fids = {f['id'] for f in src['factions']}
    if len(fids) != len(src['factions']):
        errs.append('factions 存在重复 id')
    juns = sorted({j for jl in src['juns'].values() for j in jl})
    zhou_names = set(src['juns'])
    for jl in src['juns'].values():
        for z in zhou_names:
            if z in jl:
                errs.append('juns[%s] 里混入州名' % z)
    if set(juns) - OFFCANVAS_JUN != set(jun_names) - OFFCANVAS_JUN:
        errs.append('juns 与 junpoly 郡名不一致：多 %s 少 %s'
                    % (sorted((set(juns) - OFFCANVAS_JUN) - set(jun_names))[:5],
                       sorted((set(jun_names) - OFFCANVAS_JUN) - set(juns))[:5]))
    for child, parent in (src.get('follow') or {}).items():
        if parent not in juns:
            errs.append('follow 子郡 %s 的母郡 %s 不存在' % (child, parent))
    for y, snap in sorted(src['snapshots'].items(), key=lambda kv: int(kv[0])):
        seen = {}
        for fid, jl in snap['hold'].items():
            if fid not in fids:
                errs.append('%s 未知势力 %s' % (y, fid))
                continue
            for j in jl:
                if j in seen:
                    errs.append('%s 郡 %s 被重复声明（%s / %s）' % (y, j, seen[j], fid))
                seen[j] = fid
        missing = [j for j in juns if j not in seen]
        if missing:
            errs.append('%s 缺归属的郡：%s' % (y, '、'.join(missing[:8])))
        for j, fid in (snap.get('contest') or {}).items():
            if fid not in fids:
                errs.append('%s contest 未知势力 %s' % (y, fid))
            if j not in seen:
                errs.append('%s contest 郡 %s 无主' % (y, j))
    return errs


def _label_anchors(snaps, jun_recs):
    """每快照：每势力的注记锚点 = 该势力郡面并集最大连通块的标签点。
    取点规则：质心落在域内 → 用质心（视觉上最居中）；质心在域外（凹形/狭长域，
    如魏的「中原+河西走廊」带）→ 取域上离质心最近的点——不许用 representative
    point，它可能甩到走廊远端（214 年曹操标签因此落过西凉）。"""
    from shapely.ops import unary_union, nearest_points
    def _anchor(big):
        pt = big.centroid
        if not pt.within(big):
            pt = nearest_points(big, pt)[0]
        return pt
    # ★ 2026-10-29 用户定案：
    #   a) 献帝被挟持入许昌（196 年）之后，凡据有帝都三城之一且**未称帝**的势力，
    #      注记锚到该城，同时据其二/其三时按 许昌 > 洛阳 > 长安 优先级取一；
    #   b) **已称帝**的势力，注记锚其都城（魏→洛阳、蜀→成都、吴→建业、晋→洛阳、
    #      袁术 197 年称帝→寿春；汉室朝廷随帝驾：190 迁长安、196 迁许）。
    #   城坐标取自 build/places.json。
    places_idx = {}
    _pf = os.path.join(ROOT, 'build', 'places.json')
    if os.path.exists(_pf):
        for _p in json.load(io.open(_pf, encoding='utf-8')):
            places_idx[_p['name']] = (_p.get('pixel_x'), _p.get('pixel_y'))
    CAPITALS = [   # 未称帝势力的三城锚（顺序即优先级：hold 中的郡名, 城点名）
        ('颍川郡', '许'), ('河南尹', '洛阳'), ('京兆尹', '长安'),
    ]
    CAPITALS = [(jn, nm, places_idx[nm]) for jn, nm in CAPITALS
                if nm in places_idx and places_idx[nm][0] is not None]
    def _cap(nm):
        return places_idx.get(nm) if places_idx.get(nm) and places_idx[nm][0] is not None else None
    EMPIRE = [     # (势力 id, 称帝年起, 都城点位)——优先于三城规则
        ('wei', 220, _cap('洛阳')), ('shu', 221, _cap('成都')),
        ('wu', 229, _cap('建业')), ('jin', 265, _cap('洛阳')),
        ('yuan_shu', 197, _cap('寿春')),
    ]
    HAN_CAPITAL = lambda y: (None if y < 190 else _cap('长安')) if y < 196 else _cap('许')
    recs = {r['name']: r for r in jun_recs}
    zhou_pts = {}
    zhou_groups = {}
    for r in jun_recs:
        zhou_groups.setdefault(r['zhou'], []).append(r)
    for z, rs in zhou_groups.items():
        u = unary_union([g for r in rs for g in _polygons(r)])
        if u.is_empty:
            continue
        biggest = max(u.geoms, key=lambda g: g.area) if u.geom_type == 'MultiPolygon' else u
        pt = _anchor(biggest)
        zhou_pts[z] = [round(pt.x, 1), round(pt.y, 1)]
    out = {}
    for y, snap in sorted(snaps.items(), key=lambda kv: int(kv[0])):
        labels = {}
        groups = {}
        for fid, jl in snap['hold'].items():
            groups.setdefault(fid, []).extend(recs[j] for j in jl if j in recs)
        for fid, rs in groups.items():
            # b) 称帝势力 → 都城
            cap = None
            if fid == 'han':
                cap = HAN_CAPITAL(int(y))
            else:
                for efid, estart, exy in EMPIRE:
                    if efid == fid and int(y) >= estart:
                        cap = exy
                        break
            # a) 未称帝 + 196 年起 + 据帝都三城 → 三城锚（许昌>洛阳>长安）
            if cap is None and int(y) >= 196:
                held = set(snap['hold'].get(fid) or [])
                for jn, nm, xy in CAPITALS:
                    if jn in held:
                        cap = xy
                        break
            if cap:
                labels[fid] = [round(cap[0], 1), round(cap[1], 1)]
                continue
            u = unary_union([g for r in rs for g in _polygons(r)])
            if u.is_empty:
                continue
            biggest = max(u.geoms, key=lambda g: g.area) if u.geom_type == 'MultiPolygon' else u
            pt = _anchor(biggest)
            labels[fid] = [round(pt.x, 1), round(pt.y, 1)]
        out[int(y)] = {'hold': snap['hold'], 'contest': snap.get('contest') or {},
                       'note': snap.get('note') or '', 'labels': labels}
    return out, zhou_pts


def build(persons, events):
    src = load_src()
    jun_recs = _load_junpoly()
    errs = _validate(src, {r['name'] for r in jun_recs})
    if errs:
        raise ValueError('power.json 校验失败：\n  ' + '\n  '.join(errs))

    snaps = src['snapshots']
    # ── 画布外的郡不进渲染数据 ────────────────────────────────────────────
    # data/power.json（史实归属，人手维护）保留敦煌郡的归属；但 build/junpoly.json
    # 没有它的郡面，前端要靠郡面并集算势力边界、靠 hold 的键集合对齐郡面，
    # 多出来一个画不出来的郡只会让「每快照 123 郡恰一主」这类断言永远不成立。
    # 故在**这一步**剔除：源里不动，渲染数据里不出现。
    if OFFCANVAS_JUN:
        snaps = {y: {
            'note': s.get('note'),
            'hold': {fid: [j for j in jl if j not in OFFCANVAS_JUN]
                     for fid, jl in (s.get('hold') or {}).items()},
            'contest': {j: f for j, f in (s.get('contest') or {}).items()
                        if j not in OFFCANVAS_JUN},
            'labels': s.get('labels') or {},
        } for y, s in snaps.items()}
        snaps = {y: {**s, 'hold': {fid: jl for fid, jl in s['hold'].items() if jl}}
                 for y, s in snaps.items()}
    factions = src['factions']
    fmap = {f['id']: f for f in factions}
    snap_years = sorted(int(y) for y in snaps)
    lo, hi = snap_years[0], snap_years[-1]

    snap_data, zhou_pts = _label_anchors(snaps, jun_recs)
    snap_map = {int(y): snap_data[int(y)] for y in snaps}

    # 人物名 → 势力 id（用 faction.leader 反查，把在位者挂到对应势力）
    by_leader = {}
    for f in factions:
        if f.get('leader'):
            by_leader.setdefault(f['leader'], []).append(f['id'])

    # ---- 在位者：按年展开 tenure ----
    # 同一人同一年可能有多段（如孙权 229 年「君主」段收尾、「皇帝」段开头），
    # 只保留位阶最高的一段，否则「在位者」栏会把同一个人列两遍。
    ROLE_RANK = {'皇帝': 0, '君主': 1, '权臣': 2, '追谥': 3}
    best = {}      # (y, pid) -> (rank, tenure, fid)
    for p in persons:
        pid = p['id']
        for t in p.get('tenure') or []:
            role = t.get('role')
            if role not in LORDSHIP_ROLES:
                continue
            st = t.get('start_year')
            if st is None:
                continue
            e = t.get('end_year') or hi
            cands = by_leader.get(p['name']) or []
            fid = cands[0] if cands else None
            rank = ROLE_RANK.get(role, 9)
            for y in range(max(st, lo), min(e, hi) + 1):
                k = (y, pid)
                if k not in best or rank < best[k][0]:
                    best[k] = (rank, t, fid)

    lords_by_year = {}
    for (y, pid), (rank, t, fid) in best.items():
        p = next(q for q in persons if q['id'] == pid)
        lords_by_year.setdefault(y, []).append({
            'name': p['name'], 'person': pid, 'role': t.get('role'),
            'title': t.get('title') or '', 'faction': t.get('faction_id'),
            'fid': fid, 'courtesy': p.get('courtesy') or '',
        })

    # ---- 事件：按年挂 ----
    ev_by_year = {}
    for e in events:
        y = e.get('start_year')
        if not y or y < lo or y > hi:
            continue
        ev_by_year.setdefault(y, []).append({
            'id': e['id'], 'name': e['name'], 'kind': e.get('kind') or '',
            'place': e.get('place_name') or '', 'summary': (e.get('summary') or '')[:60],
            'battles': len(e.get('battle_ids') or []),
        })

    # ---- 逐年展开 ----
    by_year = {}
    cur = None
    for y in range(lo, hi + 1):
        if y in snap_map:
            cur = y
        snap = snap_map[cur]
        lords = lords_by_year.get(y, [])
        order = {'皇帝': 0, '追谥': 1, '君主': 2, '权臣': 3}
        lords.sort(key=lambda x: (order.get(x['role'], 9), 0 if x['fid'] else 1, x['name']))
        by_year[y] = {
            'from': cur,
            'note': snap['note'],
            'lords': lords,
            'events': sorted(ev_by_year.get(y, []), key=lambda x: x['name']),
        }

    # ---- 势力存续区间（用于时间条） ----
    span = {}
    for sy, snap in snap_map.items():
        for fid in snap['hold']:
            s = span.setdefault(fid, [sy, sy])
            s[0] = min(s[0], sy)
            s[1] = max(s[1], sy)

    return {
        'years': list(range(lo, hi + 1)),
        'snap_years': snap_years,
        'zhou_order': src['zhou_order'],
        'zhou_labels': zhou_pts,
        'factions': factions,
        'spans': span,
        'snapshots': {str(y): snap_map[y] for y in sorted(snap_map)},
        'byYear': by_year,
    }


def main():
    import glob
    persons = []
    for f in sorted(glob.glob(os.path.join(DATA, 'persons_*.json'))):
        persons.extend(json.load(io.open(f, encoding='utf-8'))['persons'])
    events = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'build', 'events', '*.json'))):
        d = json.load(io.open(f, encoding='utf-8'))
        events.extend(d if isinstance(d, list) else [d])
    uniq = {}
    for e in events:
        if e.get('id'):
            uniq[e['id']] = e
    events = list(uniq.values())
    out = build(persons, events)
    p = os.path.join(BUILD, 'power.json')
    json.dump(out, io.open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('写出 %s：%d 年 / %d 势力 / 快照年 %s'
          % (p, len(out['years']), len(out['factions']), out['snap_years']))
    for y in out['snap_years']:
        d = out['byYear'][y]
        snap = out['snapshots'][str(y)]
        print('  %d：主 %d 家 / 争夺 %d 郡 / 注记 %d 个，在位 %d 人，事件 %d 条 — %s'
              % (y, len(snap['hold']), len(snap['contest']), len(snap['labels']),
                 len(d['lords']), len(d['events']), d['note'][:24]))


if __name__ == '__main__':
    main()
