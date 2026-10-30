#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""清零 audit_full 的剩余问题（208 项）

  ②18 条  生卒皆 null 却标 date_precision=approx  → 改 unknown
  ②1 条   凌统只有生年 189 无卒年                 → 补 217（史载建安二十二年卒，年二十九）
  ⑨1 条   士燮 first_chapter 为 null 且无说明      → is_mentioned_only=true
  ③33 条  简介为占位符（正文 0 次的空卡）          → 改为诚实的「仅见于人物名录，正文未出现」
  ⑥151 条 官职缺失：
           · 正文 0 次（35 人）→ 标 is_mentioned_only，不再要求官职
           · 正文有出现但无官职线索 → title 填「（原文未载具体官职）」，
             并回填首见章回，绝不编造
  ⑦4 条   追谥片 timeline 晚于卒年 → 已改校验规则豁免（死后追尊属正常）
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

PH = re.compile(r'^《三国演义》人物(名录收录，谓)?见于第\d+回。?$')


def load_text():
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'build', 'chapters', '*.json'))):
        try:
            d = json.load(open(f, encoding='utf-8'))
        except Exception:
            continue
        ch = d.get('chapter') if isinstance(d.get('chapter'), dict) else {}
        no = ch.get('no') or int(re.search(r'(\d+)', os.path.basename(f)).group(1))
        for p in d.get('passages') or []:
            if p.get('text'):
                out.append((no, p['text']))
    return out


def main():
    apply = '--fix' in sys.argv
    audit = json.load(open(os.path.join(DATA, 'audit_full.json'), encoding='utf-8'))
    prec_ids = {x['id'] for x in audit.get('②生卒缺失但精度非unknown', [])}
    ph_ids = {x['id'] for x in audit.get('③简介为占位符', [])}
    miss_ids = {x['id'] for x in audit.get('⑥官职缺失', [])}

    paras = load_text()
    full = '\n'.join(t for _, t in paras)

    files = sorted(glob.glob(os.path.join(DATA, 'persons*.json')))
    log = {'precision': 0, 'death': 0, 'mentioned_only': 0, 'title': 0, 'summary': 0}
    for f in files:
        d = json.load(open(f, encoding='utf-8'))
        dirty = False
        for p in d.get('persons', []):
            pid = p['id']
            nm = p.get('name') or ''
            zero = nm and full.count(nm) == 0

            # ② 精度修正
            if pid in prec_ids and p.get('birth') is None and p.get('death') is None:
                if p.get('date_precision') != 'unknown':
                    p['date_precision'] = 'unknown'
                    log['precision'] += 1
                    dirty = True

            # ② 凌统补卒年
            if pid == 'ling_tong' and p.get('birth') == 189 and not p.get('death'):
                p['death'] = 217
                p['date_note'] = ('生年 189（史载），卒年 217：史载建安二十二年卒，'
                                  '年二十九；演义中后期仍有出场，此处采史载。')
                log['death'] += 1
                dirty = True

            # ⑨ 士燮
            if pid == 'shi_xie' and p.get('first_chapter') is None:
                p['is_mentioned_only'] = True
                log['mentioned_only'] += 1
                dirty = True

            # 正文 0 次 → 标注，不再要求官职
            if zero and pid in miss_ids:
                p['is_mentioned_only'] = True
                log['mentioned_only'] += 1
                dirty = True

            # ③ 占位符简介 → 诚实措辞
            s = (p.get('summary') or '').strip()
            if PH.match(s):
                if zero:
                    p['summary'] = '仅见于人物名录；正文 120 回中未出现，演义无事迹。'
                    p['bio'] = (f'{nm}，仅见于人物名录，演义正文 120 回中未出现，'
                                f'无事迹可述。此卡为自动建档，生卒、字号、官职均无考，'
                                f'未作任何补写。')
                else:
                    p['summary'] = '（原文未详述其官职事迹）'
                log['summary'] += 1
                dirty = True

            # ⑥ 官职：正文有出现但无线索 → 诚实标注
            if not zero and pid in miss_ids:
                for t in p.get('tenure', []) or []:
                    if not (t.get('title') or '').strip():
                        t['title'] = '（原文未载具体官职）'
                        log['title'] += 1
                        dirty = True
                if not isinstance(p.get('first_chapter'), int):
                    for no, t in paras:
                        if nm and nm in t:
                            p['first_chapter'] = no
                            break
                    dirty = True

        if dirty and apply:
            json.dump(d, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print('处理统计：' + ('' if apply else '（预演，加 --fix 写回）'))
    for k, v in log.items():
        print(f'  {k}: {v}')


if __name__ == '__main__':
    main()
