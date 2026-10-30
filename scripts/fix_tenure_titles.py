#!/usr/bin/env python3
"""修复 tenure.title 的脏数据（第三类灌水式缺陷）。

问题形态（全部有原文依据可核）：
  1. 占位符「（原文未载具体官职）」83 条  → 从原文补出真实身份，或删除字段（不编造）
  2. 被正则贪吃导致的截断残片（「曹爽门客，字」「蜀将，帐下」「乌桓触：三」）30 条 → 重写
  3. 描述性长句塞进 title 字段（「孙坚长子，随父征战」）→ 重写为职务短语
  4. 正常职务 + 括注（「偏将军（归刘备后）」）→ 保留职务、剥除括注

前四类依赖 scripts/data_title_fix.py 中的逐条核定表；剩余条目用通用规则兜底。
"""
import json, re, glob, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data_title_fix import TITLE_FIX

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = '--fix' in sys.argv

# 通用规则：只剥括注与尾部动作说明，保留官职串本身
TAIL_JUNK = [
    re.compile(r'[，,]\s*字[，,]?$'),
    re.compile(r'[，,]\s*(帐下|麾下)$'),
    re.compile(r'[，,]\s*(为|被|遭)[^，。]{0,8}(杀|斩|擒|射死|刺死|害|诛|断腕)$'),
    re.compile(r'[，,]\s*(降曹|降刘|降蜀|降吴|归曹|归刘|归蜀|归吴|降|归)$'),
    re.compile(r'[，,]\s*(操擒杀|兵败亡|病亡|早夭|自缢)$'),
]


def strip_paren(t):
    t = re.sub(r'（[^）]*）', '', t)
    t = re.sub(r'\([^)]*\)', '', t)
    return t.strip('，,、 ｜|')


def generic(ti):
    t = strip_paren(ti)
    for _ in range(3):
        before = t
        for r in TAIL_JUNK:
            t = r.sub('', t)
        if t == before:
            break
    t = re.split(r'[。；;]', t)[0]
    return t.strip('，,、 ｜|')


def load_persons():
    pids, persons = set(), []
    for f in glob.glob(os.path.join(PROJ, 'data/persons_*.json')):
        d = json.load(open(f))
        if isinstance(d, dict):
            d = d.get('persons', [])
        for p in d:
            if p.get('id') not in pids:
                pids.add(p['id'])
                persons.append(p)
    return persons


def main():
    persons = load_persons()
    pm = {p['id']: p for p in persons}
    stat = {'manual': 0, 'generic': 0, 'drop': 0}
    changed = []

    for p in persons:
        pid = p['id']
        tbl = TITLE_FIX.get(pid, {})
        tenures = [t for t in (p.get('tenure') or []) if (t.get('title') or '').strip()]
        star_ok = ('*' in tbl) and len(tenures) == 1   # '*' 仅对单任期人物生效
        if '*' in tbl and len(tenures) > 1:
            print('!! %s 有多条任期，禁止使用 *：%s' % (pid, tbl['*']))
        for t in tenures:
            ti = (t.get('title') or '').strip()
            new = '__keep__'
            if ti in tbl:
                new = tbl[ti]
            elif star_ok:
                new = tbl['*']
            else:
                g = generic(ti)
                if g != ti:
                    new = g
                    stat['generic'] += 1
            if new == '__keep__' or new == ti:
                continue
            if new is None or new == '':
                stat['drop'] += 1
                changed.append((pid, p.get('name'), ti, '<删除>'))
                if FIX:
                    t.pop('title', None)
            else:
                stat['manual'] += 1
                changed.append((pid, p.get('name'), ti, new))
                if FIX:
                    t['title'] = new

    print('manual %d / generic %d / drop %d / total %d'
          % (stat['manual'], stat['generic'], stat['drop'], len(changed)))
    for c in changed[:30]:
        print('  %-16s %-6s %s  ->  %s' % c)

    if FIX:
        for f in glob.glob(os.path.join(PROJ, 'data/persons_*.json')):
            raw = json.load(open(f))
            lst = raw.get('persons', []) if isinstance(raw, dict) else raw
            touched = False
            for i, p in enumerate(lst):
                if p.get('id') in pm and p.get('tenure'):
                    lst[i] = pm[p['id']]
                    touched = True
            if touched:
                json.dump(raw, open(f, 'w'), ensure_ascii=False, indent=1)
        print('已写回')


if __name__ == '__main__':
    main()
