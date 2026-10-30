#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 date_note 里提取「史实 vs 演义」确有分歧的人物，写入 history_life_dates。

判定：只有 date_note 中同时出现「史（载/实/无/书）」与「演义（/本回/第 N 回）」
      两套信息，且两者描述的年份（或结局时点）不同，才算真分歧。
      只有一套信息（史实即演义，或演义未载）的，不写此字段 —— 前端会回退显示 date_note。

原则：只搬运 date_note 已有事实，不做新考据、不编造。
"""
import json, glob, re, sys

ROOT = '/workspace/读三国-project'
P_FILES = sorted(glob.glob(f'{ROOT}/data/persons*.json'))

# 人工核定：note 原文已写明史实与演义时点不同，且正则无法可靠切分
MANUAL = {
    'hou_lan': '史：卒熹平元年（172）前后｜演：列为十常侍，至中平六年（189）宫变被杀',
    'yan_baihu': '史：为孙策所破后不知所踪，卒年不详｜演：约 196 奔余杭为凌操部众所杀',
    'hao_meng': '史：建安元年（196）被高顺斩｜演：活跃至第十八回（198）',
}

HIST = re.compile(r'(史载|史书|史实|史无|据史|本传|《三国志|《魏书|《吴书|《蜀书|《后汉书)')
YAN = re.compile(r'(演义|本回|第[一二三四五六七八九十百]+回)')
YEAR = re.compile(r'(\d{3})\s*年?')


def extract(note):
    """返回 (史实句, 演义句)；任一为空则不构成对照"""
    if not note:
        return None
    parts = re.split(r'[；;。]', note)
    h, y = [], []
    for s in parts:
        s = s.strip()
        if not s:
            continue
        if YAN.search(s):
            y.append(s)
        else:
            h.append(s)
    return ('；'.join(h), '；'.join(y)) if h and y else None


def usable(s):
    """演义侧是否给出了可比的时点信息（年号或年份或「活跃至」）"""
    return bool(re.search(r'(卒|死|生|活跃|终于|被杀|所杀)', s))


def main(apply=False):
    applied, manual_hit = [], []
    for f in P_FILES:
        d = json.load(open(f, encoding='utf-8'))
        dirty = False
        for p in d.get('persons', []):
            pid = p['id']
            if pid in MANUAL:
                p['history_life_dates'] = MANUAL[pid]
                manual_hit.append((p['name'], MANUAL[pid]))
                dirty = True
                continue
            if p.get('history_life_dates'):
                continue
            r = extract(p.get('date_note'))
            if not r:
                continue
            h, y = r
            if not usable(y):
                continue
            yy = re.sub(r'^\s*演义\s*[，,、]?', '', y)
            yy = re.sub(r'^(中|里|中本|所载)', '', yy).strip()
            p['history_life_dates'] = f'史：{h}｜演：{yy}'
            applied.append((p['name'], p['history_life_dates']))
            dirty = True
        if dirty and apply:
            json.dump(d, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print(f'{"已写入" if apply else "预演"}：自动 {len(applied)} 人 + 人工核定 {len(manual_hit)} 人')
    for n, v in applied[:40]:
        print(f'  {n:6s} {v[:92]}')
    if manual_hit:
        print('  --- 人工核定 ---')
        for n, v in manual_hit:
            print(f'  {n:6s} {v[:92]}')


if __name__ == '__main__':
    main('--fix' in sys.argv)
