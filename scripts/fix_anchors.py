#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
锚点修正器（任务②配套）

两件事，都以「正文实际命中」为准绳反推修正（而非凭印象改数据）：

  1. 人物单字 surface 的系统性误链：对每个人物的单字 surface 统计「言语后接率」
     （后接 曰/问/言/说/谓 的比例）。单称的语义本质是「对白主语」，正常该比例很高；
     低于阈值说明该字在书中多半是副词/动词/虚词（望/之/必/何/随/诗…），整条删除。
     手写 guard 保护的字（操/卓/植/儁…）不在清理范围。
  2. first_chapter 不实：以人物**全名**在正文的最早出现回目为准回填。
     原值来自自动建档时的推断（回目前已含 alias 优先等不同策略），遗漏早期提及并不罕见。

写回 data/lexicon-rules.json（drop 规则）与各 data/persons_*.json（first_chapter）。
"""
import json, io, os, re, glob
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
BUILD = os.path.join(ROOT, 'build')
SPEECH = set('曰问言说谓')
THRESHOLD = 0.40          # 言语后接率下限
MIN_COUNT = 3             # 样本太少不判定


def scan():
    nxt = defaultdict(Counter)
    tot = Counter()
    first_full = defaultdict(lambda: 999)
    for f in sorted(glob.glob(os.path.join(BUILD, 'chapters', 'ch*.json'))):
        d = json.load(io.open(f, encoding='utf-8'))
        ch = d['chapter']['no'] if isinstance(d['chapter'], dict) else d['chapter']
        texts = {p['id']: p['text'] for p in d['passages']}
        for m in d['mentions']:
            if m['entity_type'] != 'person':
                continue
            key = (m['surface'], m['entity_id'])
            tot[key] += 1
            t = texts.get(m['passage_id'], '')
            if m['end'] < len(t):
                nxt[key][t[m['end']]] += 1
            if len(m['surface']) >= 2 and ch < first_full[m['entity_id']]:
                first_full[m['entity_id']] = ch
    return nxt, tot, first_full


def main():
    nxt, tot, first_full = scan()
    persons = {}
    src_of = {}
    for f in glob.glob(os.path.join(DATA, 'persons_*.json')):
        for p in json.load(io.open(f, encoding='utf-8'))['persons']:
            persons[p['id']] = p
            src_of[p['id']] = f

    rules = json.load(io.open(os.path.join(DATA, 'lexicon-rules.json'), encoding='utf-8'))
    guarded = {(r['type'], r['id'], r['surface']) for r in rules['rules'] if r['op'] == 'guard'}
    dropped = {(r.get('type'), r.get('id'), r.get('surface'))
               for r in rules['rules'] if r['op'] == 'drop'}

    # ---- 1. 单字误链 ----
    bad = []
    for (surf, pid), c in tot.items():
        if len(surf) != 1 or c < MIN_COUNT:
            continue
        if ('person', pid, surf) in guarded or ('person', pid, surf) in dropped:
            continue
        sr = sum(v for k, v in nxt[(surf, pid)].items() if k in SPEECH) / c
        if sr < THRESHOLD:
            bad.append((pid, persons.get(pid, {}).get('name', pid), surf, c, sr,
                        ''.join(k for k, _ in nxt[(surf, pid)].most_common(5))))
    bad.sort(key=lambda x: -x[3])
    print(f'[1] 言语后接率<{THRESHOLD:.0%} 的人物单字 surface：{len(bad)} 条')
    for b in bad:
        print(f'    {b[1]}({b[0]}) 单字「{b[2]}」{b[3]}次 言语率{b[4]:.0%} 后接:{b[5]}')
    n1 = 0
    for pid, nm, surf, c, sr, top in bad:
        rules['rules'].append({
            'op': 'drop', 'surface': surf, 'type': 'person', 'id': pid,
            'evidence': f'单称「{surf}」言语后接率仅 {sr:.0%}（对比 操43%/肃51%/维42%），'
                        f'实测 {c} 处多为副词/虚词用法（后接 "{top}"）。2026-10-30 全量复测删除。'})
        n1 += 1

    # ---- 2. first_chapter 回填 ----
    fixed = []
    for pid, ch in first_full.items():
        p = persons.get(pid)
        if not p or ch == 999:
            continue
        cur = p.get('first_chapter')
        if cur is None or ch < cur:
            fixed.append((pid, p['name'], cur, ch, src_of[pid]))
    print(f'\n[2] first_chapter 需回填（全名实际最早回目更早）：{len(fixed)} 人')
    by_file = defaultdict(dict)
    for pid, nm, cur, ch, src in fixed:
        print(f'    {nm}: {cur} → 第{ch}回')
        by_file[src][pid] = ch
    n2 = 0
    for src, mapping in by_file.items():
        doc = json.load(io.open(src, encoding='utf-8'))
        hit = 0
        for p in doc['persons']:
            if p['id'] in mapping:
                p['first_chapter'] = mapping[p['id']]
                p.setdefault('date_note', '')
                hit += 1
        if hit:
            json.dump(doc, io.open(src, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            n2 += hit
    json.dump(rules, io.open(os.path.join(DATA, 'lexicon-rules.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'\n新增 drop {n1} 条；回填 first_chapter {n2} 人；rules 总数 {len(rules["rules"])}')


if __name__ == '__main__':
    main()
