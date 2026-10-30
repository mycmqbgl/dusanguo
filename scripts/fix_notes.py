#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复自动建档（auto_mined）人物卡里 note 抓取造成的文本污染。

三类污染，来自名录 note 的 flush 累加逻辑：
  A 跨条目粘连：note 把下一位人物的条目也吞进来
    形如「樊建 | 蜀掾吏，樊岐：九十一回，蜀武略中郎将」
    特征：出现「<人名>：<中文数字>回」且该人名 != 本人
  B 空字号残留：「霍峻 | 字，南郡枝江人，蜀将」里的孤立「字，」
  C 句尾截断：以「后」收尾、语义不完整（「杀孙翊后」「被立魏王后」）

只改 summary / bio 两个展示字段，不动 tenure.title 之外的结构字段；
tenure.title 若同源于 summary 也一并同步。写回原 persons 文件。
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')

# A：粘连切点 —— 「：<章回>回」，回目串可长可短
GLUE = re.compile(r'[，,、]?\s*([\u4e00-\u9fa5]{2,4}?)：\s*([一二三四五六七八九十百千零\d]+回)')
# B：孤立「字，」「字：」
BARE_ZI = re.compile(r'(?:^|[，,、；;])\s*字\s*[，,：:]\s*')


def clean(txt, name):
    """返回 (清洗后文本, 是否改动)"""
    if not txt:
        return txt, False
    orig = txt
    # A：从第一个「他人名：N回」处切断
    m = GLUE.search(txt)
    if m:
        head = txt[:m.start()].rstrip('，,、；; ')
        # 切断后若过短/为空，说明整条都是别人条目，保留原文交给人工标记
        if len(head) >= 2:
            txt = head
    # B：删除孤立「字，」
    txt = BARE_ZI.sub(lambda mm: mm.group(0)[0] if mm.group(0)[0] in '，,、；;' else '', txt)
    txt = re.sub(r'\s*^[，,、；;]', '', txt)          # 开头残留逗号
    txt = re.sub(r'[，,、；;]{2,}', '，', txt)         # 连续逗号
    txt = txt.strip('，,、；; \t')
    # C：以「后」收尾的截断
    if txt.endswith('后') and len(txt) > 2:
        txt = txt[:-1].rstrip('，,、；; ')
    return txt, txt != orig


def main():
    apply = '--fix' in sys.argv
    touched, report = 0, []
    for f in sorted(glob.glob(os.path.join(DATA, 'persons*.json'))):
        d = json.load(open(f, encoding='utf-8'))
        persons = d.get('persons', [])
        changed = False
        for p in persons:
            if p.get('review_status') != 'auto_mined':
                continue
            nm = p.get('name', '')
            s, c1 = clean(p.get('summary') or '', nm)
            b, c2 = clean(p.get('bio') or '', nm)
            if not (c1 or c2):
                continue
            # bio 形如「<名>，<summary>...」，按 summary 同步重建
            if c1:
                p['summary'] = s
                p['bio'] = re.sub(r'^' + re.escape(nm) + r'[，,、]?\s*[^（(]*',
                                  nm + '，' + s, b, count=1) if b.startswith(nm) \
                            else (nm + '，' + s + '（据原文及人物名录整理；此卡为自动建档，生卒、字号、详细事迹待考。）')
            else:
                p['bio'] = b
            # tenure.title 若与旧 summary 同源则同步
            for t in p.get('tenure', []) or []:
                if t.get('title') and c1 and (t['title'] in (p.get('summary'), b)):
                    t['title'] = s
            changed = True
            touched += 1
            report.append((nm, s))
        if changed and apply:
            json.dump(d, open(f, 'w', encoding='utf-8'),
                      ensure_ascii=False, indent=1)

    print(f'待修 {touched} 张' + ('' if apply else '（只读预演，加 --fix 写回）'))
    for nm, s in report[:40]:
        print(f'  {nm} -> {s}')
    if len(report) > 40:
        print(f'  ...另有 {len(report)-40} 条')


if __name__ == '__main__':
    main()
