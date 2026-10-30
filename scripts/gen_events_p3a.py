#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P3-A 联动：生成第 61–70 回的 3 组事件 + 2 场战役（data/event_battle_ch061_070.json）。
约束同 gen_events_p2c.py：passage_ids 解析生成；participants/commanders 仅已建档 id。
"""
import json, io, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, 'build')
DATA = os.path.join(ROOT, 'data')

places = {p['id']: p for p in json.load(io.open(os.path.join(BUILD, 'places.json'), encoding='utf-8'))}
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
        raise SystemExit('出处解析失败：第 %d 回找不到关键词「%s」' % (no, kw))
    return pids[(no, hits[0][0])]


def refs(no, kws):
    return [ref(no, kw) for kw in kws]


def check_persons(obj, *id_fields):
    for f in id_fields:
        if f == 'participants':
            ids = [p['person_id'] for p in obj['participants']]
        elif f == 'belligerents':
            ids = [c for b in obj['belligerents'] for c in b['commanders']]
        else:
            ids = obj[f]
        bad = [i for i in ids if i not in person_ids]
        if bad:
            raise SystemExit('%s：未建档人物 %s' % (obj['id'], bad))


PLACE = 'jing_zhou'   # 占位，下面各事件逐一覆盖

events, battles = [], []

# ---- E1 落凤坡之殇（63 回，213） ----
e1 = {
    'id': 'luofengpo_zhishang', 'name': '落凤坡之殇', 'kind': '人物',
    'start_year': 213, 'end_year': 213, 'date_text': '建安十八年（213）',
    'summary': '庞统随刘备攻雒城，于落凤坡中张任伏兵，乱箭死于坡下，号凤雏止于此。',
    'detail': '孔明观天象以书戒备：主将帅宜谨慎。统疑亮归功己之争，力主进兵。备以的卢马与统乘。行至落凤坡，统惊曰：吾道号凤雏，此处名落凤坡，不利吾甚！张任伏兵齐出，乱箭俱发，统死于乱箭之下，年止三十六。备闻之大恸，退守涪关，遣关平请孔明入川。',
    'place_id': 'c_益州_广汉郡_雒',
    'parent_event_id': None,
    'participants': [
        {'person_id': 'pang_tong', 'role_desc': '副军师中郎将，落凤坡中伏而亡'},
        {'person_id': 'liu_bei', 'role_desc': '统帅，以的卢马借统乘，闻讯大恸'},
        {'person_id': 'zhang_ren', 'role_desc': '设伏落凤坡，乱箭射死庞统'},
        {'person_id': 'zhuge_liang', 'role_desc': '观天象驰书戒备，后入川主持'},
    ],
    'passage_ids': refs(63, ['落凤坡', '凤雏', '庞统', '伏兵']),
}
check_persons(e1, 'participants')
events.append(e1)

# ---- E2 + B1 葭萌关之战（65 回，214） ----
b1 = {
    'id': 'jiamengguan_battle', 'name': '葭萌关之战', 'year': 214,
    'date_text': '建安十九年（214）',
    'place_id': 'jia_meng_guan', 'event_id': 'jiamengguan_zhi_zhan',
    'belligerents': [
        {'side': '蜀军（刘备）', 'faction_ids': ['shu'], 'commanders': ['zhang_fei', 'liu_bei', 'wei_yan'],
         'troops_desc': '张飞单搦马超，孔明用反间计策反李恢说降'},
        {'side': '西凉军（马超）', 'faction_ids': ['warlord'], 'commanders': ['ma_chao', 'ma_dai'],
         'troops_desc': '马超助刘璋攻葭萌关，兵败退走'},
    ],
    'result': '两军酣战不分胜负，孔明行反间计，李恢说降马超，超遂归刘备。',
    'casualties_note': '马超军粮尽援绝；蜀军无损大将。',
    'summary': '张飞夜战马超二百余合不分胜负，孔明使反间计，李恢入羌中说降马超，超转攻成都。',
    'detail': '马超投张鲁后请兵攻葭萌关以报刘璋。孔明用计激张飞出战，飞与超自午后战至夜，点添灯火续战二百余合不分胜负。备叹：真虎将也！孔明知鲁肃多谋、张鲁多疑，行反间计使张鲁疑超，进退维谷；李恢自请入中说超，陈利害，超遂倒戈，引兵助备围成都。',
    'front_line': [
        {'time': 214, 'time_seq': 1, 'kind': '驰援', 'label': '魏延先至', 'desc': '魏延先率五百骑哨探，中马岱暗箭，岱误杀韩遂部将反为延所诱退。', 'lng': 105.64, 'lat': 32.32},
        {'time': 214, 'time_seq': 2, 'kind': '单挑', 'label': '飞战马超', 'desc': '张飞与马超自午后酣战至夜，二百余合不分胜负。', 'lng': 105.64, 'lat': 32.32},
        {'time': 214, 'time_seq': 3, 'kind': '夜战', 'label': '添灯再战', 'desc': '备怜飞，飞不肯休，两军添灯夜战又数十合，各有防备。', 'lng': 105.7, 'lat': 32.36},
        {'time': 214, 'time_seq': 4, 'kind': '归降', 'label': '李恢说超', 'desc': '孔明反间使张鲁疑超，李恢入中说降，马超归刘。', 'lng': 105.5, 'lat': 32.2},
    ],
}
check_persons(b1, 'belligerents')
battles.append(b1)
e2 = {
    'id': 'jiamengguan_zhi_zhan', 'name': '葭萌关之战', 'kind': '征伐',
    'start_year': 214, 'end_year': 214, 'date_text': '建安十九年（214）',
    'summary': '马超奉张鲁命攻葭萌关，与张飞昼夜酣战不分胜负；孔明反间，李恢说降马超。',
    'detail': '详见战役「葭萌关之战」。马超归刘后引兵攻成都，刘璋见大势已去，遂出降，备得益州。',
    'place_id': 'jia_meng_guan', 'parent_event_id': None,
    'participants': [
        {'person_id': 'ma_chao', 'role_desc': '攻葭萌关主将，战张飞不分胜负，终降刘'},
        {'person_id': 'zhang_fei', 'role_desc': '守关出战，夜战马超'},
        {'person_id': 'liu_bei', 'role_desc': '坐镇关内，叹飞与超皆虎将'},
        {'person_id': 'zhuge_liang', 'role_desc': '行反间计，遣李恢说降'},
        {'person_id': 'ma_dai', 'role_desc': '随超攻关，暗箭伤魏延'},
        {'person_id': 'wei_yan', 'role_desc': '先锋先至，中马岱之箭'},
    ],
    'passage_ids': refs(65, ['葭萌关', '马超', '张飞', '李恢']),
    'battle_ids': ['jiamengguan_battle'],
}
check_persons(e2, 'participants')
events.append(e2)

# ---- E3 + B2 逍遥津之战（67 回，215） ----
b2 = {
    'id': 'xiaoyaojin_battle', 'name': '逍遥津之战', 'year': 215,
    'date_text': '建安二十年（215）',
    'place_id': 'he_fei', 'event_id': 'xiaoyaojin_zhi_zhan',
    'belligerents': [
        {'side': '吴军', 'faction_ids': ['wu'], 'commanders': ['sun_quan', 'ling_tong', 'gan_ning'],
         'troops_desc': '孙权亲率十万众围合肥'},
        {'side': '曹军', 'faction_ids': ['wei'], 'commanders': ['zhang_liao', 'li_dian', 'yue_jin'],
         'troops_desc': '张辽李典乐进七千余守合肥'},
    ],
    'result': '张辽八百勇士突阵，权几被擒，凌统亲卫尽殁护主得脱；吴军丧胆而退。',
    'casualties_note': '凌统三百亲卫尽没；吴军夺气。',
    'summary': '曹操密函教辽破敌：辽夜选八百壮士突入权麾下，权仓皇奔走，赖凌统死战得脱，吴人谈辽色变。',
    'detail': '操征汉中，密函与辽典：若孙权至，张李出战、乐守护军。权十万众至，辽夜募八百人椎牛飨士，平明突入权阵，大呼自报名号，直取权，权奔高冢持长戟自守，辽叱权下战，权不敢动。辽突围复入，权锐气顿挫，围城十余日不下而退。辽觇权军退，亲率步骑追击于逍遥津北，甘宁厉声奋击，凌统率亲近三百陷围尽殁，统身被数创救权得渡。权乘骏马上津桥，桥南已拆丈余，谷利鞭马助势，权得飞渡。自此江东小儿闻辽名夜不敢啼。',
    'front_line': [
        {'time': 215, 'time_seq': 1, 'kind': '围城', 'label': '权围合肥', 'desc': '孙权十万众围合肥，守军七千。', 'lng': 117.23, 'lat': 31.82},
        {'time': 215, 'time_seq': 2, 'kind': '突袭', 'label': '辽八百破阵', 'desc': '张辽夜募八百人，平明突入权麾，权奔高冢自守。', 'lng': 117.3, 'lat': 31.88},
        {'time': 215, 'time_seq': 3, 'kind': '追击', 'label': '津北截击', 'desc': '权退兵，辽觇之率骑追击于逍遥津北。', 'lng': 117.27, 'lat': 31.86},
        {'time': 215, 'time_seq': 4, 'kind': '死战', 'label': '凌统殁卫', 'desc': '凌统三百亲卫陷围尽殁，身被数创护权得脱。', 'lng': 117.27, 'lat': 31.86},
        {'time': 215, 'time_seq': 5, 'kind': '结局', 'label': '权飞渡津', 'desc': '谷利鞭马助势，权飞渡断桥而还，吴军丧胆。', 'lng': 117.25, 'lat': 31.84},
    ],
}
check_persons(b2, 'belligerents')
battles.append(b2)
e3 = {
    'id': 'xiaoyaojin_zhi_zhan', 'name': '逍遥津之战', 'kind': '征伐',
    'start_year': 215, 'end_year': 215, 'date_text': '建安二十年（215）',
    'summary': '曹操西征汉中，张辽以八百人破孙权十万之众于合肥，威震逍遥津。',
    'detail': '详见战役「逍遥津之战」。此战之后魏置扬州重兵于合肥，吴终曹操之世不能逾雷池一步。',
    'place_id': 'he_fei', 'parent_event_id': None,
    'participants': [
        {'person_id': 'zhang_liao', 'role_desc': '八百勇士突阵，威震逍遥津'},
        {'person_id': 'sun_quan', 'role_desc': '十万众围合肥，几被擒，飞渡断桥得脱'},
        {'person_id': 'ling_tong', 'role_desc': '率三百亲卫陷围死战，身被数创救主'},
        {'person_id': 'gan_ning', 'role_desc': '厉声奋击引弓射敌，助权突围'},
        {'person_id': 'li_dian', 'role_desc': '随辽出城突阵，护辽突围复入'},
        {'person_id': 'yue_jin', 'role_desc': '守护军拒守合肥城'},
    ],
    'passage_ids': refs(67, ['逍遥津', '张辽', '凌统', '甘宁']),
    'battle_ids': ['xiaoyaojin_battle'],
}
check_persons(e3, 'participants')
events.append(e3)

# ---- E4 单刀赴会（66 回，215） ----
e4 = {
    'id': 'dandao_fuhui', 'name': '单刀赴会', 'kind': '外交',
    'start_year': 215, 'end_year': 215, 'date_text': '建安二十年（215）',
    'summary': '鲁肃邀关羽赴陆口之会索还荆州，云长单刀赴会，谈笑间挟鲁肃脱身，荆州终不还。',
    'detail': '备得益州，权遣诸葛瑾索荆州，备诡称俟取凉州相还。权怒，令鲁肃屯兵巴丘以图荆州。肃设宴于陆口邀云长，伏刀斧手于帐后。云长慨然单刀（周仓捧刀）赴会，酒至半酣，肃索荆州，云长曰：此国家之事，筵间不必论之。佯醉挽肃至江边，周仓阶下厉声呼，云长执肃手曰：今日与吾兄饮宴，休提荆州！肃魂不附体，被云长牵至江边登舟而去。史载此会为肃单刀赴会责羽，演义反其意而写之，注于卡片史异注。',
    'place_id': 'lu_kou', 'parent_event_id': None,
    'participants': [
        {'person_id': 'guan_yu', 'role_desc': '单刀赴会，佯醉执鲁肃手脱身'},
        {'person_id': 'lu_su', 'role_desc': '设宴索荆州，反为云长所挟'},
        {'person_id': 'zhou_cang', 'role_desc': '捧刀随侍，阶下厉声呼应'},
        {'person_id': 'gan_ning', 'role_desc': '肃所部将领，江边设伏（演义）'},
    ],
    'passage_ids': refs(66, ['单刀', '鲁肃', '荆州']),
}
check_persons(e4, 'participants')
events.append(e4)

out = {'comment': 'P3-A（2026-10-29）：第 61–70 回的 3 组事件 + 2 场战役。passage_ids 由本脚本解析生成，禁止手改。',
       'events': events, 'battles': battles}
p = os.path.join(DATA, 'event_battle_ch061_070.json')
io.open(p, 'w', encoding='utf-8').write(json.dumps(out, ensure_ascii=False, indent=2))
print('写出 %s：事件 %d，战役 %d' % (p, len(events), len(battles)))
