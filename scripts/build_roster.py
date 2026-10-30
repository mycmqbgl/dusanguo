#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
名录清洗 + 原文验证 → 可建档候选清单

输入：
  /tmp/roster_11087895605124.shtml   cne3online《三国人物大全》(ren_tip 标了 1124 名/字/称谓)
  data/persons_*.json                已建档 355 卡（提供 courtesy 字号 + aliases）
  data/source/ch*.txt                全书 120 回原文
  build/places.json                   454 地名（排除地名同名）

处理：
  1. 收集所有 ren_tip 名字
  2. 剔除字号：名录里「字X」的 X + 已建档卡的 courtesy + display_aliases 中的字号
  3. 剔除称谓/地名：含 老/后/妃/夫人/氏/太后/隐者/先生/大王/洞主 等、或命中地名表
  4. 原文验证：统计每个候选名在 120 回原文中出现的次数、首次出现回目
  5. 分层：
     - tier_candidate: 原文出现 >=2 次 → 建「有据卡」(summary 取原文上下文 + 名录注)
     - tier_mentioned:  原文出现 1 次 → 建「仅提及卡」(is_mentioned_only)
     - 原文 0 次 → 丢弃（名录作者自述含"仅被提及者"，未必在正文出现）
产出 data/roster_clean.json

用法：python3 scripts/build_roster.py
"""
import json, io, os, re, glob, sys
from collections import OrderedDict
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
HTML = '/tmp/roster_11087895605124.shtml'

# 称谓/非人名尾缀（这些多在名录里作为"称呼"而非本名，但仍可能是可检索人物，
# 因此不硬删，只标记 kind='appellation' 供后续决定是否建档）
APPELLATION_RE = re.compile(r'(老|仙|翁|公|主|王|后|妃|夫人|太后|美人|氏$|隐者|先生|洞主|大王|禅师|道人|童子|国老|天子|帝$|尚书|将军|丞相|太守|刺史|督邮|单于|可汗|贤王|左贤王|乌桓触)')


def collect_zihao_from_html(soup):
    """名录正文中「字X」「字XX」「号X」的 X → 字号集合"""
    zihao = set()
    for sp in soup.find_all('span', class_='ren_tip'):
        tail = ''
        n = sp.next_sibling
        while n is not None and len(tail) < 40:
            if getattr(n, 'name', None) == 'span' and 'ren_tip' in (n.get('class') or []):
                break
            tail += n if isinstance(n, str) else n.get_text()
            n = n.next_sibling
        for m in re.finditer(r'字([\u4e00-\u9fa5]{1,2})', tail):
            zihao.add(m.group(1))
    return zihao


def main():
    html = io.open(HTML, encoding='utf-8', errors='ignore').read()
    soup = BeautifulSoup(html, 'html.parser')
    for t in soup(['script', 'style']):
        t.decompose()

    # 1) 所有 ren_tip 名字 + 每个名字后的描述(取到下一个 span 前)
    entries = OrderedDict()
    for sp in soup.find_all('span', class_='ren_tip'):
        nm = sp.get_text(strip=True)
        if not re.fullmatch(r'[\u4e00-\u9fa5·]{2,6}', nm):
            continue
        tail = ''
        n = sp.next_sibling
        while n is not None and len(tail) < 60:
            if getattr(n, 'name', None) == 'span' and 'ren_tip' in (n.get('class') or []):
                break
            tail += n if isinstance(n, str) else n.get_text()
            n = n.next_sibling
        entries[nm] = re.sub(r'\s+', '', tail).lstrip('：:')

    zihao_html = collect_zihao_from_html(soup)

    # 2) 已建档
    known = {}  # name -> id
    courtesy = set()
    for f in glob.glob(os.path.join(DATA, 'persons_*.json')):
        for p in json.load(io.open(f, encoding='utf-8')).get('persons', []):
            known[p['name']] = p['id']
            for a in (p.get('match_surfaces') or []) + (p.get('display_aliases') or []):
                known.setdefault(a, p['id'])
            if p.get('courtesy'):
                courtesy.add(p['courtesy'])
                # 「伯符」这类两字字号
    zihao_all = zihao_html | courtesy

    # 3) 地名
    places = set()
    for p in json.load(io.open(os.path.join(ROOT, 'build', 'places.json'), encoding='utf-8')):
        places.add(p['name'])
        for a in (p.get('aliases') or []):
            places.add(a)

    # 4) 原文
    SRC = {}
    for f in sorted(glob.glob(os.path.join(DATA, 'source', 'ch*.txt'))):
        no = int(re.search(r'ch(\d+)', f).group(1))
        SRC[no] = io.open(f, encoding='utf-8').read()
    FULL = ''.join(SRC.values())

    # 5) 分层
    cand, mentioned, dropped = [], [], []
    for nm, desc in entries.items():
        # 已建档跳过（含别名命中）
        if nm in known:
            continue
        # 字号跳过
        if nm in zihao_all:
            dropped.append((nm, 'zihao')); continue
        if nm in places:
            dropped.append((nm, 'place')); continue
        # 单字跳过
        if len(nm) < 2:
            dropped.append((nm, 'single')); continue
        cnt = FULL.count(nm)
        first_ch = None
        for ch in sorted(SRC):
            if nm in SRC[ch]:
                first_ch = ch
                break
        kind = 'appellation' if APPELLATION_RE.search(nm) else 'name'
        rec = {'name': nm, 'count': cnt, 'first_ch': first_ch, 'kind': kind,
               'roster_note': desc[:40]}
        if cnt >= 2:
            cand.append(rec)
        elif cnt == 1:
            mentioned.append(rec)
        else:
            dropped.append((nm, 'not-in-text'))

    cand.sort(key=lambda r: (-r['count'], r['first_ch'] or 999))
    mentioned.sort(key=lambda r: (r['first_ch'] or 999))

    out = os.path.join(DATA, 'roster_clean.json')
    json.dump({
        'source': 'cne3online 三国人物大全 ren_tip 清洗 + 原文验证',
        'total_ren_tip': len(entries),
        'known_matched': len(entries) - len(cand) - len(mentioned) - len(dropped),
        'candidate_ge2': len(cand),
        'mentioned_eq1': len(mentioned),
        'dropped': len(dropped),
        'candidates': cand, 'mentioned': mentioned,
        'dropped_detail': dropped,
    }, io.open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"ren_tip {len(entries)} | 已建档命中 {len(entries)-len(cand)-len(mentioned)-len(dropped)}")
    print(f"候选(原文≥2次) {len(cand)} | 仅提及(=1次) {len(mentioned)} | 剔除 {len(dropped)}")
    print(f"→ 可新增合计 {len(cand)+len(mentioned)}；连同现有 355 → {355+len(cand)+len(mentioned)}")
    print(f"已写出 {out}")
    print('--- 候选前 50 ---')
    for r in cand[:50]:
        print(f"  {r['count']:4d} ch{str(r['first_ch'] or '?'):>3s} [{r['kind'][:4]}] {r['name']:5s} {r['roster_note'][:28]}")
    print('--- 剔除原因统计 ---')
    from collections import Counter
    print(Counter(d[1] for d in dropped))


if __name__ == '__main__':
    main()
