#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把东汉底表（data/counties-han.json，342 县）里尚未收录的县补进 build/places.json。

背景
----
`places.json` 是「地图上会出点位、可搜索、有行政区划」的地点全集，但它是按
《演义》叙事逐步攒起来的，只覆盖了 147 条，底表 342 个县里只有 60 个能按名/别名
命中。于是出现两种硬伤：

  · 读者在地图上看到某郡，点进去却查不到该郡的县；
  · 「郡治标记」用的是郡名（汝南、汉中），底表治所是县名（平舆、南郑），
    两边对不上——校验里 21/38 个郡治标记报「与底表治所不一致」。

本脚本做的事
------------
  · 底表 `t=都` 的县（郡治）→ type=`郡治`，附 `seat_of`=所治郡名；
  · 底表 `t=县` 的县 → type=`县`；
  · 两者统一 `ancient_admin`=`州·郡`，`lng/lat` 取底表坐标，投影出 pixel_x/pixel_y；
  · 已存在的地点（按名字或别名命中）不重复添加，只补 `seat_of` / `ancient_admin`。

不覆盖人工写的内容：`note`、`modern_name`、`first_chapter` 等字段若已有值则保留。
新增条目的 `first_chapter` 记为 None（该县在正文中未被点名），
`note` 写「东汉底表县，正文未点名」，前端据此可单独分组或隐藏。

★ 输出去向（2026-10 修正）
--------------------------
本脚本必须写进 `data/places-additions.json`，**不能**写 `build/places.json`。
`build/` 是 `scripts/build.py` 的**产物目录**：`load_places()` 只读
`data/places-seed.csv` + `data/places-additions.json`，然后**整体覆写**
`build/places.json`。原先写 build/ 的后果是：每跑一次 build.py，282 条底表县
就被冲掉，而 `data/places-hierarchy.json` 里 283 条 `c_州_郡_县` id 全部
变成「未知地名」→ build.py 直接 SystemExit。
新增条目并进 additions 的 `places` 数组后，build.py 下次构建会一并带上，
层级树里的 id 也就对得上了。

用法：
  python3 scripts/fill_counties_into_places.py [--dry]
"""
import json, io, os, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# ★ 源文件：build.py 的 load_places() 从这里读，见文件头说明
P_ADD = os.path.join(ROOT, 'data', 'places-additions.json')
P_CNTY = os.path.join(ROOT, 'data', 'counties-han.json')

AX, BX, AY, BY = 39.5608, -3711.03, -46.1517, 2030.70

additions = json.load(io.open(P_ADD, encoding='utf-8'))
places = additions['places']
counties = json.load(io.open(P_CNTY, encoding='utf-8'))['counties']

# 检索键索引：name / aliases → 地点对象
key2obj = {}
for pl in places:
    key2obj.setdefault(pl['name'], pl)
    for a in pl.get('aliases') or []:
        key2obj.setdefault(a, pl)

# ★ 2026-10：判重必须把 seed（data/places-seed.csv）也算进去。
#   places.json = seed + additions，fill 只看 additions 时，底表里「长安、谯、
#   平原、襄平、秣陵」等已由 seed 收录的县会被再次新增（type=县/郡治，id=c_州_郡_县），
#   build 后 places.json 出现同名同郡的两条 → 校验「无重复同名地点」整片报红。
#   seed 命中时走与 additions 命中相同的「只补 seat_of / 别名」分支即可。
import csv as _csv
with io.open(os.path.join(ROOT, 'data', 'places-seed.csv'), encoding='utf-8-sig') as _f:
    for _r in _csv.DictReader(_f):
        for _k in ('古名', '别名'):
            _v = (_r.get(_k) or '').strip()
            if not _v or _v == '—':
                continue
            for _n in _v.replace('；', ',').replace('、', ',').split(','):
                _n = _n.strip()
                if _n:
                    key2obj.setdefault(_n, {'name': _n, '__seed__': True})


def slug(z, j, n):
    """稳定 id：州_郡_县（ASCII 化交给前端无所谓，这里只要唯一、可复现）。"""
    s = '%s_%s_%s' % (z, j, n)
    return 'c_' + s.replace('·', '_')


added, patched, skipped = [], 0, 0
seen_ids = {pl['id'] for pl in places}

for c in counties:
    n, z, j = c['n'], c['p'], c['a']
    is_seat = (c.get('t') == '都')
    hit = key2obj.get(n)

    if hit is not None:
        # 已有条目：补 seat_of（只对郡治县）与实际行政区划。
        # ★ 注意：都城/州治也是郡治县（长安=京兆尹治、蓟=广阳郡治、彭城=彭城国治），
        #   它们以更高优先级类型先入了册，若只按 type=='郡治' 判定就会漏标 seat_of，
        #   于是「有治所的郡都标了郡治」永远差那 15 个郡。这里对任何已存在条目都补。
        if is_seat:
            if hit.get('seat_of') != j:
                hit['seat_of'] = j
                patched += 1
            if not hit.get('ancient_admin'):
                hit['ancient_admin'] = '%s·%s' % (z, j)
            # 记录治所县名，便于校验与检索（如 长安 / 蓟 / 彭城）
            al = hit.setdefault('aliases', [])
            if n != hit['name'] and n not in al:
                al.append(n)
        continue

    pid = slug(z, j, n)
    k = 2
    base = pid
    while pid in seen_ids:
        pid = '%s_%d' % (base, k)
        k += 1
    seen_ids.add(pid)

    obj = {
        'id': pid,
        'name': n,
        'aliases': [],
        'type': '郡治' if is_seat else '县',
        'modern_name': '',
        'province': '',
        'lng': c['lng'],
        'lat': c['lat'],
        'ancient_admin': '%s·%s' % (z, j),
        'first_chapter': None,
        'coord_precision': '精确',
        'coord_note': '东汉底表县治',
        'note': '东汉底表%s，正文未点名' % ('郡治' if is_seat else '县'),
        'pixel_x': round(AX * c['lng'] + BX, 1),
        'pixel_y': round(AY * c['lat'] + BY, 1),
        'mention_count': 0,
        'chapters': [],
    }
    if is_seat:
        obj['seat_of'] = j
    places.append(obj)
    added.append((n, z, j, obj['type']))

print('新增 %d 条，补 seat_of %d 条' % (len(added), patched))
from collections import Counter
print('  新增类型分布：', Counter(t for _, _, _, t in added))

# ── 自检 ────────────────────────────────────────────────────────────────────
key2obj = {}
for pl in places:
    key2obj.setdefault(pl['name'], pl)
    for a in pl.get('aliases') or []:
        key2obj.setdefault(a, pl)
miss = [c['n'] for c in counties if c['n'] not in key2obj]
print('底表 %d 县，收录 %d，仍缺 %d %s'
      % (len(counties), len(counties) - len(miss), len(miss), miss[:10]))

# 每个郡是否都有郡治标记
# ★ 判定用 `seat_of` 而不是 `type=='郡治'`：长安是「都城」、江陵是「重镇」、
#   彭城是「州治」、蓟是「州域」的别称——它们同时是郡治，type 只有一个槽位，
#   不能用 type 来判断「这个郡有没有标出治所」。
by_jun = defaultdict(list)
for pl in places:
    if pl.get('seat_of'):
        by_jun[pl['seat_of']].append(pl['name'])
need = {c['a'] for c in counties if c.get('t') == '都'}
no_seat = sorted(need - set(by_jun))
print('有底表治所的郡 %d 个，已标郡治 %d 个，缺 %d %s'
      % (len(need), len(need & set(by_jun)), len(no_seat), no_seat[:10]))

if '--dry' in sys.argv:
    print('（--dry：不写盘）')
    sys.exit(0)

json.dump(additions, io.open(P_ADD, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('已写回 %s（共 %d 条）' % (os.path.relpath(P_ADD, ROOT), len(places)))
