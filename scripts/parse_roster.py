#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
解析 cne3online《三国人物大全》名录 HTML → 结构化人名表。

源页面每位人物形如：<span class="ren_tip">鲍信</span>：三回，初为济北相。剿青州黄巾军，被害。
作者自述：「所列之人有些并未出场，只被提及……只列回数……人名以汉语拼音排列」，
正好覆盖《三国演义》有名有姓者约 1191 人 + 仅提及者，是铺量到 1200+ 的权威词表来源。

产出 data/roster.json:
  [{name, chapter_raw, chapter, note, pinyin_group}, ...]

用法：python3 scripts/parse_roster.py [/tmp/roster_11087895605124.shtml]
"""
import json, io, os, re, sys
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
DEFAULT_HTML = '/tmp/roster_11087895605124.shtml'

CN_NUM = {'零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
          '十': 10, '百': 100, '两': 2}


def cn2int(s):
    """中文数字 → int，支持 一~一百二十"""
    if not s:
        return None
    if s.isdigit():
        return int(s)
    total, section, num = 0, 0, 0
    for ch in s:
        if ch not in CN_NUM:
            return None
        v = CN_NUM[ch]
        if v == 100:
            section = (section or 1) * 100
            total += section
            section, num = 0, 0
        elif v == 10:
            section = (num or 1) * 10
            total += section
            num = 0
        else:
            num = v
    return total + section + num


def parse(html_path):
    html = io.open(html_path, encoding='utf-8', errors='ignore').read()
    soup = BeautifulSoup(html, 'html.parser')
    for t in soup(['script', 'style']):
        t.decompose()
    # 定位到正文容器：找含 ren_tip span 的顶层 div
    holders = []
    for sp in soup.find_all('span', class_='ren_tip'):
        holders.append(sp)
    # 用每个 span 的文本 + 其后紧邻的兄弟文本拼出「：回数，描述」
    out = []
    seen = set()
    for sp in holders:
        name = sp.get_text(strip=True)
        if not name or not re.fullmatch(r'[\u4e00-\u9fa5·]{2,6}', name):
            continue
        # 该 span 之后紧邻的文本节点（直到下一个 span 或段落结束）
        tail = ''
        node = sp.next_sibling
        while node is not None:
            if getattr(node, 'name', None) == 'span' and 'ren_tip' in (node.get('class') or []):
                break
            if isinstance(node, str):
                tail += node
            else:
                tail += node.get_text()
            node = node.next_sibling
            if len(tail) > 120:
                break
        tail = tail.strip()
        # tail 形如 「：三回，初为济北相。剿青州黄巾军，被害。」
        m = re.match(r'^[：:]\s*([一二三四五六七八九十百零两0-9]+)回[，,]?\s*(.*)', tail)
        if not m:
            # 有些条目没有回数，只要名字
            ch, note = None, tail.lstrip('：:').strip()
        else:
            ch = cn2int(m.group(1))
            note = m.group(2).strip()
        # note 截到下一个可能的条目开始（人名+冒号）之前
        note = re.split(r'[\u4e00-\u9fa5·]{2,6}[：:]', note)[0].strip()
        # 去掉尾部残留
        note = re.sub(r'\s+', '', note)
        key = name
        if key in seen:
            continue
        seen.add(key)
        out.append({'name': name, 'chapter_raw': None, 'chapter': ch, 'note': note})
    return out


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HTML
    rows = parse(path)
    # 过滤明显非人名（含标点、超长、纯称谓）
    rows = [r for r in rows if 2 <= len(r['name']) <= 4 and re.fullmatch(r'[\u4e00-\u9fa5·]+', r['name'])]
    # 统计
    with_ch = sum(1 for r in rows if r['chapter'])
    print(f'解析出人名 {len(rows)} 条，其中带出场回数 {with_ch} 条')
    # 与现有档案对比
    import glob
    known = set()
    for f in glob.glob(os.path.join(DATA, 'persons_*.json')):
        for p in json.load(io.open(f, encoding='utf-8')).get('persons', []):
            known.add(p['name'])
            for a in (p.get('match_surfaces') or []) + (p.get('display_aliases') or []):
                known.add(a)
    new = [r for r in rows if r['name'] not in known]
    print(f'已建档命中 {len(rows)-len(new)} 条，未建档 {len(new)} 条')
    out = os.path.join(DATA, 'roster.json')
    json.dump({'source': 'cne3online 三国人物大全', 'total': len(rows),
               'with_chapter': with_ch, 'new_count': len(new), 'rows': rows},
              io.open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('已写出', out)
    print('--- 未建档样例（前 40）---')
    for r in new[:40]:
        print(f"  ch{str(r['chapter'] or '?'):>4s} {r['name']:4s} {(r['note'] or '')[:32]}")


if __name__ == '__main__':
    main()
