#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按原文铁证修正自动建档卡的阵营。

只采信「紧邻人名前的阵营前缀」这一种结构，例如：
  蜀将张翼 / 吴将朱然 / 魏将潘遂 / 晋将张尚
并且要求同一前缀在全书中出现 ≥2 次，避免单次误匹配。
同时把「首见回目只在错误语境外出现」的卡纠正过来源。

无证据者不改，保持原状并统计出来供人工复核。
"""
import json, glob, re, sys, collections

ROOT = '/workspace/读三国-project'
sys.path.insert(0, f'{ROOT}/scripts')
from extract_from_text import load_text

FAC_PREFIX = {
    '蜀': 'shu', '汉': 'shu',
    '吴': 'wu',
    '魏': 'wei',
    '晋': 'jin',
}
# 敌方视角要排除的说法：「破蜀将X」「斩吴将X」等，X 其实是我方
ENEMY_CTX = re.compile(r'(破|斩|擒|杀|刺|射|退|拒|败|攻|围|追|截)[\u4e00-\u9fa5]{0,3}$')

ROLE_HINT = [
    ('将', '武将'), ('大将', '武将'), ('牙将', '武将'), ('部将', '武将'),
    ('太守', '文臣'), ('刺史', '文臣'), ('长史', '文臣'), ('司马', '文臣'),
    ('从事', '文臣'), ('主簿', '文臣'), ('参军', '文臣'), ('丞', '文臣'),
    ('中郎将', '武将'), ('校尉', '武将'), ('都督', '武将'),
]


def main(apply=False):
    paras = load_text()
    # 统计「X将 + 人名」的铁证
    ev = collections.defaultdict(lambda: collections.Counter())   # name -> Counter(fac)
    ev_ctx = {}
    for no, t in paras:
        for m in re.finditer(r'(蜀|汉|吴|魏|晋)将([\u4e00-\u9fa5]{2,4})', t):
            fac_cn, name = m.group(1), m.group(2)
            # 只收「X将+人名」且紧接人名，不跨标点
            if len(name) < 2:
                continue
            ev[name][FAC_PREFIX[fac_cn]] += 1
            ev_ctx.setdefault(name, (no, t[max(0, m.start() - 8):m.end() + 8]))

    P = {}
    files = {}
    for f in sorted(glob.glob(f'{ROOT}/data/persons*.json')):
        d = json.load(open(f, encoding='utf-8'))
        files[f] = d
        for p in d.get('persons', []):
            P.setdefault(p['id'], p)

    rows = [p for p in P.values() if (p.get('summary') or '').startswith('（原文')]
    changed, skipped = [], []
    for p in rows:
        nm = p['name']
        c = ev.get(nm)
        if not c:
            skipped.append((nm, '无「X将+名」铁证'))
            continue
        top, n = c.most_common(1)[0]
        if n < 2:
            skipped.append((nm, f'证据仅 1 次：{top}'))
            continue
        if len(c) > 1 and c.most_common(2)[1][1] == n:
            skipped.append((nm, f'阵营歧义：{dict(c)}'))
            continue
        no, ctx = ev_ctx[nm]
        for t in (p.get('tenure') or []):
            if t.get('faction_id') == top:
                break
        else:
            for t in (p.get('tenure') or []):
                old = t.get('faction_id')
                t['faction_id'] = top
                t['basis'] = f'原文第 {no} 回「{ctx.strip()}」——原文以「{ {"shu":"蜀","wu":"吴","wei":"魏","jin":"晋"}[top] }将」称之。'
                t['confidence'] = 0.7
                t['review_status'] = 'auto_mined'
                changed.append((nm, old, top, f'{no}回 {ctx.strip()[:26]}'))
                break

    print(f'{"已改" if apply else "预演"}：{len(changed)} 人（证据驱动）')
    for nm, old, new, ctx in changed:
        print(f'  {nm:6s} {old}→{new} | {ctx}')
    print(f'未改 {len(skipped)} 人（无充分证据）')

    if apply:
        for f, d in files.items():
            json.dump(d, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main('--fix' in sys.argv)
