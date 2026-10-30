#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P5 联动：生成 9 组事件 + 1 场战役（data/event_battle_ch_p5.json）。
约束同 gen_events_p3a.py：passage_ids 由 build/chapters 解析生成；participants/commanders 仅已建档 id。
注：姜维洮西破王经一役在毛本第 110 回（非 109），已 grep 原文核实。
"""
import json, io, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, 'build')
DATA = os.path.join(ROOT, 'data')

places = {p['id']: p for p in (json.load(io.open(os.path.join(BUILD, 'places.json'), encoding='utf-8'))['places']
          if isinstance(json.load(io.open(os.path.join(BUILD, 'places.json'), encoding='utf-8')), dict) and 'places' in json.load(io.open(os.path.join(BUILD, 'places.json'), encoding='utf-8')) else json.load(io.open(os.path.join(BUILD, 'places.json'), encoding='utf-8')))}
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


def check_places(obj):
    pid = obj['place_id']
    if pid not in places:
        raise SystemExit('%s：地点不存在 %s' % (obj['id'], pid))


events, battles = [], []

# ---- E1 赵云截江夺阿斗（61 回，211–212） ----
e1 = {
    'id': 'zhao_yun_jiejiang', 'name': '赵云截江夺阿斗', 'kind': '征伐',
    'start_year': 211, 'end_year': 212, 'date_text': '建安十六年（211，原文系年）',
    'summary': '孙夫人听吴国太病笃之诈，携阿斗登舟归吴；赵云弃马截江夺回阿斗，张飞随后到，杀周善，阿斗得还。',
    'detail': '孙权闻刘备西征，用张昭之计遣周善以国太病笃为名接孙夫人回吴，嘱其带阿斗去以为质。夫人不疑，携阿斗登舟。赵云巡哨知觉，沿江赶至，弃马乘渔舟跳上吴船，夺抱阿斗欲下船而不得，靠江岸泊住。张飞乘船赶到，杀周善，遂同截阿斗归。夫人独自回吴，此后吴蜀因而生隙。',
    'place_id': 'jiang_ling', 'parent_event_id': None,
    'participants': [
        {'person_id': 'zhao_yun', 'role_desc': '巡哨知觉，弃马截江，独抱阿斗'},
        {'person_id': 'zhang_fei', 'role_desc': '率船赶到，杀周善，同截阿斗'},
        {'person_id': 'sun_quan', 'role_desc': '听张昭之计遣周善赚夫人携阿斗归吴'},
    ],
    'passage_ids': refs(61, ['截江', '阿斗', '孙夫人', '周善']),
}
check_persons(e1, 'participants'); check_places(e1)
events.append(e1)

# ---- E2 左慈掷杯戏曹操（68 回，216） ----
e2 = {
    'id': 'zuoci_zhibei', 'name': '左慈掷杯戏曹操', 'kind': '神异',
    'start_year': 216, 'end_year': 216, 'date_text': '建安二十一年（216）',
    'summary': '左慈于宴间掷杯化鹤飞去，化羊遁走，操捕之不得，惊而成疾。',
    'detail': '左慈显异于王屋山取柑、进柑于操，操欲杀之，慈掷杯于空，杯化白鹤绕殿而飞；寻慈不见，遍城捕之。后有牧羊小儿见慈化羊，操令捕羊，群羊皆跪作人语，刀斧不能施。操自是惊惧成疾。（左慈未建卡，参与者暂记曹操。）',
    'place_id': 'xu_du', 'parent_event_id': None,
    'participants': [
        {'person_id': 'cao_cao', 'role_desc': '宴中受左慈戏弄，惊惧成疾（左慈未建卡）'},
    ],
    'passage_ids': refs(68, ['掷杯', '左慈']),
}
check_persons(e2, 'participants'); check_places(e2)
events.append(e2)

# ---- E3 管辂论命（69 回，218） ----
e3 = {
    'id': 'guanlu_lunming', 'name': '管辂论命', 'kind': '神异',
    'start_year': 218, 'end_year': 218, 'date_text': '建安二十三年（218）',
    'summary': '平原神卜管辂应召为曹操卜东吴、西蜀吉凶，预言许都火灾与诸将死期，后皆一一应验。',
    'detail': '操感左慈之惊成疾，方士荐平原管辂。辂善卜，操使卜东吴、西蜀二处休咎，辂各断之，且言来春许都必有火灾，请曹丕谨慎。后果如所言。操又问诸将寿算，辂皆隐语答之，其后遂应；操叹天机不可泄，欲以官爵留辂，辂固辞不受而去。',
    'place_id': 'xu_du', 'parent_event_id': None,
    'participants': [
        {'person_id': 'guan_lu', 'role_desc': '神卜应召，断吴蜀吉凶、许都火灾，预言皆验'},
        {'person_id': 'cao_cao', 'role_desc': '因疾召辂问卜，叹其神异'},
    ],
    'passage_ids': refs(69, ['管辂', '东吴', '西蜀']),
}
check_persons(e3, 'participants'); check_places(e3)
events.append(e3)

# ---- E4 徐盛火攻破曹丕（86 回，224） ----
e4 = {
    'id': 'xu_sheng_huogong', 'name': '徐盛火攻破曹丕', 'kind': '征伐',
    'start_year': 224, 'end_year': 224, 'date_text': '黄武三年（224）',
    'summary': '曹丕大举伐吴，徐盛一夜筑假城疑敌，沿江以芦苇缚草为人；曹丕被徐盛火攻烧舟，败退而还。',
    'detail': '曹丕起大兵三十余万伐吴，徐盛建议自建业起筑围墙，一夜而成假城，又沿江结芦苇缚草为人、尽衣旌旗。丕临江见之大惊疑惧。徐盛乘风纵火，火船直入魏军舟阵，曹丕龙舟被围，赖死士救护得脱，魏军大败而退。陆逊在后方策应。（疑城即假城，原文作「一夜」「假城」。）',
    'place_id': 'jian_ye', 'parent_event_id': None,
    'participants': [
        {'person_id': 'xu_sheng', 'role_desc': '一夜筑假城、缚草为兵疑敌，乘风纵火破魏'},
        {'person_id': 'cao_pi', 'role_desc': '亲统大军伐吴，见疑城而惧，龙舟遭火攻败退'},
        {'person_id': 'lu_xun', 'role_desc': '在后方督军策应'},
    ],
    'passage_ids': refs(86, ['假城', '徐盛', '曹丕', '龙舟']),
}
check_persons(e4, 'participants'); check_places(e4)
events.append(e4)

# ---- E5 孙权称帝（98 回，229） ----
e5 = {
    'id': 'sun_quan_chengdi', 'name': '孙权称帝', 'kind': '典制',
    'start_year': 229, 'end_year': 229, 'date_text': '黄龙元年（229）',
    'summary': '孙权于武昌郊天即皇帝位，迁都建业；蜀遣使贺，吴蜀约中分天下。',
    'detail': '孙权筑坛登坛郊天，即皇帝位，改元黄龙，迁都建业。陆逊辅政。诸葛亮遣使赴吴称贺，吴蜀立盟，约中分天下：豫、青、徐、幽属吴，兖、冀、并、凉属蜀，司州以函谷关为界。三国鼎立之局至此名实俱全。',
    'place_id': 'jian_ye', 'parent_event_id': None,
    'participants': [
        {'person_id': 'sun_quan', 'role_desc': '郊天即皇帝位，改元黄龙，迁都建业'},
        {'person_id': 'lu_xun', 'role_desc': '辅政重臣'},
        {'person_id': 'zhuge_liang', 'role_desc': '遣使赴吴称贺，赞成吴蜀中分天下之盟'},
    ],
    'passage_ids': refs(98, ['即皇帝位', '筑坛', '分天下', '孙权']),
}
check_persons(e5, 'participants'); check_places(e5)
events.append(e5)

# ---- E6 孙峻诛诸葛恪（108 回，253） ----
e6 = {
    'id': 'sun_jun_zhu_zhugeke', 'name': '孙峻诛诸葛恪', 'kind': '政变',
    'start_year': 253, 'end_year': 253, 'date_text': '建兴二年（253）',
    'summary': '诸葛恪新城大败而归，反更骄横专权，孙峻与吴主孙亮设计，宴间杀之，夷其三族。',
    'detail': '诸葛恪围新城不克，士卒死伤大半而退，归后不自咎，反杀害忠谏、更换宿卫、骄横日甚。孙峻与吴主孙亮密谋，置酒设宴，伏武士于帷内，恪入席，酒行数巡，峻掷杯为号，武士出而斩恪，割首张示，夷三族。吴政遂归于峻。',
    'place_id': 'jian_ye', 'parent_event_id': None,
    'participants': [
        {'person_id': 'zhuge_ke', 'role_desc': '新城兵败归而骄横，宴间被诛，夷三族'},
        {'person_id': 'sun_jun', 'role_desc': '与吴主密谋，宴间掷杯为号伏杀诸葛恪'},
        {'person_id': 'sun_liang', 'role_desc': '吴主，与孙峻定计诛恪'},
    ],
    'passage_ids': refs(108, ['诸葛恪', '孙峻', '新城']),
}
check_persons(e6, 'participants'); check_places(e6)
events.append(e6)

# ---- E7 丁奉定计斩孙綝（113 回，258） ----
e7 = {
    'id': 'ding_feng_zhan_sunlin', 'name': '丁奉定计斩孙綝', 'kind': '政变',
    'start_year': 258, 'end_year': 258, 'date_text': '永安元年（258）',
    'summary': '孙綝专权废亮立休；孙休与丁奉、张布设计，腊日以祭祀为名缚斩孙綝。',
    'detail': '孙綝骄横专政，废孙亮为会稽王，迎立孙休。休阳示恩宠而阴与丁奉、张布谋。丁奉曰：欲除綝，宜以腊日会为名。至腊日，綝托疾不赴，被强请入宫，武士齐出缚之，休历数其罪，斩之，夷三族。吴政始归孙休。',
    'place_id': 'jian_ye', 'parent_event_id': None,
    'participants': [
        {'person_id': 'sun_xiu', 'role_desc': '吴景帝，阳示恩宠阴与定计，历数綝罪而斩之'},
        {'person_id': 'ding_feng', 'role_desc': '定腊日之计，伏兵缚斩孙綝'},
        {'person_id': 'sun_chen', 'role_desc': '专权废立，腊日被缚斩，夷三族'},
    ],
    'passage_ids': refs(113, ['腊日', '丁奉', '孙綝', '张布']),
}
check_persons(e7, 'participants'); check_places(e7)
events.append(e7)

# ---- E8 姜维屯田避祸（115–116 回，258–262） ----
e8 = {
    'id': 'jiangwei_tuntian_bihu', 'name': '姜维屯田避祸', 'kind': '谋略',
    'start_year': 258, 'end_year': 262, 'date_text': '景耀元年至五年间（258–262）',
    'summary': '姜维屡遭黄皓谗害，听郤正之策求沓中屯田以避祸，兼图再举，遂成汉中空虚之局。',
    'detail': '姜维北伐屡为宦官黄皓所谗，刘禅听信黄皓，维惧诛，不敢归成都。郤正献策：请沓中屯田，可避祸，亦可就中练兵积粮以图再举。维表请屯田沓中，刘禅允之。此后魏人闻蜀兵在沓中，遂定伐蜀之策；维请遣兵守阴平桥头，黄皓匿其表，汉中遂虚。',
    'place_id': 'cheng_du', 'parent_event_id': None,
    'participants': [
        {'person_id': 'jiang_wei', 'role_desc': '惧黄皓之谗，求屯田沓中以避祸兼图再举'},
        {'person_id': 'liu_shan', 'role_desc': '听信黄皓，准维屯田沓中'},
    ],
    'passage_ids': refs(115, ['屯田', '沓中', '黄皓']) + refs(116, ['沓中', '黄皓']),
}
check_persons(e8, 'participants'); check_places(e8)
events.append(e8)

# ---- E9 + B1 洮西大捷（110 回，255） ----
b1 = {
    'id': 'taoxi_battle', 'name': '洮西之战', 'year': 255,
    'date_text': '正元二年（255）',
    'place_id': 'c_凉州_陇西郡_狄道', 'event_id': 'taoxi_dajie',
    'belligerents': [
        {'side': '蜀军', 'faction_ids': ['shu'], 'commanders': ['jiang_wei', 'xiahou_ba'],
         'troops_desc': '姜维起兵二十万出阳平关伐魏，夏侯霸为参谋'},
        {'side': '魏军', 'faction_ids': ['wei'], 'commanders': ['wang_jing', 'chen_tai', 'deng_ai', 'guo_huai'],
         'troops_desc': '王经统雍凉兵出狄道迎敌；陈泰、郭淮方面策应；邓艾继起拒维'},
    ],
    'result': '王经背水而战大败，死伤数万，残部退保狄道；姜维进围狄道，陈泰驰援解围，维粮尽而退，邓艾继起拒之。',
    'casualties_note': '魏军死伤数万，王经部众溺于洮水者不计其数；蜀军亦因顿兵坚城、粮尽而退。',
    'summary': '姜维洮西大破王经，经众数万溺于洮水，退保狄道；维围之，陈泰驰援解围，邓艾继起拒维。',
    'detail': '姜维起兵二十万出阳平关，与夏侯霸议取陇西。魏雍州刺史王经自恃兵多，背洮水而阵，维令夏侯霸、诸军两翼夹击，魏兵大溃，争渡洮水溺死者无数，经残众万人退保狄道。维乘胜围狄道。陈泰星夜驰援，扬声截维归路，维粮尽解围退屯钟提。魏以邓艾继起拒维，洮西之败震动关陇。',
    'front_line': [
        {'time': 255, 'time_seq': 1, 'kind': '进军', 'label': '维出阳平关', 'desc': '姜维起兵二十万出阳平关伐魏，与夏侯霸议取陇西。', 'lng': 103.21, 'lat': 35.65},
        {'time': 255, 'time_seq': 2, 'kind': '会战', 'label': '洮西大战', 'desc': '王经背洮水而阵，蜀军两翼夹击，魏兵大溃，溺死于洮水者数万。', 'lng': 103.88, 'lat': 35.38},
        {'time': 255, 'time_seq': 3, 'kind': '围城', 'label': '围狄道', 'desc': '王经残部退保狄道，姜维乘胜进围。', 'lng': 103.88, 'lat': 35.38},
        {'time': 255, 'time_seq': 4, 'kind': '解围', 'label': '陈泰驰援', 'desc': '陈泰星夜驰援，扬声截维归路，维粮尽解围而退。', 'lng': 103.83, 'lat': 35.33},
        {'time': 255, 'time_seq': 5, 'kind': '拒守', 'label': '邓艾继起', 'desc': '魏以邓艾拒维，维退屯钟提，洮西之败震动关陇。', 'lng': 103.9, 'lat': 35.45},
    ],
}
check_persons(b1, 'belligerents'); check_places(b1)
battles.append(b1)
e9 = {
    'id': 'taoxi_dajie', 'name': '洮西大捷', 'kind': '征伐',
    'start_year': 255, 'end_year': 255, 'date_text': '正元二年（255）',
    'summary': '姜维洮西大破王经，经众数万溺于洮水；乘胜围狄道，陈泰解围，邓艾继起。',
    'detail': '详见战役「洮西之战」。此役蜀军斩获空前，魏雍凉震动；然顿兵狄道不下，粮尽而退，未能扩战果。',
    'place_id': 'c_凉州_陇西郡_狄道', 'parent_event_id': None,
    'participants': [
        {'person_id': 'jiang_wei', 'role_desc': '统军二十万伐魏，洮西大破王经，围狄道'},
        {'person_id': 'xiahou_ba', 'role_desc': '参谋军事，献取陇西之策'},
        {'person_id': 'wang_jing', 'role_desc': '背水迎战大败，众溺洮水，退保狄道'},
        {'person_id': 'chen_tai', 'role_desc': '星夜驰援，解狄道之围'},
        {'person_id': 'deng_ai', 'role_desc': '继起拒维，分兵守要'},
        {'person_id': 'guo_huai', 'role_desc': '雍凉方面统帅，策应狄道'},
    ],
    'passage_ids': refs(110, ['洮水', '王经', '陈泰', '邓艾']),
    'battle_ids': ['taoxi_battle'],
}
check_persons(e9, 'participants'); check_places(e9)
events.append(e9)

out = {'comment': 'P5（2026-10-29）：9 组事件 + 1 场战役。passage_ids 由本脚本解析生成，禁止手改。洮西之战在毛本第 110 回，已按原文核实。',
       'events': events, 'battles': battles}
p = os.path.join(DATA, 'event_battle_ch_p5.json')
io.open(p, 'w', encoding='utf-8').write(json.dumps(out, ensure_ascii=False, indent=2))
print('写出 %s：事件 %d，战役 %d' % (p, len(events), len(battles)))
for e in events:
    print('事件', e['id'], 'place=%s' % e['place_id'], 'passages=%d' % len(e['passage_ids']))
for b in battles:
    print('战役', b['id'], 'place=%s' % b['place_id'], 'front_line=%d 节点' % len(b['front_line']))
