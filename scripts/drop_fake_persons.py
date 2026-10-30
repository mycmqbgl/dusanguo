#!/usr/bin/env python3
"""清理假人名、补真实爵位。

1. gan_xiu（干休）：非人名，是第4回「安肯干休」被正则误切出来的短语。
   全文 3 次出现分别在「安肯干休」「怎肯干休」「怎肯干休」语境，无一次作人称。
   → 整卡删除。
2. liu_bao（刘豹）：第80回「阳泉侯刘豹」，爵位真实，补 title。
3. 后主诸子（刘璿/刘瑶/刘璩/刘恂）：演义第118回仅列名，无封爵可考 → 保持无 title。
"""
import json, glob, os

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DROP = {'gan_xiu'}
TITLE = {'liu_bao': '阳泉侯'}


def main():
    dropped = titled = 0
    for f in glob.glob(os.path.join(PROJ, 'data/persons_*.json')):
        raw = json.load(open(f))
        is_dict = isinstance(raw, dict)
        lst = raw.get('persons', []) if is_dict else raw
        n0 = len(lst)
        lst = [p for p in lst if p['id'] not in DROP]
        dropped += n0 - len(lst)
        for p in lst:
            if p['id'] in TITLE:
                for t in (p.get('tenure') or []):
                    t['title'] = TITLE[p['id']]
                    titled += 1
        if is_dict:
            raw['persons'] = lst
        else:
            raw = lst
        json.dump(raw, open(f, 'w'), ensure_ascii=False, indent=1)
    print('删除假人名', dropped, '补爵位', titled)


if __name__ == '__main__':
    main()
