#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修正君臣边：把任期与「当时实际在位/掌权者」对齐。

由 audit_correctness 的「任期与主君无年份重叠」检查暴露，逐条按史实核准：

  刘禅  wei 263-266  lord 曹髦(254-260) → 曹奂(258-266)；降魏为安乐公，role 改「其他」
  邓艾  wei 240-250  lord 曹叡(226-239) → 曹芳(239-254)
  钟会  wei 263-264  lord 曹髦(254-260) → 司马昭(249-265)
  陆抗  wu  271-274  lord 孙休(258-264) → 孙皓(264-280)
  华歆  wu  195-199  lord 孙权(200-)    → 孙策(195-200)
  诸葛绪 wei 263-263 lord 曹髦(254-260) → 曹奂(258-266)
"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')

# (person_id, start_year) -> {lord_id, [role], basis}
FIX = {
    ('liu_shan', 263): {'lord_id': 'cao_huan', 'role': '其他',
                        'basis': '263 年蜀亡降魏，魏帝为曹奂；受封安乐公，非君主。'},
    ('deng_ai', 240): {'lord_id': 'cao_fang',
                       'basis': '240-250 年魏帝为曹芳（239-254），非曹叡（226-239）。'},
    ('zhong_hui', 263): {'lord_id': 'sim_zhao',
                         'basis': '263 年伐蜀由司马昭主政（魏帝曹奂，实权在司马氏）。'},
    ('lu_kang', 271): {'lord_id': 'sun_hao',
                       'basis': '271-274 年吴帝为孙皓（264-280），孙休已于 264 年卒。'},
    ('hua_xin', 195): {'lord_id': 'sun_ce',
                       'basis': '195-199 年江东为孙策所据（孙权 200 年才继位）。'},
    ('zhuge_xu', 263): {'lord_id': 'cao_huan',
                        'basis': '263 年魏帝为曹奂（258-266），曹髦已于 260 年被杀。'},
}


def main():
    apply = '--fix' in sys.argv
    hit = []
    for f in sorted(glob.glob(os.path.join(DATA, 'persons*.json'))):
        d = json.load(open(f, encoding='utf-8'))
        dirty = False
        for p in d.get('persons', []):
            for t in p.get('tenure', []) or []:
                rule = FIX.get((p['id'], t.get('start_year')))
                if not rule:
                    continue
                old = t.get('lord_id')
                t['lord_id'] = rule['lord_id']
                if 'role' in rule:
                    t['role'] = rule['role']
                t['basis'] = rule['basis']
                hit.append((p['name'], t.get('start_year'), old, rule['lord_id'],
                            rule.get('role', '-')))
                dirty = True
        if dirty and apply:
            json.dump(d, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print(f'修正君臣边 {len(hit)} 条' + ('' if apply else '（预演，加 --fix 写回）'))
    for nm, y, o, n, r in hit:
        print(f'  {nm} {y}: lord {o} -> {n}' + (f'，role -> {r}' if r != '-' else ''))


if __name__ == '__main__':
    main()
