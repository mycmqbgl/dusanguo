#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 `fill_counties_into_places.py` 批量补进来的重复条目并回原生条目。

问题
----
`fill_counties_into_places.py` 按「县名」在 places 里找同名条目，命中就不加。
但它只认 `name` **不认 aliases**，且原生条目的名字常与底表县名不同写法：

  · 原生「平原」`type=郡治` 早已在册，底表也有「平原」——本该命中；
  · 原生「秣陵」别名里已有「建业」，底表另有「建业」县——两处都留了条目；
  · 原生「夷陵」与底表「夷陵」并存（seed 用今字，底表用汉写）。

结果 34 组「同行政区重名」，其中多数是**同一条目被登记了两次**：一条来自 seed、
一条来自补充脚本，坐标相差 0.01~0.15°。

本脚本的口径
------------
以 **id 精确**指定「删哪个 / 留哪个」，不做模糊合并——同名异地（高平、潞）必须
保留两条。合并时：

  · `seat_of` 从被删条目搬到保留条目（保留条目已有则不覆盖）；
  · `ancient_admin` 保留条目为空时用被删条目的补上；
  · 被删条目的 `name` 挂进保留条目的 `aliases`，检索键不丢；
  · 坐标、`mention_count`、`first_chapter` 一律以保留条目为准。

另外两处数据录入错一并修：
  · seed 里「下邳」古属写「徐州·下邳郡」——东汉是下邳国，底图郡面也叫「下邳国」，
    不改则「点位行政区划合法」项报「郡名不在该州郡表」；
  · 8 个非行政地名（彝陵、樊口、汉津…）`ancient_admin` 为空，古属只写在
    `build_place_hierarchy.py` 的 FILL 表里。这里把 FILL 落回字段，让数据与展示同源。

用法：
  python3 scripts/dedupe_places.py [--dry]
"""
import csv, io, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P_ADD = os.path.join(ROOT, 'data', 'places-additions.json')
P_SEED = os.path.join(ROOT, 'data', 'places-seed.csv')

# 被删补充条目 id → 保留条目 id（保留条目可在 seed 或 additions）
MERGE = {
    'c_扬州_九江郡_合肥': 'he_fei',
    'c_扬州_九江郡_寿春': 'shou_chun',
    'c_青州_平原郡_平原': 'ping_yuan',
    'c_荆州_南郡_当阳': 'dang_yang',
    'c_益州_蜀郡_成都': 'cheng_du',
    'c_荆州_南阳郡_新野': 'xin_ye',
    'c_并州_太原郡_晋阳': 'jin_yang',
    'c_幽州_辽西郡_柳城': 'liu_cheng',
    'c_扬州_豫章郡_柴桑': 'chai_sang',
    'c_益州_巴郡_江州': 'jiang_zhou',
    'c_荆州_南郡_江陵': 'jiang_ling',
    'c_兖州_东郡_濮阳': 'pu_yang',
    'c_兖州_东郡_白马': 'bai_ma',
    'c_益州_广汉郡_绵竹': 'mian_zhu',
    'c_幽州_辽东郡_襄平': 'xiang_ping',
    'c_豫州_沛国_谯': 'qiao_xian',
    'c_司隶_京兆尹_长安': 'chang_an',
    'c_司隶_右扶风_陈仓': 'chen_cang',
    'c_荆州_零陵郡_零陵': 'ling_ling',
    'c_徐州_下邳国_下邳': 'xia_pi',
    'c_益州_汉中郡_南郑': 'han_zhong',
}

# 「夷陵」这组不是重复，是**同一城的两种建置**：汉夷陵县属南郡，汉末吴分置宜都郡后
# 自南郡析出。seed 的 yi_ling 标「荆州·宜都郡」是汉末实况，底表 c_荆州_南郡_夷陵
# 是永和旧制，两条都该留。改行政区划（把底表那条挪进宜都郡）会掩盖沿革差异，
# 故给底表那条加别名「西陵」（吴改夷陵为西陵），并保留原名可检索。
# 同行政区重名的判定按「名字 + 行政区」两者同时相同才算，加别名后自然解除。
ALIAS_ADD = {
    'c_荆州_南郡_夷陵': ['西陵'],
}

FILL_ADM = {
    '彝陵': '荆州·南郡', '巴丘': '荆州·南郡', '油江口': '荆州·南郡',
    '陆口': '荆州·江夏郡', '樊口': '荆州·江夏郡', '三江口': '扬州·丹阳郡',
    '汉津': '荆州·南郡', '七星坛': '扬州·丹阳郡',
}

ADM_FIX = {'徐州·下邳郡': '徐州·下邳国'}

additions = json.load(io.open(P_ADD, encoding='utf-8'))
places = additions['places']
by_id = {p['id']: p for p in places}

# seed 行：保留目标若在 seed，别名要写回 CSV
seed_rows = list(csv.DictReader(io.open(P_SEED, encoding='utf-8-sig')))
seed_rows = [{(k.lstrip('\ufeff').strip()): v for k, v in r.items()} for r in seed_rows]
seed_by_id = {r['id']: r for r in seed_rows}
seed_alias_add = {}


def _split_al(s):
    return [a.strip() for a in (s or '').replace('；', ',').replace('、', ',').split(',')
            if a.strip() and a.strip() != '—']


dropped, merged, aliased, filled, fixed = [], 0, 0, 0, 0
for src, dst in MERGE.items():
    p = by_id.get(src)
    if p is None:
        continue
    tgt = by_id.get(dst)
    if tgt is not None:
        if p.get('seat_of') and not tgt.get('seat_of'):
            tgt['seat_of'] = p['seat_of']
            merged += 1
        if not tgt.get('ancient_admin') and p.get('ancient_admin'):
            tgt['ancient_admin'] = p['ancient_admin']
            merged += 1
        if p['name'] != tgt['name']:
            al = tgt.setdefault('aliases', [])
            if p['name'] not in al:
                al.append(p['name'])
                aliased += 1
    else:
        srow = seed_by_id.get(dst)
        if srow is None:
            print('  ! 保留目标不存在，跳过：%s → %s' % (src, dst))
            continue
        seed_alias_add.setdefault(dst, [])
        if p['name'] != srow['古名'].strip():
            seed_alias_add[dst].append(p['name'])
            aliased += 1
    dropped.append(src)

drop_set = set(dropped)
additions['places'] = [p for p in places if p['id'] not in drop_set]

for p in additions['places']:
    aa = p.get('ancient_admin') or ''
    if aa in ADM_FIX:
        p['ancient_admin'] = ADM_FIX[aa]
        fixed += 1
    if not aa and p['name'] in FILL_ADM:
        p['ancient_admin'] = FILL_ADM[p['name']]
        filled += 1
    for a in ALIAS_ADD.get(p['id'], ()):
        al = p.setdefault('aliases', [])
        if a not in al and a != p['name']:
            al.append(a)
            aliased += 1

# seed 古属订正 + 别名回写
seed_dirty = False
for r in seed_rows:
    if r['三国时州郡'].strip() in ADM_FIX:
        r['三国时州郡'] = ADM_FIX[r['三国时州郡'].strip()]
        seed_dirty = True
    extra = seed_alias_add.get(r['id'])
    if extra:
        al = _split_al(r['别名'])
        for n in extra:
            if n and n not in al and n != r['古名'].strip():
                al.append(n)
        r['别名'] = ','.join(al) if al else '—'
        seed_dirty = True

if seed_dirty and '--dry' not in sys.argv:
    cols = list(seed_rows[0].keys())
    with io.open(P_SEED, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in seed_rows:
            w.writerow(r)
    print('seed 已更新（%d 行）' % len(seed_rows))

print('并入删重 %d 条，搬字段 %d 处，补别名 %d 个，补古属 %d 条，订正古属 %d 处'
      % (len(dropped), merged, aliased, filled, fixed))
print('additions 现有 %d 条' % len(additions['places']))

if '--dry' not in sys.argv:
    json.dump(additions, io.open(P_ADD, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('已写回 %s' % os.path.relpath(P_ADD, ROOT))
