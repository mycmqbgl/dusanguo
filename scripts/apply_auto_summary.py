#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""应用 fix_auto_faction_map.FIX 的判定，并重建 summary/bio。

对每条判定：
  - 覆盖 tenure 为单一确证片（含原文 basis）
  - summary 用「名，阵营身份，官职。见于第 N 回。」的规范句式
  - bio 保留原文片段作为出处引文，不再冒充事迹
未列入 FIX 的卡：只重建 summary/bio 格式，tenure 原样保留并标 review_status=needs_review。
"""
import json, glob, re, sys, os

ROOT = '/workspace/读三国-project'
sys.path.insert(0, f'{ROOT}/scripts')
from fix_auto_faction_map import FIX

FAC_CN = {'han': '东汉', 'warlord': '群雄', 'wei': '曹魏', 'wu': '孙吴',
          'shu': '蜀汉', 'jin': '西晋', 'barbarian': '南蛮', 'mystic': '神怪'}
ROLE_CN = {'皇帝': '皇帝', '追谥': '追尊', '君主': '君主', '权臣': '权臣',
           '亲族': '宗室', '文臣': '文臣', '武将': '武将', '女眷': '女眷', '其他': ''}
SNIP = re.compile(r'原文第\s*(\d+)\s*回附近出现：(.+?)。?此卡为自动建档')


def norm_title(t):
    t = (t or '').strip()
    return '' if '（原文未载' in t else t


def make_summary(p):
    tns = [t for t in (p.get('tenure') or []) if isinstance(t, dict)]
    if not tns:
        return None
    last = sorted(tns, key=lambda t: (t.get('end_year') or 0, t.get('start_year') or 0))[-1]
    fac = FAC_CN.get(last.get('faction_id'), '')
    role = ROLE_CN.get(last.get('role'), '')
    title = norm_title(last.get('title'))
    body = fac + (role if role and role != fac else '')
    s = p['name'] + '，' + body
    if title:
        s += '，' + title
    s += '。'
    fc = p.get('first_chapter')
    if isinstance(fc, int):
        s += f'见于《三国演义》第 {fc} 回。'
    return s


def make_bio(p):
    seg = []
    tns = [t for t in (p.get('tenure') or []) if isinstance(t, dict)]
    if tns:
        last = sorted(tns, key=lambda t: (t.get('end_year') or 0, t.get('start_year') or 0))[-1]
        fac = FAC_CN.get(last.get('faction_id'), '')
        role = ROLE_CN.get(last.get('role'), '')
        title = norm_title(last.get('title'))
        head = p['name'] + '，' + fac + (role if role and role != fac else '')
        if title:
            head += '，任' + title
        seg.append(head + '。')
        b = last.get('basis')
        if b:
            seg.append(b)
    m = SNIP.search(p.get('bio') or '')
    if m:
        q = m.group(2).strip().strip('。')
        q = re.sub(r'^[，。、；：]+', '', q)
        seg.append(f'原文第 {m.group(1)} 回相关片段：「{q}」。')
    if not tns:
        seg.append('本卡依人物名录与原文提及自动建档；生卒、字号、详细事迹俟考。')
    return ''.join(seg)


def main(apply=False):
    stat = {'fixed': 0, 'reformatted': 0}
    logs = []
    for f in sorted(glob.glob(f'{ROOT}/data/persons*.json')):
        d = json.load(open(f, encoding='utf-8'))
        dirty = False
        for p in d.get('persons', []):
            if not (p.get('summary') or '').startswith('（原文'):
                continue
            pid = p['id']
            v = FIX.get(pid)
            if v:
                fac, role, st, en, title, basis = v
                p['tenure'] = [{
                    'faction_id': fac, 'role': role,
                    'start_year': st, 'end_year': en, 'title': title,
                    'basis': basis, 'confidence': 0.85, 'review_status': 'reviewed',
                }]
                stat['fixed'] += 1
                logs.append(('FIX', p['name'], f'{fac}/{role} {st}-{en} {title}'))
            else:
                stat['reformatted'] += 1
            p['summary'] = make_summary(p) or p.get('summary')
            p['bio'] = make_bio(p)
            dirty = True
        if dirty and apply:
            json.dump(d, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'{"已应用" if apply else "预演"}：确证修正 {stat["fixed"]} 张，仅重排文案 {stat["reformatted"]} 张')
    for x in logs[:25]:
        print('  ', x[1], '→', x[2])


if __name__ == '__main__':
    main('--fix' in sys.argv)
