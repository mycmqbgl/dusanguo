#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P1-E/D 联动：生成第 11–20 回的 8 组事件 + 6 场战役（data/event_battle_ch011_020.json）。

用法：先跑一次 build.py（让新地名拿到像素坐标），再跑本脚本，再跑一次 build.py。

设计约束（沿用 gen_events_p1d.py）：
- passage_ids 不手填：出处写成 (回数, 关键词)，脚本解析出段落 id 并断言命中。
- participants/commanders 只允许引用已建档 person id。
- front_line 坐标从 build/places.json 取，允许 ±0.06° 偏移防叠点。
"""
import json, io, os, sys

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
    return [ref(n, k) for n, k in pairs]


def coords(pid, dx=0.0, dy=0.0):
    p = places[pid]
    return round(p['lng'] + dx, 3), round(p['lat'] + dy, 3)


def check_ids(persons):
    bad = [x['person_id'] for x in persons if x['person_id'] not in person_ids]
    if bad:
        raise SystemExit('未建档的人物 id：%s' % ', '.join(bad))


def check_cmd_ids(ids):
    bad = [i for i in ids if i not in person_ids]
    if bad:
        raise SystemExit('战役指挥官未建档：%s' % ', '.join(bad))


def nd(seq, kind, label, desc, pid, dx=0.0, dy=0.0, year=None):
    lng, lat = coords(pid, dx, dy)
    return {'time': year, 'time_seq': seq, 'kind': kind, 'label': label, 'desc': desc, 'lng': lng, 'lat': lat}


events, battles = [], []
A, B = events.append, battles.append

# =============== 1. 曹操徐州复仇之战（194） ===============
A({
 'id': 'cao_tao_xuzhou_zhi_zhan', 'name': '曹操东征徐州', 'kind': '军事行动',
 'start_year': 194, 'end_year': 194, 'date_text': '兴平元年（194）',
 'summary': '曹嵩过徐州被张闿所杀，曹操尽起大军东征，所到之处鸡犬不留；刘备、田楷、孔融驰援，吕布陈宫袭兖州，操被迫退兵。',
 'detail': '曹操遣泰山太守应劭往琅琊郡接父曹嵩，嵩携家小四十余口经徐州，陶谦欲结好曹操，遣都尉张闿护送——闿乃黄巾余党，见财起意，尽杀嵩家小，劫财奔淮南。操闻之哭倒于地，切齿曰「陶谦纵兵杀吾父，此仇不共戴天」，遂留荀彧程昱守鄄城，尽起大军东征，下令但得城池，将城中百姓尽行屠戮，以雪父仇。操屠徐州，泗水为之不流；陶谦求救于孔融、田楷，融请刘备同往，备借得公孙瓒部赵云及二千兵驰援。操攻拨势急，恰逢陈宫张邈迎吕布袭兖州，操只得罢兵回救。',
 'place_id': 'xu_zhou', 'parent_event_id': None,
 'participants': [
  {'person_id': 'cao_cao', 'role_desc': '主帅，尽起大军东征屠徐州'},
  {'person_id': 'tao_qian', 'role_desc': '徐州牧，本欲结好操，反受其祸'},
  {'person_id': 'liu_bei', 'role_desc': '平原相，借赵云与兵驰援徐州'},
  {'person_id': 'kong_rong', 'role_desc': '北海相，请刘备同救徐州'},
  {'person_id': 'tian_kai', 'role_desc': '青州刺史，与刘备为掎角之势'},
  {'person_id': 'zhao_yun', 'role_desc': '借兵两千来助，阵前护刘备'},
  {'person_id': 'chen_gong', 'role_desc': '说张邈迎吕布袭兖州，逼操退兵'},
 ],
 'timeline': [
  {'year': 194, 'title': '张闿杀曹嵩', 'description': '护送途中黄巾余党张闿见财起意，尽杀嵩家小四十余口。', 'importance': 3},
  {'year': 194, 'title': '操起兵复仇', 'description': '「陶谦纵兵杀吾父，此仇不共戴天」，令屠城泄愤。', 'importance': 3},
  {'year': 194, 'title': '泗水不流', 'description': '操军所到之处鸡犬不留，杀戮之惨震动诸侯。', 'importance': 3},
  {'year': 194, 'title': '诸镇驰援', 'description': '孔融、田楷、刘备陆续赴援，刘备致书曹操请和。', 'importance': 2},
  {'year': 194, 'title': '吕布袭兖州', 'description': '陈宫、张邈迎吕布入兖州，仅余鄄城、范、东阿三城。', 'importance': 3},
  {'year': 194, 'title': '操退兵回救', 'description': '兖州危局，曹操罢兵退回，陶谦让徐州于刘备。', 'importance': 2},
 ],
 'passage_refs': None,
 'passage_ids': refs(
  (10, '张闿'), (10, '此仇不共戴天'), (10, '尽行屠戮'), (11, '却说曹操'),
  (11, '孔融'), (11, '管亥'), (11, '陶谦'), (11, '陈宫'),
 ),
})
B({
 'id': 'xuzhou_fu_chou', 'name': '徐州屠城之战', 'year': 194, 'date_text': '兴平元年（194）',
 'place_id': 'xu_zhou', 'event_id': 'cao_tao_xuzhou_zhi_zhan',
 'belligerents': [
  {'side': '曹操军', 'faction_ids': ['warlord'], 'commanders': ['cao_cao', 'yu_jin'], 'troops_desc': '兖州大军倾巢而出'},
  {'side': '徐州守军与援军', 'faction_ids': ['warlord'], 'commanders': ['tao_qian', 'liu_bei', 'kong_rong', 'tian_kai'], 'troops_desc': '陶谦本部 + 孔融田楷援军 + 刘备赵云'},
 ],
 'result': '曹操屠城连下数城，因吕布袭兖州被迫退兵',
 'casualties_note': '泗水为之不流；管亥为关羽所斩。',
 'summary': '曹操为父复仇东征，所过屠戮；刘备孔融驰援不支，吕布袭兖州令操罢兵——徐州之祸暂解。',
 'detail': '操军攻拔徐州所过之处鸡犬不留。陶谦欲缚己送操营请罪未成；孔融被围北海遣太史慈突围求救，刘备借兵来援，阵前关羽数十合斩管亥解北海之围，遂与田楷为掎角赴徐州。操怒攻愈急，恰陈宫张邈迎吕布入兖州，操只得退兵；陶谦三让徐州，备初辞，谦卒后备始领徐州牧。',
 'front_line': [
  nd(1, '出兵', '起大军东征', '留荀彧程昱守鄄城，尽起大军令屠城。', 'yan_zhou', 0.02, 0, 194),
  nd(2, '攻伐', '所过屠戮', '攻拔徐州城池，鸡犬不留，泗水不流。', 'xu_zhou', 0, 0, 194),
  nd(3, '救援', '北海解围', '刘备关羽驰援，数十合斩管亥，与田楷会徐州。', 'bei_hai', 0.04, -0.03, 194),
  nd(4, '对峙', '徐州城下', '陶谦让徐州，刘备初辞不受。', 'xu_zhou', -0.05, 0.02, 194),
  nd(5, '结局', '吕布袭兖州', '陈宫张邈迎吕布，操退兵回救，徐州暂解。', 'juancheng', 0.03, -0.02, 194),
 ],
})

# =============== 2. 濮阳之战（194–195） ===============
A({
 'id': 'puyang_zhi_zhan', 'name': '濮阳·兖州争夺', 'kind': '军事行动',
 'start_year': 194, 'end_year': 195, 'date_text': '兴平元年—二年（194–195）',
 'summary': '陈宫张邈迎吕布入兖州，郡县响应，曹操仅余鄄城等三城。濮阳城内田氏诈降诱操入城，操中伏几死，赖典韦死战得出。相持岁余，蝗灾起，双方罢兵。',
 'detail': '陈宫说张邈「今天下分崩，豪杰并起」，迎吕布屯濮阳，兖州郡县皆应，曹操地盘只剩鄄城、范、东阿。操回师攻濮阳，城中大户田氏诈降开门——操单马入城，吕布军伏兵四起，操赖典韦冲杀、吕布戟击操盔而不识，操反指「骑黄马者是我」脱身，遇火烧须坠马，为典韦救出。此后相持岁余，蝗灾起、粮尽，双方罢兵。操自此定「先取山东，后图天下」之策，收许褚、破定陶巨野，吕布败投刘备。',
 'place_id': 'pu_yang', 'parent_event_id': None,
 'participants': [
  {'person_id': 'cao_cao', 'role_desc': '回师攻濮阳，中伏几死'},
  {'person_id': 'lv_bu', 'role_desc': '入主兖州屯濮阳，戟击操盔而不识'},
  {'person_id': 'chen_gong', 'role_desc': '首谋迎吕布入兖州'},
  {'person_id': 'dian_wei', 'role_desc': '死战救操出濮阳城'},
  {'person_id': 'chen_deng', 'role_desc': '（广陵）闻操势复振，劝父暗结曹操'},
  {'person_id': 'xu_chu', 'role_desc': '何仪部将出身，操收为宿卫'},
 ],
 'timeline': [
  {'year': 194, 'title': '吕布入兖州', 'description': '陈宫说张邈迎布，郡县响应，操仅余三城。', 'importance': 3},
  {'year': 194, 'title': '濮阳中伏', 'description': '田氏诈降，操单骑入城中伏，吕布戟击其盔不识。', 'importance': 3},
  {'year': 194, 'title': '典韦救主', 'description': '操遇火烧须坠马，典韦死战得出。', 'importance': 2},
  {'year': 195, 'title': '蝗灾罢兵', 'description': '岁余相持，蝗灾粮尽，双方罢兵。', 'importance': 2},
  {'year': 195, 'title': '操复振', 'description': '收许褚、破定陶巨野，吕布败投刘备。', 'importance': 2},
 ],
 'passage_ids': refs(
  (11, '陈宫'), (11, '濮阳'), (11, '典韦'), (12, '田氏'), (12, '许褚'), (12, '定陶'),
 ),
})
B({
 'id': 'puyang_zhi_bian', 'name': '濮阳中伏', 'year': 194, 'date_text': '兴平元年（194）',
 'place_id': 'pu_yang', 'event_id': 'puyang_zhi_zhan',
 'belligerents': [
  {'side': '曹操军', 'faction_ids': ['warlord'], 'commanders': ['cao_cao', 'dian_wei'], 'troops_desc': '回师兖州之军'},
  {'side': '吕布军', 'faction_ids': ['warlord'], 'commanders': ['lv_bu', 'gao_shun', 'zhang_liao'], 'troops_desc': '濮阳守军，田氏为内应'},
 ],
 'result': '操中伏几死，典韦死战得出；城池仍归吕布',
 'casualties_note': '操须发被烧，坠马后赖步军救出。',
 'summary': '田氏诈降诱操入城，吕布伏兵四起；吕布当面戟击操盔而不识，典韦冲杀救主——操平生最险一役。',
 'detail': '操攻濮阳不下，田氏献城诈降。操率军入城，行至州衙，一声炮响伏兵尽起：北巷张辽、东巷臧霸、西巷高顺、南巷郝萌曹性成廉，六将围操。操赖典韦冲杀至东门，吕布当面问「曹操何在」，操反指「骑黄马者是我」，布纵马追之去。操遇火烧须、梁柱压臂，典韦再入救出。是役操几丧命，自此知吕布不可力敌。',
 'front_line': [
  nd(1, '诱敌', '田氏献门', '城内大户田氏诈降，操自率军入。', 'pu_yang', 0, 0, 194),
  nd(2, '中伏', '六将围操', '北巷张辽、东巷臧霸、西巷高顺、南巷郝萌等围之。', 'pu_yang', 0.05, 0.02, 194),
  nd(3, '脱身', '布不识操', '布戟击操盔问「曹操何在」，操反指黄马者。', 'pu_yang', -0.05, -0.03, 194),
  nd(4, '救主', '典韦冲杀', '操遇火坠马，典韦再入救出。', 'pu_yang', 0.03, -0.05, 194),
 ],
})

# =============== 3. 吕布袭徐州（196） ===============
A({
 'id': 'lv_bu_xi_xuzhou', 'name': '吕布袭徐州', 'kind': '军事行动',
 'start_year': 196, 'end_year': 196, 'date_text': '建安元年（196）',
 'summary': '袁术许粮马金帛约吕布夹攻刘备；吕布夜袭下邳，张飞醉酒失城，刘备家小陷落。刘备进退无路，反屯小沛附布。',
 'detail': '袁术遗书吕布，许粮五万斛、马五百匹、金银一万两、彩缎一千匹，使夹攻刘备。吕布令高顺袭玄德之后；备乘阴雨撤盱眙之兵，高顺与纪灵索许物不得——术书言「待捉了刘备方送」。布怒骂术失信，陈宫劝布迎备屯小沛为羽翼。此后张飞守徐州醉酒鞭曹豹，豹修书吕布，布夜袭下邳，飞醉不能战，弃城而走，备家小陷于城中。备无路可投，竟屈身受布安排屯小沛——新失徐州、寄人篱下，是刘备半生最狼狈的一段。',
 'place_id': 'xu_zhou', 'parent_event_id': None,
 'participants': [
  {'person_id': 'lv_bu', 'role_desc': '袭下邳据徐州'},
  {'person_id': 'liu_bei', 'role_desc': '进退无路，反屯小沛附布'},
  {'person_id': 'zhang_fei', 'role_desc': '醉酒失下邳，弃家小而走'},
  {'person_id': 'cao_bao', 'role_desc': '遭飞鞭打，修书召吕布，出城接应被杀'},
  {'person_id': 'gao_shun', 'role_desc': '奉布命袭玄德之后'},
  {'person_id': 'yuan_shu', 'role_desc': '许粮马约夹攻，事后背约'},
  {'person_id': 'mi_zhu', 'role_desc': '迎备家小，进妹于备为夫人'},
 ],
 'timeline': [
  {'year': 196, 'title': '术书约布', 'description': '袁术许粮马金帛约吕布夹攻刘备。', 'importance': 2},
  {'year': 196, 'title': '布袭下邳', 'description': '张飞醉酒鞭曹豹，豹书布夜袭下邳。', 'importance': 3},
  {'year': 196, 'title': '备陷绝境', 'description': '失徐州失家小，袁术又不容，进退无路。', 'importance': 2},
  {'year': 196, 'title': '屯小沛附布', 'description': '布迎备屯小沛为羽翼，备屈身从之。', 'importance': 2},
 ],
 'passage_ids': refs(
  (14, '袁术'), (14, '曹豹'), (14, '吕布'), (15, '却说张飞'), (15, '袁术'),
 ),
})
B({
 'id': 'xuzhou_yi_shou', 'name': '下邳夜袭', 'year': 196, 'date_text': '建安元年（196）',
 'place_id': 'xu_zhou', 'event_id': 'lv_bu_xi_xuzhou',
 'belligerents': [
  {'side': '吕布军', 'faction_ids': ['warlord'], 'commanders': ['lv_bu', 'gao_shun'], 'troops_desc': '五百骑为先导，大军继后'},
  {'side': '刘备军（张飞守城）', 'faction_ids': ['warlord'], 'commanders': ['zhang_fei'], 'troops_desc': '醉酒失备'},
 ],
 'result': '下邳失守，徐州易主，刘备家小陷落',
 'casualties_note': '曹豹出城接应被张飞刺死。',
 'summary': '张飞醉酒鞭曹豹，豹引吕布夜袭下邳；飞醉不能战，弃城而走——刘备半生基业一夜易手。',
 'detail': '张飞守徐州，醉后逼曹豹饮酒，豹以女婿吕布求饶，飞怒鞭五十。豹连夜修书吕布，劝其乘备出、飞醉袭下邳。布夜率五百骑先至，喊声举火，飞醉卧未醒，左右拽起出城，家小尽陷。布据徐州，自领州事。',
 'front_line': [
  nd(1, '内应', '豹修书布', '张飞醉鞭曹豹，豹连夜书吕布约袭。', 'xu_zhou', 0.03, 0.02, 196),
  nd(2, '夜袭', '布入下邳', '布五百骑先入，举火呐喊，飞醉卧不醒。', 'xu_zhou', 0, 0, 196),
  nd(3, '易主', '徐州易手', '飞弃城走，备家小陷落，布自领州事。', 'xu_zhou', -0.05, -0.03, 196),
 ],
})

# =============== 4. 辕门射戟（196） ===============
A({
 'id': 'yuanmen_sheji', 'name': '辕门射戟', 'kind': '政治事件',
 'start_year': 196, 'end_year': 196, 'date_text': '建安元年（196）',
 'summary': '纪灵三万兵攻刘备，布恐唇亡齿寒，设宴辕门、以射戟为赌：一箭中戟小枝，两家罢兵——「将军天威也」。',
 'detail': '袁术遣纪灵攻小沛，备求救于吕布。布恐术破备则己被围，遂设宴请纪灵、刘备同至，席间于辕门外一百五十步设戟，曰「吾一箭射中戟小枝，两家罢兵；不中，任从厮杀」。布弓开如秋月，一箭正中戟小枝。纪灵畏布之勇，罢兵回淮南。此役是吕布一生最体面的时刻，也是其与刘备关系最后一次维系。',
 'place_id': 'xu_zhou', 'parent_event_id': None,
 'participants': [
  {'person_id': 'lv_bu', 'role_desc': '设宴辕门，一箭解两家之斗'},
  {'person_id': 'liu_bei', 'role_desc': '被攻方，得布之救'},
  {'person_id': 'guan_yu', 'role_desc': '随备赴宴压阵'},
  {'person_id': 'ji_ling', 'role_desc': '攻备方主将，畏布罢兵'},
  {'person_id': 'zhang_fei', 'role_desc': '随备赴宴，席间欲杀灵'},
 ],
 'timeline': [
  {'year': 196, 'title': '纪灵攻备', 'description': '袁术遣纪灵三万兵攻小沛，备求救于布。', 'importance': 2},
  {'year': 196, 'title': '布设局', 'description': '布设宴请两家，辕门一百五十步设戟为赌。', 'importance': 3},
  {'year': 196, 'title': '一箭定局', 'description': '布一箭正中戟小枝，纪灵罢兵。', 'importance': 3},
 ],
 'passage_ids': refs(
  (16, '辕门'), (16, '射戟'), (16, '纪灵'), (16, '射中戟小枝'),
 ),
})

# =============== 5. 宛城之变（197） ===============
A({
 'id': 'wancheng_zhi_bian', 'name': '宛城之变', 'kind': '军事行动',
 'start_year': 197, 'end_year': 197, 'date_text': '建安二年（197）正月',
 'summary': '曹操纳张绣叔母邹氏，绣用贾诩计夜反；典韦失戟战死，曹昂让马救父、曹安民皆遇害——操平生最惨之败。',
 'detail': '曹操南征，绣举众降。操侄安民引操见绣叔母邹氏，操遂取之；绣以为奇耻，用贾诩计：请胡车儿盗典韦双戟，夜袭曹营。变起仓促，韦醉失兵器，以步卒短刀杀数十人、挟两尸为兵器而战死；操中箭，昂以己马授操得脱，昂、安民皆殁。操收兵于淯水岸祭奠典韦——「吾折长子、爱侄，俱无深痛；独号泣典韦也」。此后绣再叛再降，官渡前依贾诩之策降操。',
 'place_id': 'wan_cheng', 'parent_event_id': None,
 'participants': [
  {'person_id': 'cao_cao', 'role_desc': '中箭败走，淯水祭韦'},
  {'person_id': 'zhang_xiu', 'role_desc': '降而夜反，杀操长子'},
  {'person_id': 'jia_xu', 'role_desc': '献夜反之计'},
  {'person_id': 'dian_wei', 'role_desc': '失戟死战，殁于辕门'},
  {'person_id': 'cao_ang', 'role_desc': '让马救父，自身战死'},
  {'person_id': 'cao_anmin', 'role_desc': '引操见邹氏，变中遇害'},
  {'person_id': 'hu_cheer', 'role_desc': '盗典韦双戟'},
 ],
 'timeline': [
  {'year': 197, 'title': '绣举众降', 'description': '操南征至宛城，绣降。', 'importance': 1},
  {'year': 197, 'title': '纳邹氏', 'description': '安民引操见绣叔母邹氏，操遂取之，绣以为耻。', 'importance': 2},
  {'year': 197, 'title': '夜变', 'description': '贾诩献计，胡车儿盗典韦双戟，绣夜反。', 'importance': 3},
  {'year': 197, 'title': '典韦战死', 'description': '韦醉失兵器，步战杀数十人而亡。', 'importance': 3},
  {'year': 197, 'title': '昂让马', 'description': '操中箭，昂以己马授操，自身战死；安民亦殁。', 'importance': 3},
  {'year': 197, 'title': '淯水祭韦', 'description': '操祭典韦：「折长子爱侄俱无深痛，独号泣典韦。」', 'importance': 2},
 ],
 'passage_ids': refs(
  (16, '张绣'), (16, '邹氏'), (16, '胡车儿'), (16, '典韦'), (16, '淯水'),
 ),
})
B({
 'id': 'wancheng_ye_zhan', 'name': '宛城夜战', 'year': 197, 'date_text': '建安二年（197）正月',
 'place_id': 'wan_cheng', 'event_id': 'wancheng_zhi_bian',
 'belligerents': [
  {'side': '张绣军', 'faction_ids': ['warlord'], 'commanders': ['zhang_xiu', 'hu_cheer'], 'troops_desc': '夜袭曹营'},
  {'side': '曹操军', 'faction_ids': ['wei'], 'commanders': ['cao_cao', 'dian_wei'], 'troops_desc': '仓促应战'},
 ],
 'result': '操军溃败，典韦、曹昂、曹安民皆殁',
 'casualties_note': '典韦步战杀数十人而死；操长子昂、侄安民遇害。',
 'summary': '绣夜袭曹营，典韦失戟死战于辕门，操中箭由昂让马得脱——宛城一夜，操折典韦、昂、安民三人。',
 'detail': '二更时分绣军四起，曹营仓促应战。典韦醉卧失戟，取步卒腰刀杀数十人，刀砍缺不能用，复挟两尸迎敌，至死据辕门。操中箭走，昂以马授操，安民被杀。操走至舞阴收兵，闻韦死为位哭祭。',
 'front_line': [
  nd(1, '夜起', '绣军四起', '二更绣军举火喊杀，曹营仓促应战。', 'wan_cheng', 0, 0, 197),
  nd(2, '死战', '典韦据辕门', '韦失戟步战，挟两尸迎敌，至死不退。', 'wan_cheng', 0.05, -0.02, 197),
  nd(3, '脱身', '昂让马', '操中箭，昂以己马授操，父子自此永诀。', 'wan_cheng', -0.04, 0.03, 197),
  nd(4, '收兵', '淯水祭奠', '操收兵淯水岸，设祭哭典韦。', 'yu_shui', 0, 0, 197),
 ],
})

# =============== 6. 献帝东归（195–196） ===============
A({
 'id': 'xian_di_dong_gui', 'name': '献帝东归', 'kind': '政治事件',
 'start_year': 195, 'end_year': 196, 'date_text': '兴平二年—建安元年（195–196）',
 'summary': '李傕郭汜相攻，献帝与伏皇后随驾东归，杨奉董承韩暹等血战护驾；至洛阳宫室尽毁，曹操迎天子都许——「挟天子以令诸侯」自此始。',
 'detail': '李傕郭汜相攻数月，长安化为丘墟；杨奉、董承等护献帝东归，傕汜追击，东涧、曹阳血战，百官士卒死者不可胜数。渡黄河至安邑、洛阳，宫室尽毁，百官采野菜充饥。董承召曹操入朝制衡韩暹，操遂迎天子移驾许都——自此挟天子以令诸侯，汉室名存实亡。',
 'place_id': 'luo_yang', 'parent_event_id': None,
 'participants': [
  {'person_id': 'liu_xie', 'role_desc': '献帝，随驾东归受尽颠沛'},
  {'person_id': 'li_jue', 'role_desc': '劫帝、追击'},
  {'person_id': 'guo_si', 'role_desc': '劫公卿，与傕相攻'},
  {'person_id': 'dong_cheng', 'role_desc': '护驾东归，后召曹操'},
  {'person_id': 'yang_feng', 'role_desc': '白波帅，血战护驾'},
  {'person_id': 'han_xi', 'role_desc': '护驾有功拜大将军，后专权'},
  {'person_id': 'duan_wei', 'role_desc': '华阴迎驾献衣粮'},
  {'person_id': 'fu_huanghou', 'role_desc': '伏皇后随驾受苦'},
  {'person_id': 'cao_cao', 'role_desc': '迎天子移驾许都'},
 ],
 'timeline': [
  {'year': 195, 'title': '傕汜相攻', 'description': '李傕郭汜相攻数月，长安化为丘墟。', 'importance': 3},
  {'year': 195, 'title': '东涧血战', 'description': '杨奉董承护驾东归，傕汜追击，东涧曹阳血战。', 'importance': 3},
  {'year': 195, 'title': '北渡黄河', 'description': '帝后徒步过河至安邑，采野菜充饥。', 'importance': 2},
  {'year': 196, 'title': '还洛阳', 'description': '洛阳宫室尽毁，百官无以为居。', 'importance': 2},
  {'year': 196, 'title': '董承召操', 'description': '韩暹专权，承密召曹操入朝。', 'importance': 2},
  {'year': 196, 'title': '移驾许都', 'description': '操迎天子都许，挟天子以令诸侯自此始。', 'importance': 3},
 ],
 'passage_ids': refs(
  (13, '李傕'), (13, '郭汜'), (13, '东涧'), (13, '安邑'), (14, '董承'), (14, '移驾'),
 ),
})
B({
 'id': 'dong_gui_hu_jia', 'name': '护驾东归', 'year': 195, 'date_text': '兴平二年（195）',
 'place_id': 'hongnong', 'event_id': 'xian_di_dong_gui',
 'belligerents': [
  {'side': '护驾诸军', 'faction_ids': ['han'], 'commanders': ['dong_cheng', 'yang_feng', 'han_xi'], 'troops_desc': '护驾东归诸将'},
  {'side': '李傕郭汜追兵', 'faction_ids': ['warlord'], 'commanders': ['li_jue', 'guo_si'], 'troops_desc': '追击之军'},
 ],
 'result': '帝驾脱险北渡，百官士卒死者不可胜数',
 'casualties_note': '东涧、曹阳两役，公卿士卒死者无数。',
 'summary': '杨奉董承等护献帝东归，李傕郭汜追击，东涧曹阳血战——帝后徒步渡河，随驾者十不存一。',
 'detail': '傕汜追帝至弘农东涧，董承杨奉力战，辎重御物尽弃；至曹阳再战复败，士卒妇女死者不可胜数。帝后徒步渡黄河，皇后兄伏德挟绢十匹扶后下船。至安邑、洛阳，随驾之人十不存一。',
 'front_line': [
  nd(1, '出逃', '长安出关', '傕汜相攻，帝后随杨奉董承出关东走。', 'chang_an', 0.03, 0, 195),
  nd(2, '血战', '东涧之败', '傕汜追至东涧，董承杨奉力战，辎重尽弃。', 'hongnong', 0, 0, 195),
  nd(3, '再败', '曹阳再战', '复败于曹阳，士卒死者不可胜数。', 'hongnong', 0.06, -0.02, 195),
  nd(4, '北渡', '徒步过河', '帝后徒步渡黄河至安邑。', 'hongnong', -0.06, 0.03, 195),
  nd(5, '还都', '洛阳残破', '至洛阳宫室尽毁，随驾十不存一。', 'luo_yang', 0, 0, 196),
 ],
})

# =============== 7. 孙策定江东（195–196） ===============
A({
 'id': 'sun_ce_ding_jiangdong', 'name': '孙策定江东', 'kind': '军事行动',
 'start_year': 195, 'end_year': 196, 'date_text': '兴平二年—建安元年（195–196）',
 'summary': '孙策以传国玺质袁术借兵三千渡江，牛渚首捷、曲阿破刘繇、收太史慈，下乌程破严白虎、奇袭会稽降王朗——数年之间尽有江东，为孙吴立国之基。',
 'detail': '孙策以亡父玉玺质于袁术，借兵三千、马五百匹，以周瑜、朱治为辅，渡江首夺牛渚「尽得粮谷战具」。攻刘繇于曲阿，神亭与太史慈单骑酣斗，后擒慈亲解其缚收为爪牙；繇败走豫章。破秣陵降薛礼，下乌程破严白虎（虎奔余杭为凌操所杀），佯攻查渎夜袭会稽，王朗败降、虞翻来归。数年之间「尽有江东」，江东人称「孙郎」。曹操表策为讨逆将军、吴侯。',
 'place_id': 'jian_ye', 'parent_event_id': None,
 'participants': [
  {'person_id': 'sun_ce', 'role_desc': '渡江主帅，江东人称孙郎'},
  {'person_id': 'zhou_yu', 'role_desc': '以兵粮相助，共定江东'},
  {'person_id': 'taishi_ci', 'role_desc': '神亭酣斗、泾县来归'},
  {'person_id': 'liu_yao', 'role_desc': '扬州刺史，曲阿败走'},
  {'person_id': 'wang_lang', 'role_desc': '会稽太守，固守力战而降'},
  {'person_id': 'yan_baihu', 'role_desc': '乌程豪帅，兵败死于余杭'},
  {'person_id': 'yu_fan', 'role_desc': '会稽贤士来归，荐华佗'},
  {'person_id': 'zhang_zhao', 'role_desc': '文武之事一以委之'},
  {'person_id': 'wu_jing', 'role_desc': '策之舅，丹杨起兵之资'},
  {'person_id': 'ling_cao', 'role_desc': '余杭杀严白虎来投'},
 ],
 'timeline': [
  {'year': 195, 'title': '质玺借兵', 'description': '以传国玺质袁术，借兵三千渡江。', 'importance': 3},
  {'year': 195, 'title': '牛渚首捷', 'description': '渡江首夺牛渚，尽得粮谷战具。', 'importance': 2},
  {'year': 195, 'title': '神亭酣斗', 'description': '与太史慈单骑大战，后擒慈收服。', 'importance': 3},
  {'year': 195, 'title': '曲阿破繇', 'description': '刘繇败走豫章，江东震动。', 'importance': 3},
  {'year': 196, 'title': '破严白虎', 'description': '下乌程破虎，虎奔余杭为凌操所杀。', 'importance': 2},
  {'year': 196, 'title': '奇袭会稽', 'description': '佯攻查渎夜袭，王朗败降，虞翻来归。', 'importance': 3},
  {'year': 196, 'title': '曹操表封', 'description': '操表策为讨逆将军、吴侯。', 'importance': 2},
 ],
 'passage_ids': refs(
  (15, '权为质当'), (15, '牛渚'), (15, '神亭'), (15, '太史慈'), (15, '严白虎'),
  (15, '查渎'), (15, '会稽'),
 ),
})
B({
 'id': 'jiangdong_pingding', 'name': '江东平定战', 'year': 195, 'date_text': '兴平二年（195）起',
 'place_id': 'qu_a', 'event_id': 'sun_ce_ding_jiangdong',
 'belligerents': [
  {'side': '孙策军', 'faction_ids': ['wu'], 'commanders': ['sun_ce', 'zhou_yu', 'cheng_pu', 'huang_gai', 'han_dang'], 'troops_desc': '借兵三千渡江，沿途收降扩军'},
  {'side': '刘繇·王朗·严白虎', 'faction_ids': ['warlord'], 'commanders': ['liu_yao', 'taishi_ci', 'wang_lang', 'yan_baihu'], 'troops_desc': '曲阿守军 + 会稽守军 + 乌程之众'},
 ],
 'result': '孙策尽有江东，吴国立基',
 'casualties_note': '张英死于陈武枪下、陈横死于蒋钦箭下、严白虎死于凌操之手。',
 'summary': '牛渚—秣陵—曲阿—吴郡—会稽，孙策数年连破刘繇、严白虎、王朗，尽定江东。',
 'detail': '策渡江首夺牛渚；攻曲阿，神亭与太史慈酣斗后擒之收服；繇败走豫章。下乌程破严白虎（弟严舆请和被杀）、虎走余杭被凌操所杀。会稽王朗固守，策用奇计夜出查渎，朗败降、虞翻来归。江东自此定。',
 'front_line': [
  nd(1, '渡江', '首夺牛渚', '以玉玺质术借兵三千，渡江首捷。', 'niu_zhu', 0, 0, 195),
  nd(2, '攻坚', '秣陵降礼', '薛礼、笮融屯秣陵拒之，城破礼死。', 'jian_ye', 0.03, 0.02, 195),
  nd(3, '会战', '曲阿破繇', '神亭酣斗收太史慈，繇败走豫章。', 'qu_a', -0.04, -0.03, 195),
  nd(4, '西进', '乌程破虎', '严白虎弟请和被杀，虎走余杭为凌操所杀。', 'wu_cheng', 0.04, 0.03, 196),
  nd(5, '奇袭', '夜出查渎', '佯攻查渎，夜袭王朗屯处。', 'cha_du', 0, 0, 196),
  nd(6, '定局', '会稽定', '朗败降，虞翻来归，江东遂定。', 'kuai_ji', -0.05, -0.03, 196),
 ],
})

# =============== 8. 衣带诏（199–200） ===============
A({
 'id': 'yidai_zhao', 'name': '衣带诏', 'kind': '政治事件',
 'start_year': 199, 'end_year': 200, 'date_text': '建安四年—五年（199–200）',
 'summary': '献帝以血书付董承，承与王子服等六人、马腾、刘备歃血为盟谋诛曹操；事泄三族被诛，董贵妃有孕亦被杀。',
 'detail': '许田打围，曹操「遮前欺后」僭越之礼毕露，关羽欲杀操、刘备止之。献帝泣付董承血诏，承归与王子服、吴子兰、种辑、吴硕密议，马腾、刘备相继入盟。备借截击袁术之名脱身徐州。建安五年事泄（家奴告变），操诛董承等三族，董贵妃有孕亦缢杀；刘备在徐州举兵反曹，马腾归西凉。',
 'place_id': 'xu_tian', 'parent_event_id': None,
 'participants': [
  {'person_id': 'liu_xie', 'role_desc': '献帝，泣血付诏'},
  {'person_id': 'dong_cheng', 'role_desc': '受诏首谋'},
  {'person_id': 'wang_zifu', 'role_desc': '六义士之一'},
  {'person_id': 'ma_teng', 'role_desc': '西凉太守，入盟'},
  {'person_id': 'liu_bei', 'role_desc': '入盟后借机脱身徐州'},
  {'person_id': 'cao_cao', 'role_desc': '许田僭越，事后族诛承等'},
  {'person_id': 'guan_yu', 'role_desc': '许田欲杀操，备止之'},
  {'person_id': 'fu_huanghou', 'role_desc': '与帝同忧'},
 ],
 'timeline': [
  {'year': 199, 'title': '许田打围', 'description': '操借天子仪仗遮前欺后，关羽欲杀操，备止之。', 'importance': 3},
  {'year': 199, 'title': '血诏付承', 'description': '献帝以血书付董承。', 'importance': 3},
  {'year': 199, 'title': '七人结盟', 'description': '承与王子服、马腾、刘备等歃血为盟。', 'importance': 3},
  {'year': 199, 'title': '备脱身徐州', 'description': '备借截击袁术之名领兵出许都。', 'importance': 2},
  {'year': 200, 'title': '事泄族诛', 'description': '家奴告变，操诛承等三族，董贵妃有孕亦死。', 'importance': 3},
 ],
 'passage_ids': refs(
  (20, '许田'), (20, '缝于玉带紫锦衬内'), (20, '董承'), (20, '玉带一条'), (20, '王子服'), (20, '马腾'),
 ),
})
B({
 'id': 'xutian_dawei', 'name': '许田打围', 'year': 199, 'date_text': '建安四年（199）',
 'place_id': 'xu_tian', 'event_id': 'yidai_zhao',
 'belligerents': [
  {'side': '曹操与汉臣', 'faction_ids': ['wei'], 'commanders': ['cao_cao'], 'troops_desc': '借天子仪仗'},
  {'side': '汉室（帝与诸臣）', 'faction_ids': ['han'], 'commanders': ['liu_xie'], 'troops_desc': '随驾'},
 ],
 'result': '曹操僭越毕露，汉臣自此知操必篡',
 'casualties_note': '无交战；关羽拔剑欲杀操被刘备摇手止之。',
 'summary': '操借天子仪仗打围，受贺僭越「遮前欺后」；关羽拍弓欲杀，备止之——汉曹决裂的标志性一幕。',
 'detail': '操请天子田猎以观动静。围场中操纵马直出遮于帝前迎受「万岁」之贺，僭越毕露。关羽剔起卧蚕眉、拍弓搭箭欲斩操，备摇手送目止之。操自此知帝与诸臣不平，遂有「许田打围」之议的朝局。',
 'front_line': [
  nd(1, '出猎', '借天子仪仗', '操请帝田猎，帝曰「欲观卿之武艺」。', 'xu_tian', 0, 0, 199),
  nd(2, '僭越', '遮帝受贺', '操纵马遮于帝前受「万岁」之贺。', 'xu_tian', 0.04, 0.02, 199),
  nd(3, '杀机', '云长欲斩', '关羽拍弓欲杀，备摇手止之。', 'xu_tian', -0.04, -0.03, 199),
 ],
})

# ---------- 校验并写出 ----------
for e in events:
    check_ids(e['participants'])
    for p in e['passage_ids']:
        if p not in pids.values():
            raise SystemExit('事件 %s 引用了不存在的段落 %s' % (e['id'], p))
for b in battles:
    for side in b['belligerents']:
        check_cmd_ids(side['commanders'])
    for i in range(len(b['front_line']) - 1):
        assert b['front_line'][i]['time'] <= b['front_line'][i + 1]['time'], b['id']

out = {
 'comment': 'P1-G（2026-10-27）：第 11–20 回的 8 组事件 + 6 场战役。passage_ids 由 scripts/gen_events_p1e.py 从构建产物解析生成，禁止手改。',
 'events': events, 'battles': battles,
}
io.open(os.path.join(DATA, 'event_battle_ch011_020.json'), 'w', encoding='utf-8').write(
    json.dumps(out, ensure_ascii=False, indent=1))
print('生成事件 %d 组、战役 %d 场、战线节点 %d 个' % (
    len(events), len(battles), sum(len(b['front_line']) for b in battles)))
for e in events:
    print('  事件 %-26s 段落 %d 处  人物 %d' % (e['id'], len(e['passage_ids']), len(e['participants'])))
for b in battles:
    print('  战役 %-26s 节点 %d  挂 %s' % (b['id'], len(b['front_line']), b['event_id']))
