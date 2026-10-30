#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
未登录实体挖掘：从原文里捞出「看起来是人名、但还没建档」的候选。

为什么需要它
  词典匹配的漏链是静默的——「孙坚」在第二回出现 11 次，没卡片就一次都链不上，
  界面上看不出来。这个工具反过来读原文，用「姓+名 后跟说话/动作动词」这类高置信模式
  把人名捡回来，按出现次数排序，直接产出下一批批产的名单。

模式（按精度降序）
  P1 自我介绍   「姓孙，名坚，字文台」        精度最高，直接给全名+字
  P2 字         「关羽字云长」／「名绍，字本初」
  P3 官职+名    「刺史臧旻」「太守龚景」      精度高，官职称谓后面几乎必是人名
  P4 姓+名+曰   「孙坚曰」「袁绍大怒」        召回高，需过滤爵称与常用词

用法：
  python scripts/discover_entities.py                # 全部模式
  python scripts/discover_entities.py --min 2        # 只报出现 ≥2 次的
  python scripts/discover_entities.py --out data/discovered.json
"""
import json, io, os, re, argparse
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, 'build')
DATA = os.path.join(ROOT, 'data')

SURNAMES = set('''
王李张刘陈杨黄赵吴周徐孙马朱胡郭何高林罗郑梁谢宋唐许韩冯邓曹彭曾萧田董袁潘于蒋蔡余杜叶程苏魏吕丁任沈姚卢姜崔钟谭陆汪范金石廖贾夏韦付方白邹孟熊秦邱江尹薛段雷侯龙史陶黎贺顾毛郝龚邵万钱严覃武戴莫孔向汤
'''.strip())
COMPOUND = ['诸葛', '司马', '夏侯', '皇甫', '公孙', '太史', '毋丘', '钟离', '淳于', '濮阳',
            '单于', '令狐', '上官', '东方', '独孤', '慕容', '宇文', '长孙', '呼延', '万俟']
# 爵称/官职尾字：出现即不是姓名
BAD_TAIL = set('王公侯伯子男相将军事守尉史令长君监侍郎掾吏掾')
BAD_WORDS = set(['於是', '如何', '何以', '於是', '于是', '陈留', '中山', '昌邑', '安定', '武威',
                 '张掖', '酒泉', '敦煌', '上党', '太原', '南阳', '汝南', '济南', '东海', '北海',
                 '西凉', '平原', '长沙', '零陵', '桂阳', '武陵', '会稽', '吴郡', '丹阳', '豫章'])
OFFICES = ['刺史', '太守', '将军', '校尉', '中郎将', '司徒', '太尉', '司空', '侍中', '议郎',
           '主簿', '司马', '长史', '从事', '别驾', '都尉', '相国', '太傅', '太常', '光禄勋',
           '车骑将军', '骠骑将军', '卫将军', '后将军', '前将军', '左将军', '右将军']

# 人名之后极常见的动词/虚词。演义的对话多用单称（「进曰」「绍曰」），
# 全名出现时后面常接这些字，因此放宽动词集合换召回，再用姓氏与尾字过滤压误报。
VERBS = ('曰|乃|亦|遂|大|自|引|令|使|与|谓|闻|见|至|从|将|领|拜|封|为|攻|守|走|死|降|谏|奏|'
         '怒|惊|笑|问|答|出|入|还|归|屯|进|退|率|带|持|执|拔|按|又|不|未|已|即|却|便|先|复|'
         '尚|果|竟|独|皆|尽|更|再|方|正|忽|骤|暗|密|连|急|慌|欣|素|颇|欲|请|劝|说|随|会|起|'
         '病|卒|亡|奔|逃|弃|斩|杀|刺|围|破|败|胜|追|救|护|扶|立|废|迎|送|屯|据|守|拔|克|平')
# 候选名后可能粘上的非人名字尾
TAIL_NOISE = ['府', '宅', '家', '等', '部', '众', '军', '营', '兵', '辈', '氏', '门', '第']
# 单称回推的排除字：这些字本身是指代/称谓/动作，不可能是人名的最后一字
STOP_SINGLE = set('帝后王公卿相臣将兵卒民人子女母弟兄主君父夫妇儿贼众军城郡州县关山'
                  '水河江门宫殿室家府中内外前后上下东西南北左右大小多少高低长短新旧轻'
                  '重远近是非有无可不未已果竟忽乃亦遂且而则若如故因由从与为以之其何方'
                  '又复尚独皆尽更再正欲请劝说随会起病亡奔逃弃斩杀刺围破败胜追救护扶'
                  '立废迎送据守拔克平自引令使谓闻见至攻走死降谏奏怒惊笑问答出入还归'
                  '屯进退率带持执按密连急慌欣素颇早晚先初终始末一二三四五六七八九十'
                  '百千万两数几半氏等辈')
# 不可能作为人名第二字的虚词
FUNCTION2 = set('欲不必以方又与为之其何是有无可未已果竟忽乃亦遂且而则若如故因由从'
                '相将皆尽更再正自引令使谓闻见至者也就亦矣焉哉一二三四五六七八九十七')


def load_all():
    """返回 [{no, passages:{id:text}, mentions:[...]}] 与已建档名称集合"""
    chs = []
    for f in sorted(os.listdir(os.path.join(BUILD, 'chapters'))):
        if f.endswith('.json'):
            d = json.load(io.open(os.path.join(BUILD, 'chapters', f), encoding='utf-8'))
            chs.append({'no': d['chapter']['no'],
                        'passages': {p['id']: p['text'] for p in d['passages']},
                        'mentions': d['mentions']})
    known_person, known_place = set(), set()
    for f in os.listdir(os.path.join(BUILD, 'persons')):
        if f.endswith('.json'):
            p = json.load(io.open(os.path.join(BUILD, 'persons', f), encoding='utf-8'))
            known_person.add(p['name'])
            for a in (p.get('display_aliases') or []) + [p.get('courtesy') or '']:
                if a:
                    known_person.add(a)
    for p in json.load(io.open(os.path.join(BUILD, 'places.json'), encoding='utf-8')):
        known_place.add(p['name'])
        for a in (p.get('aliases') or []):
            known_place.add(a)
    return chs, known_person, known_place


def linked_spans(ch):
    span = defaultdict(list)
    for m in ch['mentions']:
        span[m['passage_id']].append((m['start'], m['end']))
    return span


def name_ok(s, known_person, known_place):
    if len(s) < 2 or s in known_person or s in known_place or s in BAD_WORDS:
        return False
    if s[-1] in BAD_TAIL:
        return False
    if s[0] in SURNAMES:
        return True
    return any(s.startswith(c) for c in COMPOUND)


def scan(chs, known_person, known_place):
    hits = Counter()
    ev = defaultdict(list)

    def add(name, chno, ctx, pat):
        hits[name] += 1
        if len(ev[name]) < 3:
            ev[name].append({'ch': chno, 'pat': pat, 'ctx': ctx})

    # 先统计「姓+字」二元组频次：用于把单称（绍/布/允）回推成全名（袁绍/吕布/王允）
    bi, tri = Counter(), Counter()
    for ch in chs:
        for text in ch['passages'].values():
            for i in range(len(text) - 1):
                if text[i] in SURNAMES:
                    bi[text[i:i + 2]] += 1
            for cs in COMPOUND:
                st = 0
                while True:
                    k = text.find(cs, st)
                    if k < 0:
                        break
                    tri[text[k:k + 3]] += 1
                    st = k + 1

    def recover(c):
        """单称 → 全名。复姓优先（公孙瓒 而非 孙瓒）。"""
        cands = [(k, v) for k, v in tri.items() if k[2] == c]
        cands += [(k, v) for k, v in bi.items() if k[1] == c]
        cands = [x for x in cands if name_ok(x[0], known_person, known_place)]
        return max(cands, key=lambda x: x[1])[0] if cands else None

    for ch in chs:
        spans = linked_spans(ch)
        for pid, text in ch['passages'].items():
            taken = spans.get(pid, [])

            def free(a, b):
                return not any(a < e and s < b for s, e in taken)

            # P1 姓X，名Y，字Z  /  姓孙名坚字文台
            for mt in re.finditer(r'姓([\u4e00-\u9fa5]{1,2})[，,、]?名([\u4e00-\u9fa5]{1,2})(?:[，,、]?字([\u4e00-\u9fa5]{1,3}))?', text):
                full = mt.group(1) + mt.group(2)
                if name_ok(full, known_person, known_place) and free(mt.start(), mt.end()):
                    add(full, ch['no'], text[max(0, mt.start() - 8):mt.end() + 8], 'P1自我介绍' + ('字' + mt.group(3) if mt.group(3) else ''))

            # P2 「名X字Y」单独出现（承前文姓氏）
            for mt in re.finditer(r'名([\u4e00-\u9fa5])[，,]?字([\u4e00-\u9fa5]{1,3})', text):
                if free(mt.start(), mt.end()):
                    add('〔' + mt.group(1) + '〕字' + mt.group(2), ch['no'], text[max(0, mt.start() - 10):mt.end() + 6], 'P2名与字')

            # P3 官职 + 姓名
            for off in OFFICES:
                for mt in re.finditer(off + r'([\u4e00-\u9fa5]{2,3})', text):
                    cand = mt.group(1)
                    if name_ok(cand, known_person, known_place) and free(mt.start(), mt.end()):
                        add(cand, ch['no'], text[max(0, mt.start() - 6):mt.end() + 6], 'P3官职+名')

            # P4 姓+名 + 动词/虚词（放宽集合换召回，靠姓氏表与尾字表压误报）
            for mt in re.finditer(r'([\u4e00-\u9fa5]{2,3})(?:' + VERBS + r')', text):
                cand = mt.group(1)
                for t in TAIL_NOISE:
                    if cand.endswith(t) and len(cand) > 2:
                        cand = cand[:-1]
                if len(cand) > 1 and cand[1] in FUNCTION2:
                    continue
                if name_ok(cand, known_person, known_place) and free(mt.start(), mt.start() + len(cand)):
                    add(cand, ch['no'], text[max(0, mt.start() - 8):mt.end() + 3], 'P4姓名+动词')

            # P5 单称 + 动词（绍曰 / 布曰 / 坚从）→ 用姓字频次回推全名
            for mt in re.finditer(r'(?:^|[，。！？”」；：\s、])([\u4e00-\u9fa5])(?:' + VERBS + r')', text):
                c = mt.group(1)
                if c in STOP_SINGLE:
                    continue
                if any(n.endswith(c) for n in known_person):
                    continue          # 该单称已是建档人物的末字，无需再推
                if not free(mt.start() + 1, mt.start() + 2):
                    continue
                full = recover(c)
                if full:
                    add(full, ch['no'], text[max(0, mt.start() - 8):mt.end() + 3], 'P5单称「%s」回推' % c)
    return hits, ev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--min', type=int, default=1)
    ap.add_argument('--out', default='')
    args = ap.parse_args()

    chs, kp, kl = load_all()
    hits, ev = scan(chs, kp, kl)
    ranked = [(n, c) for n, c in hits.most_common() if c >= args.min]

    print('已扫描 %d 回，已建档人物 %d 名' % (len(chs), len(kp)))
    print('未登录人名候选 %d 个（出现 ≥%d 次）\n' % (len(ranked), args.min))
    print('%-8s %4s  %s' % ('候选', '次数', '首见上下文'))
    print('-' * 92)
    for n, c in ranked[:60]:
        print('%-8s %4d  [第%d回] %s' % (n, c, ev[n][0]['ch'], ev[n][0]['ctx']))

    if args.out:
        out = []
        for n, c in ranked:
            out.append({'candidate': n, 'count': c,
                        'patterns': sorted({e['pat'] for e in ev[n]}),
                        'evidence': ev[n],
                        'confidence': round(min(0.98, 0.35 + 0.1 * min(c, 5) + (0.25 if any('P1' in e['pat'] for e in ev[n]) else 0)
                                               + (0.15 if any('P3' in e['pat'] for e in ev[n]) else 0)), 2)})
        json.dump({'scanned_chapters': [c['no'] for c in chs], 'candidates': out},
                  io.open(os.path.join(ROOT, args.out), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('\n已写出 %s（%d 条）' % (args.out, len(out)))


if __name__ == '__main__':
    main()
