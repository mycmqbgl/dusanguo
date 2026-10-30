#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第三批：新增「客君」身份 + 清理同阵营重叠时间片。

问题（用户 2026-10-30 提出）：
  1. 刘禅在曹魏挂「亲族」——他不是曹氏帝系，只是魏所封的安乐公（蜀汉后主），
     所谓「蜀室之亲」是对曹魏而言的「客」，不是亲族。
  2. 曹奂在晋挂「亲族」、刘协在魏挂「其他」——同一类问题，归类标准不统一。
  3. 曹芳（254–274）、曹奂（258–260）在曹魏同时有「亲族」段和「其他」段，
     按年筛选时一个人被数两次，违反「某年只属于一个身份」的既有要求。

定案（已与用户确认）：
  - 新增身份「客君」：非本朝帝系、以前朝/他国君主之身受本朝封爵者。
    刘协→魏·客君；刘禅→魏·客君、晋·客君；曹奂→晋·客君。
  - 同阵营同一时点只允许一个身份：删除冗余的「其他」段。
  - 孙策：修正吴阵营时间片的 role 与区间（原 追谥 229–280，
    改为 亲族 [229, 280]，title 写明「孙权之兄，追谥长沙桓王」），
    与 entity-schema.json 的既有决策一致——王而非帝者不入「追谥」。
"""
import json, glob, os, io

ROOT = '/workspace/读三国-project'
DATA = os.path.join(ROOT, 'data')


def each_person():
    for f in sorted(glob.glob(os.path.join(DATA, 'persons_*.json'))):
        doc = json.load(io.open(f, encoding='utf-8'))
        for i, p in enumerate(doc['persons']):
            yield f, doc, i, p


def save(f, doc):
    json.dump(doc, io.open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


TEN = {}


def T(pid, lst):
    TEN[pid] = lst


# ---------- 刘协：魏·其他 → 魏·客君 ----------
T('liu_xie', [
    dict(faction_id='han', role='亲族', start_year=181, end_year=189,
         title='灵帝次子，陈留王',
         basis='第2回：皇子协养于董太后宫中，封陈留王。为灵帝次子。',
         confidence=0.95, review_status='reviewed'),
    dict(faction_id='han', role='皇帝', start_year=189, end_year=220,
         title='汉献帝',
         basis='第3回：董卓废少帝，立陈留王协为帝，是为献帝。',
         confidence=0.95, review_status='reviewed'),
    dict(faction_id='wei', role='客君', start_year=220, end_year=234,
         title='山阳公（汉献帝降封）',
         basis='第80回：丕降旨封帝为山阳公。刘协本是汉朝皇帝，禅位后受魏封为山阳公，'
               '为魏之宾而非魏之宗亲，故归客君；卒于魏青龙二年（234），未及晋。',
         confidence=0.95, review_status='reviewed'),
])

# ---------- 刘禅：魏·亲族 → 魏·客君；晋·亲族 → 晋·客君 ----------
T('liu_shan', [
    dict(faction_id='shu', role='皇帝', start_year=223, end_year=263, title='蜀汉后主',
         basis='第85回：先主崩，后主刘禅即位，年十七。',
         confidence=0.95, review_status='reviewed'),
    dict(faction_id='wei', role='客君', start_year=263, end_year=266,
         title='安乐公（蜀汉后主降封）',
         basis='第118回：后主降魏，魏封为安乐公。刘禅是蜀汉皇帝，降后受魏封，'
               '为魏之宾而非曹氏帝系之亲，故归客君。',
         confidence=0.9, review_status='reviewed'),
    dict(faction_id='jin', role='客君', start_year=266, end_year=271,
         title='安乐公（晋袭封）',
         basis='晋受魏禅，安乐公爵如故，至 271 年刘禅卒。仍为晋之宾，非司马氏之亲。',
         confidence=0.85, review_status='reviewed'),
])

# ---------- 曹奂：晋·亲族 → 晋·客君；删除冗余的魏·其他 ----------
T('cao_huan', [
    dict(faction_id='wei', role='亲族', start_year=258, end_year=260,
         title='曹操之孙，常道乡公（燕王曹宇之子）',
         basis='第114回：司马昭立曹奂为帝，时封常道乡公。奂为燕王曹宇之子，魏室之亲。',
         confidence=0.9, review_status='reviewed'),
    dict(faction_id='wei', role='皇帝', start_year=260, end_year=265, title='魏元帝',
         basis='第114回：立高贵乡公曹髦……髦死，立常道乡公曹奂为帝。',
         confidence=0.95, review_status='reviewed'),
    dict(faction_id='jin', role='客君', start_year=265, end_year=302,
         title='陈留王（魏元帝禅位后受晋封）',
         basis='第119回：晋帝司马炎封魏主曹奂为陈留王。曹奂本是魏帝，禅位后受晋封，'
               '为晋之宾而非司马氏之亲，故归客君。',
         confidence=0.9, review_status='reviewed'),
])

# ---------- 曹芳：删除冗余的魏·其他（若有） ----------
# 现为 魏·皇帝 + 魏·亲族 两段，已无「其他」段，仅做断言

# ---------- 孙策：吴·追谥 → 吴·亲族 ----------
T('sun_ce', [
    dict(faction_id='warlord', role='武将', start_year=191, end_year=195,
         title='孙坚长子，随父征战',
         basis='第7回：孙策随父孙坚讨黄巾、讨董卓，年方十七，骁勇过人。',
         confidence=0.9, review_status='reviewed'),
    dict(faction_id='warlord', role='君主', start_year=195, end_year=200,
         title='讨逆将军、会稽太守、吴侯',
         basis='第15回：孙策以玉玺质于袁术借兵渡江，数年尽有江东六郡。',
         confidence=0.95, review_status='reviewed'),
    dict(faction_id='wu', role='亲族', start_year=229, end_year=280,
         title='孙权之兄，追谥长沙桓王',
         basis='孙权称帝后追封兄孙策为长沙桓王。谥王不谥帝，故不入「追谥」；'
               '策为孙权之兄、吴国奠基者，按 entity-schema 既有决策归吴·亲族。',
         confidence=0.95, review_status='reviewed'),
])

# ---------- 应用 tenure 替换 ----------
applied = set()
for f, doc, i, p in each_person():
    if p['id'] in TEN:
        p['tenure'] = TEN[p['id']]
        doc['persons'][i] = p
        save(f, doc)
        applied.add(p['id'])

print('tenure 已替换', sorted(applied))

# ---------- 同阵营同一时点重叠检查 ----------
# 口径：相邻两片共享端点年（前片 end == 后片 start）属正常交接，只扣 1 年；
# 若重叠年数 > 1，则同一年里此人有两个身份，违反「某年只属于一个身份」。
def ovl_years(x, y):
    lo = max(x['start_year'], y['start_year'])
    hi = min(x['end_year'], y['end_year'])
    return max(0, hi - lo + 1)


bad = []
for f, doc, i, p in each_person():
    by = {}
    for t in p['tenure']:
        by.setdefault(t['faction_id'], []).append(t)
    for fac, lst in by.items():
        for a in range(len(lst)):
            for b in range(a + 1, len(lst)):
                x, y = lst[a], lst[b]
                n = ovl_years(x, y)
                if n <= 1:
                    continue
                bad.append((p['id'], p['name'], fac, x['role'], y['role'],
                            f"{x['start_year']}-{x['end_year']}",
                            f"{y['start_year']}-{y['end_year']}", n))
print('同阵营实质重叠（>1年）', len(bad))
for b in bad:
    print('  ', b)
