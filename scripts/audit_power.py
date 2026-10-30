# -*- coding: utf-8 -*-
"""大势数据自查（对 data/power.json 与 build/power.json 做独立断言）。

用法：python3 scripts/audit_power.py   （在 build_power.py 之后运行）
"""
import json
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
BUILD = os.path.join(ROOT, 'build')

W, H = 1400, 1200

# 画布外的郡——与 build_power.py / build_junpoly.py 共用同一份口径，见 geo_const.py
from geo_const import OFFCANVAS_JUN  # noqa: E402

FAILS = []


def check(name, ok, detail=''):
    print('%s %s%s' % ('OK  ' if ok else 'FAIL', name, (' — ' + detail) if detail and not ok else ''))
    if not ok:
        FAILS.append(name + ((' — ' + detail) if detail else ''))


def main():
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    src = json.load(io.open(os.path.join(DATA, 'power.json'), encoding='utf-8'))
    out = json.load(io.open(os.path.join(BUILD, 'power.json'), encoding='utf-8'))
    jprecs = json.load(io.open(os.path.join(BUILD, 'junpoly.json'), encoding='utf-8'))
    recs = {r['name']: r for r in jprecs}

    fids = [f['id'] for f in src['factions']]
    fmap = {f['id']: f for f in src['factions']}
    juns = sorted({j for jl in src['juns'].values() for j in jl})

    # 1 势力表
    check('势力 id 唯一', len(set(fids)) == len(fids))
    bad_color = [f['id'] for f in src['factions']
                 if not (isinstance(f.get('color'), str) and len(f['color']) == 7
                         and f['color'].startswith('#'))]
    check('势力 color 均为 #rrggbb', not bad_color, str(bad_color))
    check('含 none（不属/不明）', 'none' in fmap)
    for k in ('han', 'wei', 'shu', 'wu', 'jin'):
        check('含王朝势力 %s' % k, k in fmap)

    # 2 郡面覆盖
    oncan = set(juns) - OFFCANVAS_JUN
    check('juns 与 junpoly 完全一致（画布外郡除外）', oncan == set(recs),
          '多%s 少%s' % (oncan - set(recs), set(recs) - oncan))
    check('郡数 = 123（不含画布外 %d）' % len(OFFCANVAS_JUN),
          len(oncan) == 123, str(len(oncan)))

    # 3 快照归属完备性
    for y, snap in sorted(src['snapshots'].items(), key=lambda kv: int(kv[0])):
        seen = {}
        dup = []
        for fid, jl in snap['hold'].items():
            if fid not in fmap:
                dup.append('未知势力 ' + fid)
            for j in jl:
                if j in seen:
                    dup.append('%s 被 %s/%s 重复' % (j, seen[j], fid))
                seen[j] = fid
        miss = [j for j in juns if j not in seen]
        check('%s：123 郡恰一主' % y, not dup and not miss,
              '重复%s 缺%s' % (dup[:3], miss[:5]))
        bad_c = [j for j in (snap.get('contest') or {})
                 if j not in seen or (snap.get('contest') or {})[j] not in fmap]
        check('%s：contest 郡有主且势力合法' % y, not bad_c, str(bad_c))
        # 4 注记锚点在画布内且落在自家多边形内
        lbl = out['snapshots'].get(str(y), {}).get('labels', {})
        off = [fid for fid, (x, y2) in lbl.items() if not (0 <= x <= W and 0 <= y2 <= H)]
        check('%s：注记锚点在画布内' % y, not off, str(off))

    # 5 锚点落多边形内（全量）
    from shapely.geometry import Point
    bad_in = []
    for sy, osnap in out['snapshots'].items():
        for fid, (x, y2) in osnap['labels'].items():
            polys = []
            for j in osnap['hold'].get(fid, []):
                r = recs.get(j)
                if not r:
                    continue
                for ring in [r['pts']] + [e for e in (r.get('extra') or []) if len(e) >= 3]:
                    g = Polygon(ring)
                    if not g.is_valid:
                        g = g.buffer(0)
                    if g.area > 0:
                        polys.append(g)
            if not polys:
                bad_in.append('%s/%s 无面' % (sy, fid))
                continue
            u = unary_union(polys)
            biggest = max(u.geoms, key=lambda g: g.area) if u.geom_type == 'MultiPolygon' else u
            # covers 而非 contains：锚点允许落在边界上（质心出界时取「域上离质心最近的点」，
            # nearest_points 结果可能恰在边界，2026-10 取点规则变更）
            # ★ 2026-10-29 豁免 han：汉室锚定帝驾城（190 长安/196 许），帝驾所在
            #   不在朝廷名义郡面内属定案行为，不按几何规则校验。
            if fid != 'han' and not biggest.covers(Point(x, y2)):
                bad_in.append('%s/%s 锚点出界' % (sy, fid))
    check('注记锚点均落在该势力最大连通块内', not bad_in, str(bad_in[:5]))

    # 6 build 输出与 data 一致
    check('build 快照年数 = %d（同 data）' % len(src['snapshots']),
          len(out['snap_years']) == len(src['snapshots']),
          'build %d / data %d' % (len(out['snap_years']), len(src['snapshots'])))
    check('build 年份连续 184..280', out['years'] == list(range(184, 281)))
    ok_from = all(out['byYear'][str(y)]['from'] <= y for y in out['years'])
    check('byYear.from ≤ 当年', ok_from)
    mism = []
    for y, osnap in out['snapshots'].items():
        ssnap = src['snapshots'][y]
        # 源数据含画布外郡，build 剔除了它——比对前按同一口径归一
        want_hold, want_contest = {}, {}
        for fid, jl in (ssnap.get('hold') or {}).items():
            keep = [j for j in jl if j not in OFFCANVAS_JUN]
            if keep:
                want_hold[fid] = keep
        for j, f in (ssnap.get('contest') or {}).items():
            if j not in OFFCANVAS_JUN:
                want_contest[j] = f
        if osnap['hold'] != want_hold or osnap['contest'] != want_contest:
            mism.append(y)
    check('build 快照与 data 完全一致', not mism, str(mism))
    check('13 州注记锚点齐全', set(out['zhou_labels']) == set(src['juns']),
          str(set(src['juns']) - set(out['zhou_labels'])))
    offz = [z for z, (x, y2) in out['zhou_labels'].items() if not (0 <= x <= W and 0 <= y2 <= H)]
    check('州注记锚点在画布内', not offz, str(offz))

    # 7 势力存续区间
    bad_span = [f for f, (a, b) in out['spans'].items() if not (184 <= a <= b <= 280)]
    check('势力存续区间合法', not bad_span, str(bad_span))
    holdfids = {fid for osnap in out['snapshots'].values() for fid in osnap['hold']}
    check('spans 与快照势力一致', set(out['spans']) == holdfids,
          str(set(out['spans']) ^ holdfids))

    print()
    if FAILS:
        print('自查失败 %d 项' % len(FAILS))
        sys.exit(1)
    print('自查全部通过')


if __name__ == '__main__':
    main()
