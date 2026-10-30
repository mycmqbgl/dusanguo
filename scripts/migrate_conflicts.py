#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P1-1 定案（v1.3）存量卡片迁移辅助：把写在 date_note / bio 里的史异表述
提取为 history_conflict_type + history_conflict_note 的**候选**。

为什么只做候选：判类型（功劳归属/事件有无/职官归属/生死结局）需要读上下文，
机器只能按关键词猜。所以本脚本只产出候选清单，绝不直接改数据文件；
人工确认类型后用 --apply 落到指定文件，并把这些卡的 review_status 降为 auto_generated。

用法：
  python3 scripts/migrate_conflicts.py                 # 只扫描，输出 build/conflict_candidates.json
  python3 scripts/migrate_conflicts.py --list          # 扫描并打印候选摘要
  python3 scripts/migrate_conflicts.py --apply build/conflict_candidates.json
"""
import json, io, os, sys, re, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
BUILD = os.path.join(ROOT, 'build')

# 已有的史异表述关键词
MARKERS = ('演义', '史实', '史载', '史书', '当从', '史为', '三国志', '后汉书')

# 候选提取只认「双句式」：同一句里既有演义侧词、又有史书侧词，且出现差异标记词。
# 不猜类型——实测关键词猜类型精确率很低（关羽、张角、刘备都会被误判），
# 宁可在 date_note 里多留一阵，也不能把错类型写进数据。
YAN = ('演义', '本书', '小说')
SHI = ('史实', '史载', '史书', '实为', '当从', '三国志', '后汉书')
# 「实为」太泛（「实为曹操内应」这类是情节陈述，不是史异），只在史侧词 ≠ 实为时才算差异标记
DIFF = ('当从', '史实为', '演义作', '演义未载', '演义未写', '演义归功', '演义将',
        '史书无载', '史无', '原型', '无载', '不见于')


def looks_like_conflict(sentence):
    """判断一句话是否像硬冲突表述（仍需人工确认类型）。

    必须有「演义侧」与「史书侧」同时在场，且出现至少一个**翻转词**
    （当从／史实为／演义作／演义归功／史无／原型…）。
    只出现「史载」而没有演义侧对照的，是在陈述史实，不是史异——这类曾被大面积误报（刘备、吴硕）。
    """
    has_yan = any(k in sentence for k in YAN)
    has_shi = any(k in sentence for k in SHI)
    has_diff = any(k in sentence for k in DIFF)
    if not has_shi:
        return False
    # 演义侧与史书侧必须同时在场，且至少一个翻转词：三者缺一不出候选。
    # 注意「史载为X」只在陈述史实年份，不是翻转，故不入 DIFF（刘备曾因此误报）。
    return has_yan and has_diff


def split_sentences(text):
    return [s.strip() for s in re.split(r'[。；;]', text or '') if s.strip()]


def scan():
    cands = []
    for f in sorted(glob.glob(os.path.join(DATA, 'persons_*.json'))):
        d = json.load(io.open(f, encoding='utf-8'))
        arr = d['persons'] if isinstance(d, dict) else d
        for p in arr:
            if p.get('history_conflict_type'):
                continue                      # 已迁移
            texts = [(k, p.get(k) or '') for k in ('date_note', 'bio', 'summary')]
            hits = []
            for k, t in texts:
                for s in split_sentences(t):
                    if looks_like_conflict(s):
                        hits.append({'field': k, 'sentence': s})
            if hits:
                cands.append({
                    'id': p['id'], 'name': p.get('name'), 'file': os.path.basename(f),
                    'history_conflict_type': '',      # 留空，人工填四类之一
                    'evidence': hits,
                    'current_date_note': p.get('date_note') or '',
                })
    return cands


def apply(path):
    cands = json.load(io.open(path, encoding='utf-8'))
    by_file = {}
    for c in cands:
        t = c.get('history_conflict_type')
        note = (c.get('history_conflict_note') or '').strip()
        if not t or not note:
            print('  跳过（缺类型或未写 note）：%s %s' % (c['id'], c.get('name')))
            continue
        by_file.setdefault(c['file'], {})[c['id']] = (t, note)
    n = 0
    for fname, m in by_file.items():
        fp = os.path.join(DATA, fname)
        d = json.load(io.open(fp, encoding='utf-8'))
        arr = d['persons'] if isinstance(d, dict) else d
        for p in arr:
            if p['id'] in m:
                p['history_conflict_type'], p['history_conflict_note'] = m[p['id']]
                p['review_status'] = 'auto_generated'
                n += 1
        # 保持原文件换行与格式：json.dumps 会把紧凑数组展开成多行，造成无关 diff。
        # 这里只做「读回—写回」最小改动：先按原缩进序列化，再还原 CRLF。
        raw = io.open(fp, encoding='utf-8', newline='').read()
        nl = '\r\n' if '\r\n' in raw else '\n'
        text = json.dumps(d, ensure_ascii=False, indent=1).replace('\n', nl)
        io.open(fp, 'w', encoding='utf-8', newline='').write(text)
    print('已写入 %d 张卡，请人工复核类型后再转 reviewed' % n)


def main():
    args = sys.argv[1:]
    if '--apply' in args:
        apply(args[args.index('--apply') + 1])
        return
    cands = scan()
    os.makedirs(BUILD, exist_ok=True)
    out = os.path.join(BUILD, 'conflict_candidates.json')
    json.dump(cands, io.open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('候选 %d 张（type 全部留空待人工判）→ %s' % (len(cands), out))
    if '--list' in args:
        for c in cands:
            print('  %-14s %-10s %-6s %s' % (c['id'], c['name'], c['evidence'][0]['field'],
                                              c['evidence'][0]['sentence'][:70]))


if __name__ == '__main__':
    main()
