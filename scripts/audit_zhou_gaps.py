# -*- coding: utf-8 -*-
"""州界缝隙扫描（P2-R 收口项）。

待办原文：「写脚本扫『到最近它州界距离 0–2px』的相邻区域，输出坐标清单（现靠肉眼发现）」。

两层检查：
  A. 数据层——shapely 对每对州多边形算距离。共享弧机制理论上让相邻州距离为 0
     （逐点一致），凡 >0 即逻辑缝隙，输出缝隙位置与宽度（px）。
  B. 三州共点——找出现 ≥3 次的共享坐标点，核对三州在该点的坐标是否精确一致；
     三州共点是最容易因手工取点误差产生三角微缝的地方。

用法：
  python scripts/audit_zhou_gaps.py            # 扫描并打印
  python scripts/audit_zhou_gaps.py --max 0.5  # 只看宽度大于 0.5px 的缝隙
退出码：发现超容差缝隙 → 1（可接 CI）。
"""
import io
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 画布参数与 build/book.json canvas 一致（px 换算用）
CANVAS = {'w': 1400, 'h': 1200, 'lng0': 97.0, 'lng1': 126.0, 'lat0': 18.0, 'lat1': 44.0}


def px_per_deg():
    return (CANVAS['w'] / (CANVAS['lng1'] - CANVAS['lng0']),
            CANVAS['h'] / (CANVAS['lat1'] - CANVAS['lat0']))


def load_zhou():
    g = json.load(io.open(os.path.join(ROOT, 'data', 'geo-real.json'), encoding='utf-8'))
    return {z['name']: z['pts'] for z in g['zhoupoly']}


def audit_distances(zhou, max_px):
    """A. 相邻州多边形距离。相邻判据：两州共享 ≥3 个坐标点（共享边界弧平滑后
    整条弧逐点一致）。不相邻州对之间的距离是自然间隔，不是缝隙。"""
    from shapely.geometry import Polygon
    shared = {}
    for n, ps in zhou.items():
        for p in ps:
            shared.setdefault(tuple(p), set()).add(n)
    touch = {}
    for k, ns in shared.items():
        ns = sorted(ns)
        for i, a in enumerate(ns):
            for b in ns[i + 1:]:
                touch.setdefault((a, b), 0)
                touch[(a, b)] += 1
    names = list(zhou)
    polys = {n: Polygon(zhou[n]) for n in names}
    bad = 0
    adjacent = 0
    for (a, b), nshare in sorted(touch.items()):
        if nshare < 3:
            continue          # 只共享 1–2 个点 = 仅端点相触（三州交汇），无公共边
        adjacent += 1
        d_deg = polys[a].distance(polys[b])
        if d_deg == 0:
            continue
        kx, ky = px_per_deg()
        d_px = d_deg * max(kx, ky)
        if d_px <= max_px:
            continue
        try:
            from shapely.ops import nearest_points
            pa, pb = nearest_points(polys[a], polys[b])
            at = '(%0.3f,%0.3f)' % (pa.x, pa.y)
        except Exception:
            at = '?'
        print('  缝隙 %s ↔ %s（共享 %d 点）：%0.4f° ≈ %0.2fpx，最近点 %s'
              % (a, b, nshare, d_deg, d_px, at))
        bad += 1
    print('  A. 数据层：相邻州对 %d 对（公共边），%s'
          % (adjacent, '全部距离为 0，无逻辑缝隙' if not bad else '以上 %d 对存在缝隙' % bad))
    return bad


def audit_triple_points(zhou):
    """B. 三州共点核对：≥3 州使用的坐标点必须逐字节一致；并检查共点 <2px
    （0.05°）范围内有无某州「漂移副本」——未被合并的手工取点误差。
    注意：共享弧上的正常采样点与共点距 0.1–0.4°，阈值必须远小于它，否则误报。"""
    DRIFT = 0.05            # ≈2px，肉眼可见微缝的量级
    seen = {}
    for n, ps in zhou.items():
        for p in ps:
            seen.setdefault(tuple(p), set()).add(n)
    triples = {k: v for k, v in seen.items() if len(v) >= 3}
    bad = 0
    for k, ns in sorted(triples.items()):
        near = {}
        for n in ns:
            for p in zhou[n]:
                d = math.hypot(p[0] - k[0], p[1] - k[1])
                if 0 < d < DRIFT:
                    near.setdefault(n, []).append((round(d, 3), p))
        if near:
            print('  三州共点 %s（%s）%dpx 内存在漂移副本：' % (str(k), '/'.join(sorted(ns)), DRIFT * 48))
            for n, lst in near.items():
                print('    %s: %s' % (n, lst[:3]))
            bad += 1
    if triples:
        print('  B. 三州共点：%d 处（%s）——%s'
              % (len(triples),
                 '；'.join('/'.join(sorted(ns)) for k, ns in sorted(triples.items())),
                 '全部精确共享、无漂移副本' if not bad else '以上 %d 处有漂移副本' % bad))
    else:
        print('  B. 三州共点：未发现')
    return bad


def main():
    max_px = 0.5
    if '--max' in sys.argv:
        max_px = float(sys.argv[sys.argv.index('--max') + 1])
    zhou = load_zhou()
    print('州界缝隙扫描（%d 州，容差 %0.2fpx）' % (len(zhou), max_px))
    bad = audit_distances(zhou, max_px)
    bad += audit_triple_points(zhou)
    print('结论：%s' % ('发现 %d 处问题' % bad if bad else '全部干净'))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
