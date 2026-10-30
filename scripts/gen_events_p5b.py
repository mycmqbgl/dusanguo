#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P5-B：补 3 组空白回事件（94 擒孟达 / 102 木牛流马 / 105 魏延之死）。"""
import json, io, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, 'build')
DATA = os.path.join(ROOT, 'data')

passages, pids = {}, {}
for f in sorted(os.listdir(os.path.join(BUILD, 'chapters'))):
    d = json.load(io.open(os.path.join(BUILD, 'chapters', f), encoding='utf-8'))
    no = d['chapter']['no']
    for p in d['passages']:
        passages[(no, p['seq'])] = p['text']
        pids[(no, p['seq'])] = p['id']
person_ids = set()
for f in os.listdir(DATA):
    if f.startswith('persons_') and f.endswith('.json'):
        for p in json.load(io.open(os.path.join(DATA, f), encoding='utf-8'))['persons']:
            person_ids.add(p['id'])


def ref(no, kw):
    hits = [(s, t) for (n, s), t in passages.items() if n == no and kw in t]
    if not hits:
        raise SystemExit('第 %d 回找不到「%s」' % (no, kw))
    return pids[(no, hits[0][0])]


def check(obj):
    bad = [p['person_id'] for p in obj['participants'] if p['person_id'] not in person_ids]
    if bad:
        raise SystemExit('%s 未建档: %s' % (obj['id'], bad))


events = [
    {
        'id': 'mengda_zhifubing', 'name': '司马懿克日擒孟达', 'kind': '征伐',
        'start_year': 228, 'end_year': 228, 'date_text': '太和二年（228）',
        'summary': '孟达谋归蜀，司马懿未奏先斩、八日急行军，克日破新城，达死乱军。',
        'detail': '孟达降魏复通蜀，约孔明同时并举。亮以书戒其慎防司马懿，达笑懿非急者。懿闻讯，一面发书稳达、一面大军倍道兼行，八日而至新城，昼夜急攻。达外应内绝，申仪泄其谋，李辅开门，达死于乱军。亮闻之叹：大事去矣。此役为亮一伐之先声受挫。',
        'place_id': 'c_益州_新城郡_房陵',
        'parent_event_id': None,
        'participants': [
            {'person_id': 'sim_yi', 'role_desc': '未奏先斩，八日擒孟达'},
            {'person_id': 'meng_da', 'role_desc': '谋叛事泄，困守新城而死'},
            {'person_id': 'zhuge_liang', 'role_desc': '约达并举，书戒其慎'},
        ],
        'passage_ids': [ref(94, '孟达降魏'), ref(94, '孟达若死'), ref(94, '司马懿'), ref(94, '新城')],
    },
    {
        'id': 'muliu_numa', 'name': '诸葛亮造木牛流马', 'kind': '发明',
        'start_year': 234, 'end_year': 234, 'date_text': '建兴十二年（234）',
        'summary': '孔明造木牛流马转运粮草，懿仿造反中计，粮为蜀军所劫。',
        'detail': '剑阁道险，粮运不继，亮依《造木牛流马法》造之：木牛腹中有机，流马前后有轴，搬运粮草如活物。懿使人仿造百有余只，反为蜀兵夺寨劫粮——夺其木牛，扭转其舌，牛不能行，魏军尽弃粮草。六出祁山之役，蜀军赖此不困于粮。',
        'place_id': 'jian_ge',
        'parent_event_id': None,
        'participants': [
            {'person_id': 'zhuge_liang', 'role_desc': '造木牛流马，转粮如活物'},
            {'person_id': 'sim_yi', 'role_desc': '仿造反中计，粮草尽失'},
        ],
        'passage_ids': [ref(102, '木牛'), ref(102, '流马'), ref(102, '剑阁')],
    },
    {
        'id': 'weiyan_zhisi', 'name': '魏延之死', 'kind': '人物',
        'start_year': 234, 'end_year': 234, 'date_text': '建兴十二年（234）',
        'summary': '武侯遗计，杨仪依锦囊激马岱，魏延「谁敢杀我」三呼而斩。',
        'detail': '亮卒于五丈原，遗命退军，魏延不服断后，烧绝栈道、拥兵南归，与杨仪各表称反。仪依亮锦囊之计，于阵前问延：敢三声谁敢杀我？延方呼毕，马岱应声出刀，斩于马下——盖亮先已密嘱岱也。夷延三族。演义写延脑后反骨，实为亮死后蜀将内讧之首祸；史载延本意夺权诛仪，非降魏。',
        'place_id': 'wu_zhang_yuan',
        'parent_event_id': 'wu_zhang_yuan_zhi_zhan',
        'participants': [
            {'person_id': 'wei_yan', 'role_desc': '不服断后，三呼「谁敢杀我」被斩'},
            {'person_id': 'yang_yi', 'role_desc': '依锦囊激延，夷其三族'},
            {'person_id': 'ma_dai', 'role_desc': '受亮密嘱，阵前出刀斩延'},
            {'person_id': 'jiang_wei', 'role_desc': '拥后军断后退兵'},
        ],
        'passage_ids': [ref(105, '魏延'), ref(105, '锦囊'), ref(105, '谁敢杀我') if any('谁敢杀我' in t for t in passages.values()) else ref(105, '马岱'), ref(105, '杨仪')],
    },
]
for e in events:
    check(e)
out = {'comment': 'P5-B（2026-10-29）：补空白回 3 组事件（94/102/105）。passage_ids 解析生成，禁止手改。',
       'events': events, 'battles': []}
p = os.path.join(DATA, 'event_battle_ch_p5b.json')
io.open(p, 'w', encoding='utf-8').write(json.dumps(out, ensure_ascii=False, indent=2))
print('写出 %s：事件 %d' % (p, len(events)))
