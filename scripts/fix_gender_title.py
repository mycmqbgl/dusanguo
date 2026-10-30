#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修正自动建档卡的 gender 错标与 tenure.title 残留粘连。

gender 判据（按优先级）：
  1. 名字带女性标记（氏/夫人/后/妃/娘/姬/女王/女）→ female
  2. summary 开头 12 字内出现本人身份词（XX之女/之妻/之母/之妹/皇后/太后）→ female
  3. 出现男性身份词（XX父/XX子/XX兄/XX弟）→ male
  4. 其余按 role：女眷 → female，其他 → male

role 修正：确认为女性（判据 1/2 命中）却挂武将/文臣/君主/权臣 → 归「女眷」。

tenure.title：切断「<他人名>：<章回>回」式的跨条目粘连，删除孤立「字，」。
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')

GLUE = re.compile(r'[，,、]?\s*([\u4e00-\u9fa5]{2,4}?)：\s*([一二三四五六七八九十百千零\d]+回)')
BARE_ZI = re.compile(r'(?:^|[，,、；;])\s*字\s*[，,：:]\s*')

FEMALE_NAME = re.compile(r'(氏|夫人|太后|皇后|妃|娘|姬|女王|女)$')
FEMALE_SELF = re.compile(r'[\u4e00-\u9fa5]{2,4}之?(女|妻|母|妹|姊|姑)[，,、；;]|^(皇后|太后|夫人|嫔)')
MALE_SELF = re.compile(r'([\u4e00-\u9fa5]{2,4})(之父|之子|之兄|之弟|之侄|之舅)')
FEMALE_ROLES = {'女眷'}


def clean_title(t):
    if not t:
        return t, False
    o = t
    m = GLUE.search(t)
    if m and len(t[:m.start()].rstrip('，,、；; ')) >= 2:
        t = t[:m.start()].rstrip('，,、；; ')
    t = BARE_ZI.sub(lambda mm: mm.group(0)[0] if mm.group(0)[0] in '，,、；;' else '', t)
    t = re.sub(r'^[，,、；;]\s*', '', t)
    t = re.sub(r'[，,、；;]{2,}', '，', t).strip('，,、；; \t')
    return t, t != o


def decide_gender(p):
    nm = p.get('name') or ''
    s = (p.get('summary') or '')[:12]
    full = ' '.join(filter(None, [p.get('summary'), p.get('bio')]))
    if FEMALE_NAME.search(nm):
        return 'female', 'name'
    if FEMALE_SELF.search(s):
        return 'female', 'self'
    if MALE_SELF.search(full[:20]):
        return 'male', 'self'
    roles = {t.get('role') for t in (p.get('tenure') or [])}
    return ('female', 'role') if roles == FEMALE_ROLES else ('male', 'role')


def main():
    apply = '--fix' in sys.argv
    g_chg, t_chg, r_chg = [], [], []
    for f in sorted(glob.glob(os.path.join(DATA, 'persons*.json'))):
        d = json.load(open(f, encoding='utf-8'))
        dirty = False
        for p in d.get('persons', []):
            if p.get('review_status') != 'auto_mined':
                continue
            # --- tenure.title 清洗
            for t in p.get('tenure', []) or []:
                nt, ch = clean_title(t.get('title') or '')
                if ch:
                    t['title'] = nt
                    t_chg.append((p['name'], nt))
                    dirty = True
            # --- gender
            g, why = decide_gender(p)
            if g != p.get('gender'):
                g_chg.append((p['name'], p.get('gender'), g, why,
                              (p.get('summary') or '')[:16]))
                p['gender'] = g
                dirty = True
            # --- role：确认女性却挂非女眷身份
            if g == 'female' and why in ('name', 'self'):
                for t in p.get('tenure', []) or []:
                    if t.get('role') in ('武将', '文臣', '君主', '权臣', '亲族'):
                        r_chg.append((p['name'], t.get('role'), '女眷'))
                        t['role'] = '女眷'
                        dirty = True
        if dirty and apply:
            json.dump(d, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print(f'tenure.title 清洗 {len(t_chg)} 条' + ('' if apply else '（预演）'))
    for a, b in t_chg[:6]:
        print(f'  {a} -> {b}')
    print(f'gender 修正 {len(g_chg)} 条')
    for nm, o, n, why, s in g_chg:
        print(f'  {nm}: {o} -> {n} [{why}] {s}')
    print(f'role 归位 {len(r_chg)} 条')
    for a, o, n in r_chg:
        print(f'  {a}: {o} -> {n}')


if __name__ == '__main__':
    main()
