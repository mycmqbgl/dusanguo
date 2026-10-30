#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
锚点审计：从 456 个锚点里捞出「可能链错了」的那些，输出上下文供人工过目。

审计不追求自动判定对错——那是不可能的。它做的是把「需要人看一眼」的锚点按风险从高到低
排好，让每条误报的复核成本从「通读全文」降到「看一行」。

四类风险：
  A 单字锚点      一个字既是人名又是常用词，误链代价最高
  B 地名接爵称    地名后面紧跟「王/侯/将军」→ 多半是爵位官职，不是地点
  C 人物接地名    人物后面紧跟「县/郡/城」→ 多半是地名，不是人物
  D 歧义表面形式  同一字面指向两个以上实体，必有一处错
  E 未登录候选    看起来像人名却没建档（供 discover_entities 二次确认）

用法：
  python scripts/audit_mentions.py              # 全量报告
  python scripts/audit_mentions.py --check A    # 只看某一类
"""
import json, io, os, sys, re, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, 'build')

TITLE_SUFFIX = ['王', '侯', '公', '将军', '相', '牧', '守', '尉', '校尉', '刺史', '太守', '尹', '令', '长', '君']
PLACE_SUFFIX = ['县', '郡', '州', '城', '关', '山', '乡', '亭', '邑', '渡', '津', '宫', '殿', '门']
# 官职代称：按决策 #2 只做悬浮提示，不弹卡；若被当地名/人名链上即为误报
OFFICE_WORDS = ['尚书', '司徒', '太尉', '司空', '大将军', '车骑将军', '骠骑将军', '卫将军',
                '中郎将', '校尉', '刺史', '太守', '从事', '主簿', '别驾', '司马', '长史']


def load():
    chs = {}
    for f in sorted(os.listdir(os.path.join(BUILD, 'chapters'))):
        if not f.endswith('.json'):
            continue
        d = json.load(io.open(os.path.join(BUILD, 'chapters', f), encoding='utf-8'))
        chs[d['chapter']['no']] = d
    persons = {}
    pdir = os.path.join(BUILD, 'persons')
    for f in sorted(os.listdir(pdir)):
        if f.endswith('.json'):
            p = json.load(io.open(os.path.join(pdir, f), encoding='utf-8'))
            persons[p['id']] = p
    places = {p['id']: p for p in json.load(io.open(os.path.join(BUILD, 'places.json'), encoding='utf-8'))}
    return chs, persons, places


def ctx(text, s, e, pad=11):
    return text[max(0, s - pad):s] + '【' + text[s:e] + '】' + text[e:e + pad]


def collect(chs):
    out = []
    for no, d in chs.items():
        pmap = {p['id']: p['text'] for p in d['passages']}
        for m in d['mentions']:
            t = pmap[m['passage_id']]
            m2 = dict(m)
            m2['ch'] = no
            m2['ctx'] = ctx(t, m['start'], m['end'])
            m2['next'] = t[m['end']:m['end'] + 6]
            m2['prev'] = t[max(0, m['start'] - 4):m['start']]
            out.append(m2)
    return out


def name_of(m, persons, places):
    if m['entity_type'] == 'person':
        return (persons.get(m['entity_id']) or {}).get('name', m['entity_id'])
    return (places.get(m['entity_id']) or {}).get('name', m['entity_id'])


def audit(chs, persons, places):
    ms = collect(chs)
    res = {}

    # A 单字锚点
    # 按 (字面, 实体) 分组，不能只按字面：同一个「嵩」可能既指曹嵩又指皇甫嵩，
    # 合并成一组后只能标一个人的名字，质检时会把「最近全称回指」的正确结果看成错的。
    a = [m for m in ms if len(m['surface']) == 1]
    groups = {}
    for m in a:
        groups.setdefault((m['surface'], m['entity_id']), []).append(m)
    res['A'] = {('%s→%s' % (s, name_of(v[0], persons, places)), s): v
                for (s, _eid), v in sorted(groups.items(), key=lambda kv: -len(kv[1]))}

    # B 地名 + 爵称/官职
    b = []
    for m in ms:
        if m['entity_type'] != 'place':
            continue
        tail = m['next']
        for suf in TITLE_SUFFIX:
            if tail.startswith(suf):
                # 「洛阳宫」「长安城」这类不算——只有爵位/官职称谓才可疑
                if suf in ('王', '侯', '公', '将军', '相', '牧', '守', '尉', '校尉', '刺史', '太守', '尹', '令', '长', '君'):
                    b.append((m['ch'], m['ctx'], '%s → %s' % (m['surface'], name_of(m, persons, places))))
                    break
    res['B'] = b

    # C 人物 + 地名后缀
    c = []
    for m in ms:
        if m['entity_type'] != 'person':
            continue
        for suf in PLACE_SUFFIX:
            if m['next'].startswith(suf):
                c.append((m['ch'], m['ctx'], '%s → %s' % (m['surface'], name_of(m, persons, places))))
                break
    res['C'] = c

    # D 歧义表面形式
    # 必须区分两类，否则「受控歧义」会被当成 bug：
    #   受控 —— 每一处都有同段全称回指定人（source=anaphora 且带 anaphora_basis），
    #           如第 1 回的「嵩」分别由「曹嵩」「皇甫嵩」定住，两处都对；
    #   未受控 —— 有锚点没有任何判据，纯靠字面命中，这才需要人看。
    surf = {}
    for m in ms:
        surf.setdefault(m['surface'], set()).add((m['entity_type'], m['entity_id']))
    d = {}
    for s, ents in surf.items():
        if len(ents) <= 1:
            continue
        rows = [m for m in ms if m['surface'] == s]
        ungoverned = [m for m in rows if not m.get('anaphora_basis')]
        d[s] = {'governed': not ungoverned,
                'rows': [{'ch': m['ch'], 'ctx': m['ctx'],
                          'to': '%s/%s' % (m['entity_type'], m['entity_id']),
                          'basis': m.get('anaphora_basis', '')} for m in rows]}
    res['D'] = d

    # E 地名被更长地名包含（如「江夏」出现在「江夏平」无碍，但「荆州」被「荆州刺史」当官称）
    e = []
    for m in ms:
        if m['entity_type'] != 'place':
            continue
        for w in OFFICE_WORDS:
            if m['next'].startswith(w) or m['prev'].endswith(w):
                e.append((m['ch'], m['ctx'], name_of(m, persons, places)))
                break
    res['E'] = e
    return res, ms


def report(res, ms):
    L = []
    L.append('# 锚点审计报告\n')
    L.append('共 %d 个锚点。下表按风险类别排列，风险不等于错误，需逐条过目后决定是否加规则。\n' % len(ms))

    L.append('\n## A 单字锚点（%d 处 / %d 组）\n' % (sum(len(v) for v in res['A'].values()), len(res['A'])))
    for (label, _s), rows in res['A'].items():
        L.append('\n### 「%s」× %d\n' % (label, len(rows)))
        for m in rows[:6]:
            L.append('- 第%d回　%s\n' % (m['ch'], m['ctx']))

    L.append('\n## B 地名接爵称/官职（%d 处）\n' % len(res['B']))
    for ch, c, to in res['B']:
        L.append('- 第%d回　%s　`%s`\n' % (ch, c, to))

    L.append('\n## C 人物接地名后缀（%d 处）\n' % len(res['C']))
    for ch, c, to in res['C']:
        L.append('- 第%d回　%s　`%s`\n' % (ch, c, to))

    ctrl = sum(1 for v in res['D'].values() if v['governed'])
    L.append('\n## D 歧义表面形式（%d 种，其中受控 %d / 未受控 %d）\n'
             % (len(res['D']), ctrl, len(res['D']) - ctrl))
    for s, info in res['D'].items():
        L.append('\n### 「%s」%s\n' % (s, '（受控：同段全称回指）' if info['governed'] else '（未受控，需人工判定）'))
        seen = set()
        for r in info['rows']:
            if r['to'] in seen and not r['basis']:
                continue
            seen.add(r['to'])
            L.append('- 第%d回　%s　→ %s%s\n'
                     % (r['ch'], r['ctx'], r['to'], ('（依「%s」）' % r['basis']) if r['basis'] else ''))

    L.append('\n## E 地名与官职代称相邻（%d 处）\n' % len(res['E']))
    for ch, c, to in res['E']:
        L.append('- 第%d回　%s　`%s`\n' % (ch, c, to))
    return ''.join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', default='', help='只看某一类（A/B/C/D/E）')
    args = ap.parse_args()
    chs, persons, places = load()
    res, ms = audit(chs, persons, places)
    if args.check:
        print(json.dumps(res[args.check], ensure_ascii=False, indent=1))
        return
    md = report(res, ms)
    os.makedirs(os.path.join(BUILD, 'audit'), exist_ok=True)
    io.open(os.path.join(BUILD, 'audit', 'report.md'), 'w', encoding='utf-8').write(md)
    # A 组的键是 (标签, 字面) 元组，JSON 需要转成字符串
    out = {k: ({(str(a), str(b)): v for (a, b), v in val.items()} if k == 'A' else val)
           for k, val in res.items()}
    out['A'] = {('%s|%s' % k): v for k, v in out['A'].items()}
    json.dump(out, io.open(os.path.join(BUILD, 'audit', 'report.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1, default=list)
    print(md)


if __name__ == '__main__':
    main()
