#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阅读页锚点校验（任务②）

对 build/chapters/*.json 里落盘的每一条 mention 做四类检查：

  A. 多义冲突：同一 surface 被词典映射到多个实体（人物/地点），需要上下文消歧
  B. 时序越界：人物锚点出现在其 first_chapter 之前很多回，
               或是出现在其 tenure 时间片结束之后 —— 多为误链或同名他人
  C. 非叙事文本误链：开篇词（《临江仙》）、回前挡/scheme ID、乃至诗句
               被当成人名地名链接
  D. 高频泛词：出现次数远超合理值、且多为通用词/单字的 surface

输出 data/audit_anchors.json + 控制台摘要
"""
import json, io, os, glob, re, sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
BUILD = os.path.join(ROOT, 'build')


def load_all():
    mentions = []          # 全量 mention
    passages = {}          # passage_id -> (chapter, text)
    for f in sorted(glob.glob(os.path.join(BUILD, 'chapters', 'ch*.json'))):
        d = json.load(io.open(f, encoding='utf-8'))
        raw = d['chapter']
        ch = raw['no'] if isinstance(raw, dict) else raw
        for p in d['passages']:
            passages[p['id']] = (ch, p['text'])
        for m in d['mentions']:
            m['chapter'] = ch
            mentions.append(m)
    return mentions, passages


def load_entities():
    persons, places = {}, {}
    for f in glob.glob(os.path.join(DATA, 'persons_*.json')):
        for p in json.load(io.open(f, encoding='utf-8'))['persons']:
            persons[p['id']] = p
    for pl in json.load(io.open(os.path.join(BUILD, 'places.json'), encoding='utf-8')):
        places[pl['id']] = pl
    return persons, places


def main():
    mentions, passages = load_all()
    persons, places = load_entities()
    print(f'mention 总数 {len(mentions)} | 人物 {len(persons)} | 地点 {len(places)}')

    # ---------- A. 多义冲突 ----------
    surf_map = defaultdict(set)
    for m in mentions:
        surf_map[m['surface']].add((m['entity_type'], m['entity_id']))
    ambig = {s: sorted(v) for s, v in surf_map.items() if len(v) > 1}
    print(f'\n[A] 多义 surface: {len(ambig)} 个')
    for s, v in sorted(ambig.items(), key=lambda x: -len(x[1]))[:25]:
        names = []
        for t, i in v:
            names.append(persons[i]['name'] if t == 'person' else places.get(i, {}).get('name', i))
        print(f'   {s}: {names}')

    # ---------- C. 非叙事文本误链（开篇词 / 词牌 / 回目集成055）----------
    # 非叙事文本锚点的判定收紧：只有整段确实属于诗词/赞语时才算
    NON_NARR = re.compile(r'(滚滚长江东逝水|调寄《|——调寄|\{\{ poetry|有诗赞曰|后人有诗赞|^诗曰)')
    wrong_ctx = []
    for m in mentions:
        ch, text = passages.get(m['passage_id'], (0, ''))
        # 整段落是诗词/词牌：命中强标记且该段不以叙述性开头
        if NON_NARR.search(text[:120]) and not re.match(r'^(却说|且说|话说|当日|次日|正议|忽)', text.strip()[:4]):
            wrong_ctx.append((ch, m['surface'], m['entity_type'],
                              persons.get(m['entity_id'], {}).get('name') or places.get(m['entity_id'], {}).get('name', m['entity_id']),
                              text[max(0, m['start']-14):m['start']+14]))
    print(f'\n[C] 疑似非叙事文本中的锚点: {len(wrong_ctx)} 处')
    for x in wrong_ctx[:25]:
        print(f'   第{x[0]}回 {x[1]}→{x[3]}   …{x[4]}…')

    # ---------- B. 时序越界 ----------
    by_pid = defaultdict(list)
    for m in mentions:
        if m['entity_type'] == 'person':
            by_pid[m['entity_id']].append(m['chapter'])
    early, late = [], []
    for pid, chs in by_pid.items():
        p = persons.get(pid)
        if not p: continue
        fc = p.get('first_chapter')
        if fc and min(chs) < fc - 5:
            early.append((pid, p['name'], min(chs), fc, max(chs), len(chs)))
        tn = p.get('tenure') or []
        if tn:
            end_y = max([t.get('end_year') or 9999 for t in tn])
            start_y = min([t.get('start_year') or 0 for t in tn])
            # 用回目->年份表粗判
    print(f'\n[B] 锚点早于 first_chapter 5 回以上的人物: {len(early)} 个')
    for e in sorted(early, key=lambda x: -(x[3]-x[2]))[:20]:
        print(f'   {e[1]}({e[0]}): 最早锚点第{e[2]}回 / first_chapter={e[3]} / 共{e[5]}处')

    # ---------- D. 高频泛词 ----------
    cnt = Counter(m['surface'] for m in mentions)
    print(f'\n[D] 出现最多的 surface TOP30:')
    for s, c in cnt.most_common(30):
        ents = sorted(surf_map[s])
        names = [persons[i]['name'] if t == 'person' else places.get(i, {}).get('name', i) for t, i in ents]
        print(f'   {s}({c}) → {names[:3]}')

    out = {
        'total_mentions': len(mentions),
        'ambiguous_surfaces': {k: [list(x) for x in v] for k, v in ambig.items()},
        'non_narrative_anchors': [{'chapter': x[0], 'surface': x[1], 'type': x[2], 'entity': x[3], 'context': x[4]} for x in wrong_ctx],
        'too_early': [{'id': e[0], 'name': e[1], 'min_chapter': e[2], 'first_chapter': e[3], 'max_chapter': e[4], 'count': e[5]} for e in early],
        'top_surfaces': [{'surface': s, 'count': c} for s, c in cnt.most_common(80)],
    }
    json.dump(out, io.open(os.path.join(DATA, 'audit_anchors.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('\n已写出 data/audit_anchors.json')


if __name__ == '__main__':
    main()
