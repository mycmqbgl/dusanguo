#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""清理人物 bio 里的内部机器标记（保守版）。

只删除精确的模板片段，不做贪婪跨句删除：
  1. 「（据原文第N回前后文及人物名录整理；此卡为自动建档，生卒、字号、详细事迹待考。）」
     整段括号模板 → 换成一句正常说明
  2. 「faction_roster:xx/yy；」「fallback；」
  3. 「原文首见第N回，全书出现N次。」「自动建档，生卒/字号未考。」
  4. 「，任隐士/名士/使者」→ 去掉「任」
"""
import json, glob, re, sys

ROOT = '/workspace/读三国-project'

# 1) 整段括号模板
TPL_PAREN = re.compile(
    r'（据原文第\s*\d+\s*回前后文及人物名录整理[；;][^）]*?）')
TPL_PAREN_ALT = re.compile(
    r'[（(]?据原文第\s*\d+\s*回前后文及人物名录整理[；;]?此卡为[^。）]*[）)]?')

MACHINE = [
    re.compile(r'faction_roster:[^；。]*[；。]'),
    re.compile(r'fallback[；。]?'),
    re.compile(r'原文首见第\s*\d+\s*回[，,]\s*全书出现\s*\d+\s*次[。；]?'),
    re.compile(r'自动建档[，,]\s*生卒/字号未考[。；]?'),
    re.compile(r'此卡为自动建档[，,]?\s*生卒[、，]?\s*字号[、，]?\s*详细事迹待考[。]?'),
    re.compile(r'此卡为$'),
    re.compile(r'；此卡为(?=[。）]|$)'),
]

NON_OFFICE = re.compile(r'，任(隐士|名士|术士|使者|亲信)([。，])')
SOLDIER = re.compile(r'，任(魏兵（[^）]*）)')


def clean(b):
    if not b:
        return b
    b = TPL_PAREN.sub('（据原文及人物名录整理，此卡为自动建档，事迹俟考。）', b)
    b = TPL_PAREN_ALT.sub('（据原文及人物名录整理，事迹俟考。）', b)
    for pat in MACHINE:
        b = pat.sub('', b)
    b = SOLDIER.sub(r'，为\1', b)
    b = NON_OFFICE.sub(r'，\1\2', b)
    b = re.sub(r'[；，]{2,}', '；', b)
    b = re.sub(r'。{2,}', '。', b)
    b = re.sub(r'^[；，。\s]+', '', b).strip()
    return b


def main(apply=False):
    n = 0
    samples = []
    for f in sorted(glob.glob(f'{ROOT}/data/persons*.json')):
        d = json.load(open(f, encoding='utf-8'))
        dirty = False
        for p in d.get('persons', []):
            old = p.get('bio') or ''
            new = clean(old)
            if new != old:
                samples.append((p['name'], new))
                p['bio'] = new
                dirty = True
                n += 1
        if dirty and apply:
            json.dump(d, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'{"已清理" if apply else "预演"}：{n} 张')
    for nm, b in samples[:8]:
        print(f'  {nm:6s} {b[:110]}')
    # 残留检查
    left = 0
    for f in glob.glob(f'{ROOT}/data/persons*.json'):
        d = json.load(open(f, encoding='utf-8'))
        for p in d.get('persons', []):
            b = p.get('bio') or ''
            if re.search(r'faction_roster:|fallback|全书出现|此卡为$|此卡为[。）]', b):
                left += 1
    print('残留机器标记:', left)


if __name__ == '__main__':
    main('--fix' in sys.argv)
