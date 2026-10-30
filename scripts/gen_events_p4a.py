#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P4-A 联动：生成第 71–80 回的 3 组事件 + 2 场战役（data/event_battle_ch071_080.json）。
约束同 gen_events_p3a.py：passage_ids 由本脚本从 build/chapters 解析生成，禁止手改；
participants/commanders 仅引用已建档 id + 本批新卡（sim_yi/guan_ping/liu_feng/hua_tuo）。
本批事件组：①定军山之战（70–71 回，含汉水赵云一身是胆）②水淹七军（74 回）
③败走麦城（76–77 回）④曹丕受禅篡汉（80 回）。
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


def refs(*pairs):
    return [ref(no, kw) for no, kw in pairs]


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


def check_place(pid):
    if pid not in places:
        raise SystemExit('地点不存在：%s' % pid)


def check_front_line(b):
    for n in b['front_line']:
        for k in ('time', 'time_seq', 'kind', 'label', 'desc', 'lng', 'lat'):
            if k not in n:
                raise SystemExit('%s front_line 节点缺字段 %s' % (b['id'], k))
        base = places[b['place_id']]
        if abs(n['lng'] - base['lng']) > 0.06 or abs(n['lat'] - base['lat']) > 0.06:
            raise SystemExit('%s front_line 节点「%s」坐标偏离 %s 过远' % (b['id'], n['label'], base['name']))


events, battles = [], []

# ---- E1 + B1 定军山之战（70–71 回，219；含汉水赵云一身是胆） ----
b1 = {
    'id': 'dingjunshan_battle', 'name': '定军山之战', 'year': 219,
    'date_text': '建安二十四年正月（219）',
    'place_id': 'ding_jun_shan', 'event_id': 'dingjunshan_zhi_zhan',
    'belligerents': [
        {'side': '蜀军（刘备）', 'faction_ids': ['shu'], 'commanders': ['huang_zhong', 'fa_zheng', 'liu_bei', 'zhao_yun'],
         'troops_desc': '法正谋主，黄忠主将，步步为营反客为主，赵云接应'},
        {'side': '曹军（夏侯渊）', 'faction_ids': ['wei'], 'commanders': ['xiahou_yuan', 'zhang_he', 'cao_cao'],
         'troops_desc': '夏侯渊张郃守汉中，曹操起四十万大军亲征接应'},
    ],
    'result': '黄忠据对山以逸待劳，驰下山一举斩夏侯渊；张郃败走，蜀军遂取定军山，汉中大势底定。',
    'casualties_note': '曹军主帅夏侯渊被斩，曹兵大溃；蜀军无损大将。',
    'summary': '法正居高临下以逸待劳，午时红旗一挥，黄忠驰下山连头带肩砍夏侯渊为两段，定军山蜀军全胜。',
    'detail': '备自引兵十万图汉中，忠与法正屯定军山口。正令忠夜夺对面高山，与定军山相对，己居山顶：白旗则按兵，红旗则出击。渊怒而围山挑战，任其辱骂，忠按兵不动；午时以后曹兵倦怠、多下马坐息，正将红旗招展，忠一马当先驰下山来，天崩地塌之势，渊未及相迎，宝刀已落，连头带肩砍为两段。忠乘势夺定军山，张郃败走汉水，刘封、孟达先夺山栅。操闻渊死放声大哭，亲统大军来报仇，遂有汉水之战：赵云入重围救黄忠、张著，匹马单枪立营门外，壕中弓弩齐发，曹兵自相践踏落水死者无数，备赞曰：子龙一身都是胆也！号虎威将军。史载建安二十四年正月渊战死于阳平，与演义所记相合。',
    'front_line': [
        {'time': 219, 'time_seq': 1, 'kind': '对峙', 'label': '隔山相持', 'desc': '黄忠与法正屯定军山口，累次挑战，夏侯渊坚守不出。', 'lng': 106.67, 'lat': 33.09},
        {'time': 219, 'time_seq': 2, 'kind': '夺山', 'label': '夜夺对山', 'desc': '二更杀上对面高山，杜袭弃山而走；法正居顶，白旗红旗为号。', 'lng': 106.64, 'lat': 33.06},
        {'time': 219, 'time_seq': 3, 'kind': '突袭', 'label': '斩夏侯渊', 'desc': '午时曹兵倦怠，红旗招展，黄忠驰下山，连头带肩砍渊为两段。', 'lng': 106.7, 'lat': 33.12},
        {'time': 219, 'time_seq': 4, 'kind': '追击', 'label': '郃败走汉水', 'desc': '黄忠陈式两下夹攻，张郃败走；刘封、孟达已夺山栅。', 'lng': 106.62, 'lat': 33.04},
        {'time': 219, 'time_seq': 5, 'kind': '接应', 'label': '云救黄忠', 'desc': '汉水北山劫粮之役，赵云杀入重围救出黄忠、张著。', 'lng': 106.64, 'lat': 33.06},
    ],
}
check_persons(b1, 'belligerents')
check_place(b1['place_id'])
check_front_line(b1)
battles.append(b1)
e1 = {
    'id': 'dingjunshan_zhi_zhan', 'name': '定军山之战', 'kind': '征伐',
    'start_year': 219, 'end_year': 219, 'date_text': '建安二十四年正月（219）',
    'summary': '黄忠据定军山对面高山，法正以逸待劳举旗为号，忠驰下斩夏侯渊；随后汉水之战赵云一身是胆，曹操弃汉中。',
    'detail': '详见战役「定军山之战」。天荡山既失，备引兵十万亲征汉中：黄忠严颜先破张郃，忠与法正计斩夏侯渊；操亲征报仇，劫粮反败，汉水一战赵云空营却敌，玄德赞「子龙一身都是胆」，加为虎威将军。此后操退屯阳平，徐晃背水列阵又败，操弃汉中北还，备遂有汉中，进位汉中王。',
    'place_id': 'ding_jun_shan', 'parent_event_id': None,
    'participants': [
        {'person_id': 'huang_zhong', 'role_desc': '主将，驰下山连头带肩斩夏侯渊'},
        {'person_id': 'fa_zheng', 'role_desc': '谋主，夺山居顶，白旗红旗以逸待劳'},
        {'person_id': 'xiahou_yuan', 'role_desc': '曹军主帅，围山挑战，措手不及被斩'},
        {'person_id': 'zhang_he', 'role_desc': '苦谏渊勿出战，败走汉水，守北山粮草'},
        {'person_id': 'zhao_yun', 'role_desc': '汉水之战杀入重围救黄忠张著，空营却敌，号虎威将军'},
        {'person_id': 'liu_bei', 'role_desc': '统帅亲征汉中，赞子龙一身都是胆'},
        {'person_id': 'cao_cao', 'role_desc': '起四十万大军亲征报仇，兵败弃汉中'},
    ],
    'passage_ids': refs(
        (70, '天荡山'), (70, '定军山'),
        (71, '法正'), (71, '夏侯渊'),
        (71, '一身都是胆'), (71, '汉水')),
    'battle_ids': ['dingjunshan_battle'],
}
check_persons(e1, 'participants')
events.append(e1)

# ---- E2 + B2 水淹七军（74 回，219） ----
b2 = {
    'id': 'shuiyan_qijun_battle', 'name': '水淹七军', 'year': 219,
    'date_text': '建安二十四年八月（219）',
    'place_id': 'fan_cheng', 'event_id': 'shuiyan_qijun',
    'belligerents': [
        {'side': '蜀军（关羽）', 'faction_ids': ['shu'], 'commanders': ['guan_yu', 'guan_ping', 'zhou_cang'],
         'troops_desc': '关羽决襄江之水乘高就船，周仓水中生擒庞德'},
        {'side': '曹军（于禁七军）', 'faction_ids': ['wei'], 'commanders': ['yu_jin', 'pang_de', 'cao_ren'],
         'troops_desc': '于禁督七军三万屯罾口川，庞德抬榇死战，曹仁困守樊城'},
    ],
    'result': '大水骤至，七军皆没：于禁拜伏乞降，庞德立而不跪、引颈受刑；关羽威震华夏，操议迁都以避其锋。',
    'casualties_note': '于禁七军三万人死于水中、余皆投降；庞德部将董衡董超成何皆死。',
    'summary': '关羽观襄江水势，预造船筏，八月骤雨决水淹于禁七军于罾口川：禁降、德死，华夏皆惊。',
    'detail': '操遣于禁督七军救樊城，庞德抬榇决死战，与关公平战百合不分胜负，又箭中公左臂，赖于禁忌功鸣金不果。于禁移七军屯樊城北十里罾口川险隘之地，公望襄江水急，喜曰：鱼入罾口，岂能久乎！时值八月秋雨连绵，公先堰住各处水口、预备船筏。是夜风雨大作，大水骤至，平地水深丈余，七军乱窜随波逐浪。禁左右五六十人无路，口称愿降；庞德立堤上死战，斩董衡董超以止降议，夺小船欲走樊城，被周仓大筏撞翻生擒。禁押送荆州大牢，德骂不绝口引颈受刑，公怜而葬之。曹仁欲弃城，满宠谏固守，水退城全。史载汉水泛滥，于禁所督七军皆没，与演义相合。',
    'front_line': [
        {'time': 219, 'time_seq': 1, 'kind': '攻城', 'label': '兵临樊城', 'desc': '关平攻樊城，公自迎庞德；德军前抬榇誓死战。', 'lng': 112.13, 'lat': 32.04},
        {'time': 219, 'time_seq': 2, 'kind': '单挑', 'label': '德射关公', 'desc': '庞德虚作拖刀暗箭射中关公左臂；于禁忌功鸣金收军。', 'lng': 112.16, 'lat': 32.02},
        {'time': 219, 'time_seq': 3, 'kind': '水攻', 'label': '决水罾口川', 'desc': '秋雨骤雨，襄江泛涨，堰口放水，七军随波逐浪。', 'lng': 112.12, 'lat': 32.06},
        {'time': 219, 'time_seq': 4, 'kind': '擒将', 'label': '禁降德死', 'desc': '于禁拜伏乞降；庞德堤上死战，被周仓生擒，骂贼受刑。', 'lng': 112.14, 'lat': 32.05},
        {'time': 219, 'time_seq': 5, 'kind': '围城', 'label': '樊城危急', 'desc': '水围樊城，曹仁欲走，满宠谏固守，旬日水退。', 'lng': 112.13, 'lat': 32.04},
    ],
}
check_persons(b2, 'belligerents')
check_place(b2['place_id'])
check_front_line(b2)
battles.append(b2)
e2 = {
    'id': 'shuiyan_qijun', 'name': '水淹七军', 'kind': '征伐',
    'start_year': 219, 'end_year': 219, 'date_text': '建安二十四年八月（219）',
    'summary': '关羽决襄江水淹于禁七军于罾口川，庞德抬榇死战被擒殉节，关羽威震华夏，曹操议迁都。',
    'detail': '详见战役「水淹七军」。此役之后公复围樊城，曹仁弩箭中其右臂，毒已入骨，华佗刮骨疗毒；操用司马懿蒋济之谋，遣使联吴袭荆州，形势由此逆转。史载于禁督七军救樊，秋大霖雨汉水泛溢，禁降羽、庞德不降而死，与演义相合。',
    'place_id': 'fan_cheng', 'parent_event_id': None,
    'participants': [
        {'person_id': 'guan_yu', 'role_desc': '统帅，观水势决襄江，威震华夏'},
        {'person_id': 'guan_ping', 'role_desc': '攻樊城前锋，阵战庞德，救父中箭'},
        {'person_id': 'zhou_cang', 'role_desc': '乘大筏撞翻庞德小船，水中生擒庞德'},
        {'person_id': 'yu_jin', 'role_desc': '征南将军督七军，屯罾口川被淹，拜伏乞降'},
        {'person_id': 'pang_de', 'role_desc': '先锋抬榇死战，箭中关公；被擒立而不跪，引颈受刑'},
        {'person_id': 'cao_ren', 'role_desc': '困守樊城，欲弃城，赖满宠谏固守'},
        {'person_id': 'hua_tuo', 'role_desc': '自江东来为关公刮骨疗毒'},
        {'person_id': 'sim_yi', 'role_desc': '谏曹操勿迁都，密陈联吴袭荆州之计'},
    ],
    'passage_ids': refs(
        (74, '庞德'), (74, '于禁'), (74, '罾口川'), (74, '周仓'),
        (75, '华佗'), (75, '司马懿')),
    'battle_ids': ['shuiyan_qijun_battle'],
}
check_persons(e2, 'participants')
events.append(e2)

# ---- E3 败走麦城（76–77 回，219–220） ----
e3 = {
    'id': 'maicheng_zhiluan', 'name': '败走麦城', 'kind': '人物',
    'start_year': 219, 'end_year': 220, 'date_text': '建安二十四年冬十二月（219–220）',
    'summary': '荆州既失、徐晃解樊围，关羽进退无路退保麦城；上庸不救，突围夜走临沮，父子被擒殉难。',
    'detail': '吕蒙白衣渡江袭荆州，糜芳傅士仁献城降吴；徐晃破四冢解樊城之围，公疮口迸裂。取荆州路中吴军四伏，军心尽变，部从止三百余人，退入麦城。差廖化往上庸求救，刘封听孟达之言以山城初附为辞按兵不动；诸葛瑾奉权命劝降，公正色拒之：玉可碎而不可改其白，竹可焚而不可毁其节。城粮尽，公弃城夜走临沮小路，朱然潘璋伏兵四起，潘璋部将马忠以长钩套索绊倒赤兔马，公被擒；关平孤身独战力尽亦被执。权欲降之，左右咸曰恐贻后患，遂父子同遇害，时建安二十四年冬十二月，公亡年五十八。王甫堕城，周仓自刎，麦城亦陷。吕蒙庆功宴上为公英魂所附，七窍流血而死；权移祸于操，操以王侯礼葬公首级于洛阳。史载孙权遣将逆击羽，斩羽及子平于临沮，与演义相合。',
    'place_id': 'mai_cheng', 'parent_event_id': None,
    'participants': [
        {'person_id': 'guan_yu', 'role_desc': '败退麦城，拒诸葛瑾劝降，夜走临沮被擒，父子殉难'},
        {'person_id': 'guan_ping', 'role_desc': '护廖化突围求救，临沮独战力尽被执，与父同遇害'},
        {'person_id': 'liu_feng', 'role_desc': '与孟达守上庸，听谗不发救兵'},
        {'person_id': 'lv_meng', 'role_desc': '白衣渡江袭荆州设计擒羽，庆功宴上英魂所附而死'},
        {'person_id': 'pan_zhang', 'role_desc': '奉吕蒙计伏兵临沮小路，部将马忠擒获关羽'},
    ],
    'passage_ids': refs(
        (76, '麦城'), (76, '上庸'), (76, '诸葛瑾'),
        (77, '临沮'), (77, '马忠'), (77, '潘璋')),
}
check_persons(e3, 'participants')
events.append(e3)

# ---- E4 曹丕受禅篡汉（80 回，220） ----
e4 = {
    'id': 'shouchan_cuan_han', 'name': '曹丕受禅篡汉', 'kind': '人物',
    'start_year': 220, 'end_year': 220, 'date_text': '延康元年十月庚午（220）',
    'summary': '华歆等逼献帝禅位，曹丕三让后登受禅坛即皇帝位，国号大魏，封献帝为山阳公，四百年汉室至此而亡。',
    'detail': '操死丕嗣魏王位，华歆等一班文武奏称汉祚已终，请帝效尧舜禅位。帝泣曰：朕想高祖提三尺剑，斩蛇起义，创造基业四百年矣。歆引李伏许芝奏图谶符瑞，王朗进兴废之论，曹洪曹休拔剑逼宫，符宝郎祖弼索玺被斩。丕初欲受诏，司马懿谏曰宜且上表谦辞以绝天下之谤；三让之后，卜地繁阳筑受禅坛，十月庚午日帝亲捧玉玺奉丕。丕受八般大礼登帝位，改延康元年为黄初元年，国号大魏，谥操为太祖武皇帝；封献帝为山阳公，华歆按剑厉声：非宣召不许入朝！成都误传帝遇害，百官拥刘备即皇帝位以继汉统，改元章武。史载延康元年十月丕代汉，与演义相合。',
    'place_id': 'xu_du', 'parent_event_id': None,
    'participants': [
        {'person_id': 'cao_pi', 'role_desc': '嗣魏王，三让后登受禅坛即皇帝位，国号大魏'},
        {'person_id': 'liu_xie', 'role_desc': '献帝被逼禅位，降封山阳公，汉室四百年至此而终'},
        {'person_id': 'sim_yi', 'role_desc': '谏曹丕上表谦辞以绝天下之谤'},
        {'person_id': 'liu_bei', 'role_desc': '闻曹丕篡汉，为孔明等拥立即皇帝位以继汉统'},
    ],
    'passage_ids': refs(
        (80, '禅位'), (80, '受禅'), (80, '司马懿'), (80, '章武')),
}
check_persons(e4, 'participants')
events.append(e4)

out = {'comment': 'P4-A（2026-10-29）：第 71–80 回的 4 组事件（定军山、水淹七军、败走麦城、曹丕受禅）+ 2 场战役；汉水赵云一身是胆并入定军山事件与战役。passage_ids 由本脚本解析生成，禁止手改。',
       'events': events, 'battles': battles}
p = os.path.join(DATA, 'event_battle_ch071_080.json')
io.open(p, 'w', encoding='utf-8').write(json.dumps(out, ensure_ascii=False, indent=2))
print('写出 %s：事件 %d，战役 %d' % (p, len(events), len(battles)))
