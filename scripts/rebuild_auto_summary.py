#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重建 233 张「summary 为原文片段」的自动建档卡。

问题来源：早期自动建档把「名字在原文中出现的位置」的上下文窗口直接塞进
summary/bio，导致：
  1. summary 是半句原文（「（原文未详述）故招此祸。”策笑曰…」）
  2. bio 里带「原文第 N 回附近出现：…此卡为自动建档」的模板说明
  3. 阵营随「名字第一次出现的位置」而定（何曾出现在第 29 回孙策对话里，
     就被归为 warlord），实际他是晋司徒

修复原则（不编造）：
  - summary：只用卡内已有事实（tenure 的阵营+身份+官职、首见回目、性别）拼句
  - bio：把原文片段改写成「原文出处」形式，明确标注是引文而非事迹
  - 原文片段本身保留，但明确标记为「原文片段」而不是冒充简介
"""
import json, glob, re, sys, os

ROOT = '/workspace/读三国-project'
FAC_CN = {'han': '东汉', 'warlord': '群雄', 'wei': '曹魏', 'wu': '孙吴',
          'shu': '蜀汉', 'jin': '西晋', 'barbarian': '南蛮', 'mystic': '神怪'}
ROLE_CN = {'皇帝': '皇帝', '追谥': '追尊', '君主': '君主', '权臣': '权臣',
           '亲族': '宗室', '文臣': '文臣', '武将': '武将', '女眷': '女眷', '其他': ''}

SNIP = re.compile(r'原文第\s*(\d+)\s*回附近出现：(.+?)。?此卡为自动建档')


def clean_snippet(q):
    """把原文片段里明显的截断残句整理成可读的一句"""
    q = q.strip().strip('。')
    q = re.sub(r'^[，。、；：""''）】]*', '', q)
    q = re.sub(r'[“”"]+', '「', q, count=1) if False else q
    return q


def build_summary(p):
    """仅用卡内事实拼一句简介"""
    name = p['name']
    tns = [t for t in (p.get('tenure') or []) if isinstance(t, dict)]
    # 主片：取时间最早的一片作为「主要身份」
    tns_sorted = sorted(tns, key=lambda t: (t.get('start_year') or 999))
    parts = []
    if tns_sorted:
        t = tns_sorted[-1]   # 取最晚的一片，通常代表其最终归属
        fac = FAC_CN.get(t.get('faction_id'), '')
        role = ROLE_CN.get(t.get('role'), '')
        title = (t.get('title') or '').strip()
        title = '' if '（原文未载' in title else title
        seg = fac
        if role and role != fac:
            seg += role
        if title:
            seg += f'，{title}'
        parts.append(seg)
    if p.get('gender') == 'female' and not parts:
        parts.append('女性人物')
    if not parts:
        return None
    s = name + '，' + '；'.join(parts) + '。'
    # 加上首见回目，标准句
    fc = p.get('first_chapter')
    if isinstance(fc, int):
        s += f'见于《三国演义》第 {fc} 回。'
    return s


def build_bio(p):
    """把原文片段改写成明确的「原文出处」说明，不再冒充事迹"""
    b = p.get('bio') or ''
    m = SNIP.search(b)
    name = p['name']
    tns = [t for t in (p.get('tenure') or []) if isinstance(t, dict)]
    seg = []
    if tns:
        last = sorted(tns, key=lambda t: (t.get('start_year') or 999))[-1]
        fac = FAC_CN.get(last.get('faction_id'), '')
        role = ROLE_CN.get(last.get('role'), '')
        title = (last.get('title') or '').strip()
        title = '' if '（原文未载' in title else title
        head = f'{name}，{fac}{role}'
        if title:
            head += f'，任{title}'
        seg.append(head + '。')
    if m:
        no, q = m.group(1), clean_snippet(m.group(2))
        seg.append(f'原文第 {no} 回相关片段：「{q}」（此句为全书中该名出现处的上下文，'
                   f'未必全是其本人事迹，未作考据）。')
    seg.append('本卡依人物名录与原文提及自动建档；生卒、字号、详细事迹俟考，未做推测。')
    return ''.join(seg)


def main(apply=False):
    changed = 0
    samples = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'data', 'persons*.json'))):
        d = json.load(open(f, encoding='utf-8'))
        dirty = False
        for p in d.get('persons', []):
            s = p.get('summary') or ''
            if not s.startswith('（原文'):
                continue
            ns = build_summary(p)
            if not ns:
                continue
            nb = build_bio(p)
            samples.append((p['name'], ns, nb))
            if apply:
                p['summary'] = ns
                p['bio'] = nb
                dirty = True
            changed += 1
        if dirty:
            json.dump(d, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'{"已改写" if apply else "预演"}：{changed} 张')
    for n, s, b in samples[:15]:
        print(f'  {n:6s} | {s}')
        print(f'          {b[:80]}')


if __name__ == '__main__':
    main('--fix' in sys.argv)
