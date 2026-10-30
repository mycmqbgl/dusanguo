# -*- coding: utf-8 -*-
"""把 data_faction_fix.py 的判定表应用到 persons_*.json。

用法：
  python3 scripts/fix_fallback_factions.py          # 干跑，打印差异
  python3 scripts/fix_fallback_factions.py --fix     # 实写
"""
import glob
import json
import sys

sys.path.insert(0, 'scripts')
from data_faction_fix import FIX  # noqa: E402

ROLE_ORDER = ['皇帝', '追谥', '君主', '权臣', '亲族', '文臣', '武将', '女眷', '其他']
# 阵营 × 身份 允许矩阵
ALLOW = {
    'han': {'皇帝', '追谥', '权臣', '亲族', '文臣', '武将', '女眷', '其他'},
    'wei': {'皇帝', '追谥', '权臣', '亲族', '文臣', '武将', '女眷', '其他'},
    'shu': {'皇帝', '追谥', '权臣', '亲族', '文臣', '武将', '女眷', '其他'},
    'wu': {'皇帝', '追谥', '权臣', '亲族', '文臣', '武将', '女眷', '其他'},
    'jin': {'皇帝', '追谥', '权臣', '亲族', '文臣', '武将', '女眷', '其他'},
    'warlord': {'君主', '文臣', '武将', '其他'},
    'barbarian': {'君主', '文臣', '武将', '其他'},
    'mystic': {'其他'},
}

FIX_MODE = '--fix' in sys.argv

stats = {'hit': 0, 'miss': 0, 'fac': 0, 'role': 0, 'title': 0}
missing = []
changed = []

for f in sorted(glob.glob('data/persons_*.json')):
    doc = json.load(open(f))
    dirty = False
    for p in doc['persons']:
        ten = p.get('tenure') or []
        if not ten:
            continue
        basis_all = ' '.join(str(t.get('basis', '')) for t in ten)
        if 'fallback' not in basis_all:
            continue
        rule = FIX.get(p['name'])
        if not rule:
            stats['miss'] += 1
            missing.append((p['name'], p['id']))
            continue
        stats['hit'] += 1
        fac, role, title, basis, verified = rule
        if role not in ALLOW[fac]:
            raise SystemExit(f'规则非法：{p["name"]} {fac}/{role} 不在允许矩阵内')
        # fallback 卡均为单任期
        t = ten[0]
        if t.get('faction_id') != fac:
            stats['fac'] += 1
        if t.get('role') != role:
            stats['role'] += 1
        if (t.get('title') or None) != title:
            stats['title'] += 1
        changed.append((p['name'], t.get('faction_id'), fac, t.get('role'), role,
                        t.get('title'), title))
        t['faction_id'] = fac
        t['role'] = role
        if title is None:
            t.pop('title', None)
        else:
            t['title'] = title
        t['basis'] = basis
        t['confidence'] = 0.75 if verified else 0.4
        t['review_status'] = 'reviewed' if verified else 'auto'
        # 去掉旧的「原文首见…自动建档」残句
        dirty = True
    if dirty and FIX_MODE:
        json.dump(doc, open(f, 'w'), ensure_ascii=False, indent=1)

print('命中 %d / 未覆盖 %d' % (stats['hit'], stats['miss']))
print('阵营改 %d，身份改 %d，官职改 %d' % (stats['fac'], stats['role'], stats['title']))
if missing:
    print('未覆盖：', missing)
if not FIX_MODE:
    for row in changed[:15]:
        print(row)
    print('... 共 %d 条' % len(changed))
else:
    print('已写入')
