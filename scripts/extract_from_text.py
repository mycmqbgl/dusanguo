#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从正文上下文补官职与事迹线索（只取原文，不编造）。

针对官职缺失 / 简介为占位符的自动建档卡：
  在 120 回正文里定位该人名，取前后窗口，用官职词表匹配「<官职>+名」
  或「名+，+<官职>」两种语序，取出现最多的官职回填 tenure.title；
  同时把第一次出现的上下文摘录成 summary 线索（仍标注为「原文未详述」）。
"""
import glob
import json
import os
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 官职词表（按长度降序，避免「将军」吃掉「大将军」）
OFFICIALS = [
    '大将军', '骠骑将军', '车骑将军', '卫将军', '征东将军', '征西将军', '征南将军',
    '征北将军', '镇东将军', '镇西将军', '镇南将军', '镇北将军', '平东将军', '平西将军',
    '平南将军', '平北将军', '前将军', '后将军', '左将军', '右将军', '安东将军',
    '安西将军', '安南将军', '安北将军', '建威将军', '建武将军', '奋武将军', '奋威将军',
    '扬武将军', '扬烈将军', '昭武将军', '昭文将军', '讨逆将军', '讨虏将军', '破虏将军',
    '征虏将军', '威远将军', '宁远将军', '定远将军', '龙骧将军', '虎威将军', '牙门将军',
    '领军将军', '护军将军', '中领军', '中护军', '监军', '别驾', '主簿', '长史', '司马',
    '从事', '掾', '参军', '祭酒', '都督', '太守', '刺史', '州牧', '京兆尹', '河南尹',
    '校尉', '都尉', '中郎将', '尚书', '侍中', '侍郎', '丞相', '司空', '司徒', '太尉',
    '太傅', '太保', '大司马', '御史大夫', '御史中丞', '黄门侍郎', '中书令', '秘书丞',
    '县令', '县丞', '郎中', '议郎', '大夫', '国相', '舍人', '将军', '亭侯', '都亭侯',
    '治中', '治中从事', '功曹', '主记', '书佐', '兵曹', '户曹', '议曹', '文学掾',
    '军师', '军师中郎将', '参谋', '先锋', '监丞', '少府', '大鸿胪', '太仆', '卫尉',
    '宗正', '大司农', '将作大匠', '城门校尉', '步兵校尉', '屯骑校尉', '越骑校尉',
    '射声校尉', '长水校尉', '司隶校尉', '执金吾', '光禄勋', '大长秋', '中常侍',
    '部将', '偏将', '裨将', '牙将', '上将', '副将', '大将', '猛将', '名将', '骁将',
    '司直', '秘书', '秘书郎', '秘书令', '洞主', '将佐', '先锋', '末将', '部曲',
    '谋士', '宾客', '博士', '国舅', '驸马', '世子', '公子',
]
# 并列结构：官职 + 人名 + (、人名)* ——「遣大将杨昂、杨任」里杨任的官职要回看
PARALLEL = re.compile('(' + '|'.join(OFFICIALS) + r')[\u4e00-\u9fa5]{1,4}(?:、[\u4e00-\u9fa5]{0,4}){0,4}$')
# 「…二将为先锋」「…以惇为司马」
POST_LOOSE = re.compile(r'^[^。！？；]{0,4}为(' + '|'.join(OFFICIALS) + ')')
OFF_RE = re.compile('(' + '|'.join(OFFICIALS) + r')[\s、，,（(]?$')
OFF_AFTER = re.compile(r'^[\s、，,：:（(]?(' + '|'.join(OFFICIALS) + ')')


def load_text():
    """返回 [(chapter_no, paragraph_text), ...]"""
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'build', 'chapters', '*.json'))):
        try:
            d = json.load(open(f, encoding='utf-8'))
        except Exception:
            continue
        base = os.path.basename(f)
        mm = re.search(r'(\d+)', base)
        if not mm:
            continue
        no = int(mm.group(1))
        if isinstance(d, dict):
            ch = d.get('chapter') if isinstance(d.get('chapter'), dict) else {}
            no = ch.get('no') or no
            ps = d.get('passages') or d.get('paragraphs') or []
        else:
            ps = d
        for p in ps:
            t = p.get('text') if isinstance(p, dict) else str(p)
            if t:
                out.append((no, t))
    return out


SPLIT = re.compile(r'[，,、；;。！？：:「」（）()]')


def find_official(name, paras, win=9):
    """在正文窗口里找该人名**紧贴**的官职。

    关键：人名前的文本若含标点，只取最后一段——否则会把
    「治中邓义、别驾刘先」里刘先的「别驾」误配给邓义。
    返回 (Counter, 首见回目, 上下文)
    """
    cnt = Counter()
    first_ch, first_ctx = None, None
    for no, t in paras:
        for m in re.finditer(re.escape(name), t):
            a, b = m.start(), m.end()
            if first_ch is None:
                first_ch = no
                first_ctx = t[max(0, a - 24):b + 24]
            # 最严格：官职字面**直接紧贴**人名左侧，如「越嶲郡太守高定」「都督蔡林」。
            # 这样可排除「治中邓义、别驾刘先」里属于旁人的官职。
            pre = t[max(0, a - win):a]
            got = None
            for off in OFFICIALS:            # 已是长词优先
                if len(off) <= len(pre) and pre.endswith(off):
                    got = off
                    break
            if got:
                cnt[got] += 1
                continue
            # 次选：并列结构回看 —— 「遣大将杨昂、杨任」里杨任同为大将
            pre30 = t[max(0, a - 34):a]
            mp = PARALLEL.search(pre30)
            if mp:
                cnt[mp.group(1)] += 1
                continue
            # 再次：人名后「…为 + 官职」
            post = t[b:b + win]
            mm2 = POST_LOOSE.match(post)
            if mm2:
                cnt[mm2.group(1)] += 1
    return cnt, first_ch, first_ctx


def main():
    apply = '--fix' in sys.argv
    P = {}
    files = sorted(glob.glob(os.path.join(ROOT, 'data', 'persons*.json')))
    for f in files:
        for p in json.load(open(f, encoding='utf-8')).get('persons', []):
            P.setdefault(p['id'], p)

    audit = json.load(open(os.path.join(ROOT, 'data', 'audit_full.json'),
                           encoding='utf-8'))
    miss_ids = {x['id'] for x in audit.get('⑥官职缺失', [])}
    ph_ids = {x['id'] for x in audit.get('③简介为占位符', [])}
    todo = (miss_ids | ph_ids) & set(P)

    paras = load_text()
    print(f'正文 {len(paras)} 段；待补 {len(todo)} 人')

    got_title, got_ctx, nothing = [], [], []
    for pid in sorted(todo):
        p = P[pid]
        nm = p.get('name') or ''
        if not nm:
            continue
        cnt, ch, ctx = find_official(nm, paras)
        best = cnt.most_common(1)[0][0] if cnt else None
        # 回填官职
        filled = False
        if best:
            for t in p.get('tenure', []) or []:
                if not (t.get('title') or '').strip():
                    t['title'] = best
                    t['basis'] = (t.get('basis') or '') + \
                        f' 官职「{best}」据原文上下文提取。'
                    filled = True
            if filled:
                got_title.append((nm, best, ch))
        # 回填首见章回 + 上下文线索
        touched = False
        if ch and not isinstance(p.get('first_chapter'), int):
            p['first_chapter'] = ch
            touched = True
        if ctx and (p.get('summary') or '').startswith('《三国演义》人物'):
            p['summary'] = f'（原文未详述）{ctx[:34]}…'
            p['bio'] = (f'{nm}，原文第 {ch} 回附近出现：{ctx}。'
                        f'此卡为自动建档，生卒、字号、详细事迹待考。')
            touched = True
        if touched:
            got_ctx.append((nm, ch, best))
        if not filled and not touched:
            nothing.append(nm)

    print(f'\n补到官职 {len(got_title)} 人（样例）：')
    for a, b, c in got_title[:15]:
        print(f'  {a:5s} -> {b}  (第{c}回)')
    print(f'\n补到章回/上下文 {len(got_ctx)} 人；仍无信息 {len(nothing)} 人')
    if nothing[:15]:
        print('  无信息样例:', '、'.join(nothing[:15]))

    if apply:
        for f in files:
            d = json.load(open(f, encoding='utf-8'))
            ids = {p['id'] for p in d.get('persons', [])}
            if not (ids & todo):
                continue
            for p in d['persons']:
                if p['id'] in todo:
                    p.update(P[p['id']])
            json.dump(d, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('\n已写回')


if __name__ == '__main__':
    main()
