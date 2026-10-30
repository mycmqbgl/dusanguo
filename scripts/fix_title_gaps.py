#!/usr/bin/env python3
"""补齐 9 条官职缺失（tenure.title）。依据《三国演义》原文，不编造。"""
import json, glob, os

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FIX = {
    # 第38回：孙权弟孙翊为丹阳太守
    'sun_yi_2': '丹阳太守',
    # 第79回：丁廙字敬礼，沛郡人，临淄侯曹植属官（与兄丁仪同为曹植羽翼）
    'ding_yi_2': '临淄侯属官',
    # 第17回：封段煨为荡寇将军、伍习为殄虏将军
    'wu_xi': '殄虏将军',
    # 后主七子，演义仅列名（第118回），无封爵可考 → 留空，不编造
    'liu_xun_3': '',
    'liu_yao_2': '',
    'liu_qu': '',
    'liu_xuan': '',
    'liu_bao': '',
    # 南华老仙：仙人，原文无职
    'nan_hua_lao_xian': '',
}

def main():
    n = 0
    for f in glob.glob(os.path.join(PROJ, 'data/persons_*.json')):
        raw = json.load(open(f))
        lst = raw.get('persons', []) if isinstance(raw, dict) else raw
        dirty = False
        for p in lst:
            if p['id'] not in FIX:
                continue
            v = FIX[p['id']]
            for t in (p.get('tenure') or []):
                if v:
                    if t.get('title') != v:
                        t['title'] = v
                        n += 1
                        dirty = True
                else:
                    t.pop('title', None)
        if dirty:
            json.dump(raw, open(f, 'w'), ensure_ascii=False, indent=1)
    print('补写', n, '条 title')

if __name__ == '__main__':
    main()
