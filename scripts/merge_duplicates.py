#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重复人物卡合并（任务⑤配套）

同一人物因版本异写被建了两张卡（演义作「傅彤」/史书作「傅肜」、张郃/张合、
汉少帝/刘辩、糜竺/麋竺…）。两张并存会让读者看到重复卡片、且锚点互相打架。

策略：
  - 保留信息更完整的那张（优先级 verified > reviewed > auto_mined；
    同档优先正文实际用的写法，即 hug OleUntrusted 更短的 id）
  - 另一张的 name / match_surfaces / display_aliases 并入保留卡
  - 删除被合并卡，并把全库对该 id 的引用（events.participants.person_id、
    tenure.lord_id、power/relations）改指保留卡
"""
import json, io, os, glob, re, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')

RANK = {'verified': 3, 'reviewed': 2, 'auto_mined': 1}


def load():
    docs = {}
    persons = {}
    for f in sorted(glob.glob(os.path.join(DATA, 'persons_*.json'))):
        docs[f] = json.load(io.open(f, encoding='utf-8'))
        for p in docs[f]['persons']:
            persons[p['id']] = (f, p)
    return docs, persons


def find_groups(persons):
    """找出异写重复：两卡的 match_surfaces 有 >=2 字交集，且视为同一人"""
    owner = defaultdict(set)
    for pid, (f, p) in persons.items():
        for s in set(p.get('match_surfaces') or []) | {p['name']}:
            if len(s) >= 2:
                owner[s].add(pid)
    # 只合并「互相共享至少一个 >=2 字 surface」的二人组
    dup = defaultdict(set)
    for s, ids in owner.items():
        if len(ids) == 2:
            a, b = sorted(ids)
            dup[(a, b)].add(s)
    return dup


def build_freq():
    SRC = {}
    for f in sorted(glob.glob(os.path.join(DATA, 'source', 'ch*.txt'))):
        SRC[int(re.search(r'ch(\d+)', f).group(1))] = io.open(f, encoding='utf-8').read()
    return ''.join(SRC.values())


FULL = build_freq()


def keep_of(persons, ids):
    """保留依据（按重要性递减）：
       1. 原文实际写法 —— 出现次数高者优先（这才保证读者点到的就是常见写法）
       2. review_status 等级 verified > reviewed > auto_mined
       3. 生平信息完整度
    """
    best = None
    for pid in ids:
        f, p = persons[pid]
        nm = p['name']
        key = (FULL.count(nm), RANK.get(p.get('review_status'), 0),
               len(p.get('bio') or ''), int(bool(p.get('timeline'))))
        if best is None or key > best[0]:
            best = (key, pid)
    return best[1]


def main(apply=False):
    docs, persons = load()
    groups = find_groups(persons)
    plan = []
    for (a, b), shared in sorted(groups.items()):
        keep = keep_of(persons, (a, b))
        drop = b if keep == a else a
        plan.append((keep, persons[keep][1]['name'], drop, persons[drop][1]['name'], sorted(shared)))
    print(f'待合并 {len(plan)} 组：')
    for k, kn, d, dn, sh in plan:
        print(f'   {dn}({d}) 并入 → {kn}({k})   共享写法: {sh}')

    if not apply:
        print('\n（dry-run，加 --apply 落盘）')
        return

    # 反向映射：被删 id -> 保留 id
    remap = {}
    for keep, kn, drop, dn, sh in plan:
        remap[drop] = keep
        fk, pk = persons[keep]
        fd, pd = persons[drop]
        aliases = set(pk.get('display_aliases') or [])
        aliases |= set(pd.get('display_aliases') or [])
        aliases.add(pd['name'])
        pk['display_aliases'] = sorted(aliases - {pk['name']})
        # 合并锚点写法（去重）
        ms = list(dict.fromkeys(list(pk.get('match_surfaces') or []) +
                                list(pd.get('match_surfaces') or []) + [pd['name']]))
        pk['match_surfaces'] = sorted(set(ms), key=ms.index)
        # summary / bio 取更长者，并注明异写
        if len(pd.get('bio') or '') > len(pk.get('bio') or ''):
            pk['bio'] = pd['bio']
        pk.setdefault('date_note', '')
        pk['notice'] = (pk.get('notice', '') + f'；异写：{pd["name"]}').lstrip('；')

    # 落盘：删除卡 + 更新页面内引用
    for f, doc in docs.items():
        orig = len(doc['persons'])
        doc['persons'] = [p for p in doc['persons'] if p['id'] not in remap]
        for p in doc['persons']:
            for tn in (p.get('tenure') or []):
                if tn.get('lord_id') in remap:
                    tn['lord_id'] = remap[tn['lord_id']]
            for r in (p.get('relations') or []):
                if isinstance(r, dict) and r.get('person_id') in remap:
                    r['person_id'] = remap[r['person_id']]
                if isinstance(r, dict) and isinstance(r.get('with'), list):
                    r['with'] = [remap.get(x, x) for x in r['with']]
        if len(doc['persons']) != orig:
            json.dump(doc, io.open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    # 事件文件里的 participants.person_id
    n = 0
    for f in glob.glob(os.path.join(DATA, 'event_*.json')):
        doc = json.load(io.open(f, encoding='utf-8'))
        evs = doc.get('events') or (doc if isinstance(doc, list) else [])
        hit = 0
        for ev in evs:
            if not isinstance(ev, dict):
                continue
            for pt in (ev.get('participants') or []):
                if isinstance(pt, dict) and pt.get('person_id') in remap:
                    pt['person_id'] = remap[pt['person_id']]; hit += 1
        if hit:
            json.dump(doc, io.open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            n += hit
    print(f'\n已合并 {len(plan)} 组，删除重复卡 {len(remap)} 张；事件参与者 id 改写 {n} 处')


if __name__ == '__main__':
    main(apply='--apply' in sys.argv)
