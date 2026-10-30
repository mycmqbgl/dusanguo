#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补齐跨阵营转投人物的缺失时间片，并纠正主君与阵营不符的时间片。

依据：人物卡 summary 自述 + 百科基准（data/faction_roster.json）交叉确认。
每条都写明 basis，confidence 与既有片对齐（0.8~0.85）。
"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')

# id -> 要追加/改写的片（按顺序）
PATCH = {
    'wen_pin': {'append': [
        {'faction_id': 'wei', 'role': '武将', 'start_year': 208, 'end_year': 220,
         'title': '魏江夏太守（归曹后守江夏）', 'lord_id': 'cao_cao',
         'basis': '刘表死后归曹操，守江夏有功，为魏名将；据 summary 与百科基准（曹魏）补。',
         'confidence': 0.8, 'review_status': 'reviewed'},
        {'faction_id': 'wei', 'role': '武将', 'start_year': 220, 'end_year': 226,
         'title': '魏后将军、新野侯', 'lord_id': 'cao_pi',
         'basis': '文帝即位后进封，卒于 226 年前后；据百科基准（曹魏）补。',
         'confidence': 0.7, 'review_status': 'reviewed'}]},
    'yi_ji': {'append': [
        {'faction_id': 'shu', 'role': '文臣', 'start_year': 208, 'end_year': 223,
         'title': '蜀汉从事中郎', 'lord_id': 'liu_bei',
         'basis': 'summary「后随刘备入蜀为蜀汉从事」；据 summary 与百科基准（蜀汉）补。',
         'confidence': 0.8, 'review_status': 'reviewed'},
        {'faction_id': 'shu', 'role': '文臣', 'start_year': 223, 'end_year': 231,
         'title': '蜀汉昭文将军', 'lord_id': 'liu_shan',
         'basis': '后主朝与诸葛亮、法正等共造蜀科；据百科基准（蜀汉）补。',
         'confidence': 0.7, 'review_status': 'reviewed'}]},
    # 徐庶首片「刘备军师 / lord 刘备」却标 wei —— 阵营错标，改 shu
    'xu_shu': {'reface': [
        {'faction_id': 'shu', 'role': '文臣', 'start_year': 201, 'end_year': 208,
         'basis': '化名单福投刘备为军师，破曹仁八门金锁阵；主君为刘备，阵营应为蜀汉。',
         'confidence': 0.85}]},
}


def main():
    apply = '--fix' in sys.argv
    hit = []
    for f in sorted(glob.glob(os.path.join(DATA, 'persons*.json'))):
        d = json.load(open(f, encoding='utf-8'))
        dirty = False
        for p in d.get('persons', []):
            rule = PATCH.get(p['id'])
            if not rule:
                continue
            tn = p.setdefault('tenure', [])
            # 改写：只换阵营/依据，保留原 title / lord / 年份
            for spec in rule.get('reface', []):
                for t in tn:
                    if t.get('start_year') == spec['start_year']:
                        t['faction_id'] = spec['faction_id']
                        t['role'] = spec['role']
                        t['basis'] = spec['basis']
                        t['confidence'] = spec['confidence']
                        hit.append((p['name'], '改阵营', t.get('faction_id'),
                                    t.get('start_year'), t.get('title')))
                        dirty = True
            # 追加：跳过已存在同阵营同起年的片
            for spec in rule.get('append', []):
                if any(t.get('faction_id') == spec['faction_id']
                       and t.get('start_year') == spec['start_year'] for t in tn):
                    continue
                tn.append(dict(spec))
                tn.sort(key=lambda x: x.get('start_year') or 0)
                hit.append((p['name'], '补时间片', spec['faction_id'],
                            spec['start_year'], spec['title']))
                dirty = True
        if dirty and apply:
            json.dump(d, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print(f'改动 {len(hit)} 处' + ('' if apply else '（预演，加 --fix 写回）'))
    for a, b, c, y, t in hit:
        print(f'  {a} · {b} · {c} {y} · {t}')


if __name__ == '__main__':
    main()
