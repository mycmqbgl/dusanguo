#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P1-D：生成第 2–10 回的 9 组事件 + 6 场战役（data/event_battle_ch002_010.json）。

用法：先跑一次 build.py（让新地名拿到像素坐标），再跑本脚本，再跑一次 build.py。

设计约束：
- passage_ids 不手填。每个出处写成 (回数, 关键词)，脚本在 build/chapters 里解析出
  段落 id 并断言命中——关键词对不上时直接报错退出，杜绝「事件卡死链」。
- participants 只允许引用已建档的 person id，脚本会断言（112 卡之外的人引用了也不报，
  但会在人名档案里找不到卡，事件卡上显示 id，所以必须拦）。
- front_line 的 lng/lat 从 build/places.json 按地名取，允许 ±0.06° 的手工偏移，
  避免同点多节点完全重叠。
"""
import json, io, os, re, sys, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, 'build')
DATA = os.path.join(ROOT, 'data')

# ---------- 读取构建产物 ----------
places = {p['id']: p for p in json.load(io.open(os.path.join(BUILD, 'places.json'), encoding='utf-8'))}
passages = {}   # (no, seq) -> text
pids = {}       # (no, seq) -> id
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
    """(回数, 关键词) → 段落 id。关键词须在该回某段中唯一或首段命中。"""
    hits = [(s, t) for (n, s), t in passages.items() if n == no and kw in t]
    if not hits:
        raise SystemExit('出处解析失败：第 %d 回找不到关键词「%s」' % (no, kw))
    return pids[(no, hits[0][0])]


def refs(*pairs):
    return [ref(n, k) for n, k in pairs]


def coords(place_id, dx=0.0, dy=0.0):
    p = places[place_id]
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
A = events.append
B = battles.append

# =============== 1. 十常侍之乱（189） ===============
A({
 'id': 'shi_chang_shi_zhi_luan', 'name': '十常侍之乱', 'kind': '宫廷政变',
 'start_year': 189, 'end_year': 189, 'date_text': '中平六年（189）四月—八月',
 'summary': '灵帝崩，蹇硕谋立刘协不成；大将军何进谋诛宦官反被张让所杀，袁绍尽诛宦官，张让劫少帝出奔北邙山——外兵董卓趁虚入京。',
 'detail': '十常侍（张让、赵忠、封谞、段珪等）把持朝政，卖官鬻爵。灵帝崩后蹇硕欲先诛何进再立皇子协，事泄被袁绍收斩。何进既立外甥刘辩，欲尽诛宦官，太后不许；袁绍献策召外兵入京胁迫，曹操谏「但付一狱吏足矣」，进不听，密诏董卓等进京。张让等先发制人，诱何进入宫杀之。袁绍、曹操引兵入宫，见宦者皆杀，张让、段珪劫少帝与陈留王夜奔北邙山，闵贡追及，张让投水自尽。帝还宫途中，董卓率西凉大军迎驾——外戚与宦官同归于尽，朝权落入董卓之手。',
 'place_id': 'luo_yang', 'parent_event_id': None,
 'participants': [
  {'person_id': 'he_jin', 'role_desc': '大将军，谋诛宦官反被杀'},
  {'person_id': 'zhang_rang', 'role_desc': '十常侍之首，诱杀何进后投水自尽'},
  {'person_id': 'jian_shuo', 'role_desc': '上军校尉，欲先诛何进再立刘协，事泄被杀'},
  {'person_id': 'he_taihou', 'role_desc': '何太后，袒护宦官，拒诛常侍'},
  {'person_id': 'dong_taihou', 'role_desc': '董太后，与何后争权，被鸩杀于河间驿庭'},
  {'person_id': 'yuan_shao', 'role_desc': '司隶校尉，献召外兵之策，入宫尽诛宦官'},
  {'person_id': 'cao_cao', 'role_desc': '典军校尉，谏「但付一狱吏足矣」，不听'},
  {'person_id': 'liu_bian', 'role_desc': '少帝，被劫出奔北邙山'},
  {'person_id': 'liu_xie', 'role_desc': '陈留王，随少帝出奔，应对从容'},
 ],
 'timeline': [
  {'year': 189, 'title': '灵帝崩，蹇硕谋废立', 'description': '帝召何进入宫托后事而崩。蹇硕与十常侍密议先诛何进再立皇子协，潘隐告变，何进称病不入。', 'importance': 3},
  {'year': 189, 'title': '少帝即位，蹇硕被收', 'description': '刘辩即位，何太后临朝。袁绍入宫收蹇硕，禁军尽投顺。', 'importance': 2},
  {'year': 189, 'title': '鸩杀董后', 'description': '何进使人鸩杀董太后于河间驿庭。', 'importance': 2},
  {'year': 189, 'title': '召外兵胁迫', 'description': '袁绍献「召四方英雄之士，勒兵来京」之策，曹操谏而不纳，何进密诏董卓等进京。', 'importance': 3},
  {'year': 189, 'title': '何进被杀', 'description': '张让、段珪诱何进入嘉德殿，左右围而杀之。', 'importance': 3},
  {'year': 189, 'title': '尽诛宦官', 'description': '袁绍、曹操引兵入宫，见宦者皆杀，无须者误杀无数。', 'importance': 3},
  {'year': 189, 'title': '帝奔北邙山', 'description': '张让、段珪劫少帝与陈留王夜奔北邙山，闵贡追及，张让投水，段珪被杀。', 'importance': 3},
  {'year': 189, 'title': '董卓迎驾', 'description': '董卓以「护驾」之名迎帝还宫，自此兵权在手。', 'importance': 3},
 ],
 'passage_ids': refs(
  (2, '中平六年夏四月'), (2, '秘不发丧'), (2, '袁绍入宫收蹇硕'),
  (2, '却说十常侍既握重权'), (2, '谏议大夫刘陶'), (2, '何进暗使人鸩杀董后'),
  (3, '主簿陈琳谏'), (3, '张让、段珪迎出'), (3, '首级从墙上掷出'),
  (3, '劫拥少帝'), (3, '闵贡赶上段珪'), (3, '旌旗蔽日'),
 ),
})
B({
 'id': 'bei_mang_shan_bian', 'name': '北邙山之变', 'year': 189, 'date_text': '中平六年（189）八月',
 'place_id': 'bei_mang_shan', 'event_id': 'shi_chang_shi_zhi_luan',
 'belligerents': [
  {'side': '宦官余党', 'faction_ids': ['han'], 'commanders': ['zhang_rang', 'duan_gui'], 'troops_desc': '劫持车驾数十人'},
  {'side': '追兵（河南中部掾）', 'faction_ids': ['han'], 'commanders': ['min_gong'], 'troops_desc': '追兵步骑数十'},
 ],
 'result': '宦官覆灭，帝驾为董卓所迎',
 'casualties_note': '张让投水自尽，段珪被杀；此役无正规交战，是宦官集团的终点。',
 'summary': '张让、段珪劫少帝与陈留王夜奔北邙山，闵贡追至，张让投水；董卓随后迎驾还宫，攫取朝权。',
 'detail': '何进被杀后袁绍纵兵诛宦，张让、段珪劫少帝及陈留王冒烟突火连夜奔走至北邙山。二更时分闵贡等追及，段珪分途被擒；张让见事穷，投河而死。帝与陈留王伏于河岸边草堆中至四更，被闵贡寻获，扶驾而行——正遇董卓大军，帝惊不能答，陈留王厉声应对，董卓自此暗有废立之意。这夜是外戚、宦官两大集团同归于尽的终点，也是董卓时代的起点。',
 'front_line': [
  nd(1, '起事', '宫中出逃', '张让、段珪劫少帝与陈留王，冒烟突火连夜奔走。', 'luo_yang', 0.02, 0.01, 189),
  nd(2, '奔逃', '夜至北邙山', '约二更时分，避入山中，饥寒交迫，伏于岸边草堆。', 'bei_mang_shan', 0, 0, 189),
  nd(3, '追及', '闵贡追至', '贡赶段珪问天子何在，段珪被杀，张让投水。', 'bei_mang_shan', 0.05, -0.03, 189),
  nd(4, '结局', '董卓迎驾', '帝与陈留王还宫途中，为董卓大军所「迎」，朝权自此易手。', 'bei_mang_shan', -0.06, 0.04, 189),
 ],
})

# =============== 2. 董卓废立（189） ===============
A({
 'id': 'dong_zhuo_fei_li', 'name': '董卓废立', 'kind': '政治事件',
 'start_year': 189, 'end_year': 190, 'date_text': '中平六年（189）九月—初平元年（190）正月',
 'summary': '董卓以「天子暗弱，不可以奉宗庙」废少帝为弘农王、立陈留王刘协，自专朝政；丁原、袁绍、卢植反抗者或死或走，何太后与弘农王随后遇害。',
 'detail': '董卓迎驾还宫后招诱何进兄弟部曲，兵势大盛。私谓李儒「吾欲废帝立陈留王」，儒曰「今朝廷无主，正可就此行之」。省中设宴议废立，丁原挺身反对，卓欲杀之，见其背后吕布持戟而止；李肃以赤兔马与金珠说吕布杀丁原来降。次日再议，袁绍横剑而出，奔冀州；卢植抗声谏，卓欲杀之，蔡邕、彭伯救之，罢官。九月朔，卓请帝登台，宣策废刘辩为弘农王、立陈留王，自为相国，赞拜不名、入朝不趋、剑履上殿。随后使人鸩杀弘农王与何太后。废立是董卓由权臣到国贼的转折点，直接引发曹操献刀与十八路诸侯讨董。',
 'place_id': 'luo_yang', 'parent_event_id': None,
 'participants': [
  {'person_id': 'dong_zhuo', 'role_desc': '相国，主持废立，自专朝政'},
  {'person_id': 'li_ru', 'role_desc': '谋主，「正可就此行之」'},
  {'person_id': 'lv_bu', 'role_desc': '杀丁原来降，为卓爪牙'},
  {'person_id': 'li_su', 'role_desc': '以赤兔马与金珠说降吕布'},
  {'person_id': 'ding_yuan', 'role_desc': '荆州刺史，挺身反对废立，被吕布所杀'},
  {'person_id': 'yuan_shao', 'role_desc': '「汝剑利，吾剑未尝不利」，横剑出奔冀州'},
  {'person_id': 'lu_zhi', 'role_desc': '抗声直谏，罢官（得蔡邕、彭伯所救）'},
  {'person_id': 'liu_bian', 'role_desc': '被废为弘农王，后遭鸩杀'},
  {'person_id': 'liu_xie', 'role_desc': '立为帝，是为献帝'},
  {'person_id': 'he_taihou', 'role_desc': '被迁永安宫，随后遇害'},
 ],
 'timeline': [
  {'year': 189, 'title': '私议废立', 'description': '卓谓李儒「吾欲废帝立陈留王」，儒曰「今朝廷无主，正可就此行之」。', 'importance': 3},
  {'year': 189, 'title': '丁原抗命', 'description': '省中设宴议废立，丁原挺身反对，卓欲杀之而惮其身后吕布。', 'importance': 2},
  {'year': 189, 'title': '吕布杀丁原', 'description': '李肃赍赤兔马、金珠说吕布；布夜杀丁原，持首级来降，拜卓为义父。', 'importance': 3},
  {'year': 189, 'title': '袁绍出走', 'description': '再议废立，袁绍厉声反对，「汝剑利，吾剑未尝不利」，横剑而去，奔冀州。', 'importance': 3},
  {'year': 189, 'title': '废帝立协', 'description': '九月朔，宣策废刘辩为弘农王，立陈留王刘协，是为献帝。卓自为相国。', 'importance': 3},
  {'year': 190, 'title': '鸩杀弘农王', 'description': '李儒以鸩酒杀弘农王于永安宫，何太后、唐妃同殉。', 'importance': 3},
 ],
 'passage_ids': refs(
  (3, '吾欲废帝立陈留王'), (3, '掣佩剑欲斩丁原'), (3, '号曰赤兔'),
  (3, '省中设宴'), (4, '袁绍手提宝剑'), (4, '孝灵皇帝，早弃臣民'),
  (4, '卓请陈留王登殿'), (4, '怨望作诗'),
 ),
})

# =============== 3. 孟德献刀（189） ===============
A({
 'id': 'meng_de_xian_dao', 'name': '孟德献刀', 'kind': '刺杀事件',
 'start_year': 189, 'end_year': 189, 'date_text': '中平六年（189）冬',
 'summary': '曹操持王允七宝刀入相府行刺董卓，事败托名献刀，逃出洛阳，中牟被擒得陈宫相释，误杀吕伯奢一家——「宁教我负天下人」定其枭雄底色。',
 'detail': '董卓欺主弄权，王允寿宴上旧臣痛哭。曹操自请借七宝刀入相府刺卓：卓倒身而卧，操拔刀欲刺，卓见衣镜中刀光回身，吕布已牵马至阁外。操急持刀跪下曰「操有宝刀一口，献上恩相」，托词脱身，出城飞马而逃。卓省悟，画影图形遍行文书捉拿。操至中牟为县令陈宫所擒，宫闻其讨贼之志，弃官同逃。至成皋吕伯奢庄上，闻磨刀之声疑其加害，遂杀其家八口；出见伯奢沽酒归来，亦杀之。宫责之，操曰「宁教我负天下人，休教天下人负我」。宫见操是狼心之徒，弃之而走。',
 'place_id': 'luo_yang', 'parent_event_id': None,
 'participants': [
  {'person_id': 'cao_cao', 'role_desc': '行刺者，事败后亡命兖州'},
  {'person_id': 'dong_zhuo', 'role_desc': '被刺者，衣镜中见刀光'},
  {'person_id': 'lv_bu', 'role_desc': '牵马至阁外，恰好撞破行刺时机'},
  {'person_id': 'li_ru', 'role_desc': '谏卓「操无家小，宜召问之」'},
  {'person_id': 'wang_yun', 'role_desc': '借出七宝刀（寿宴定计）'},
  {'person_id': 'chen_gong', 'role_desc': '中牟县令，释操并弃官同逃，后弃之而去'},
  {'person_id': 'cao_song', 'role_desc': '操父，操亡命时投奔陈留其家（起兵资助出自卫弘）'},
 ],
 'timeline': [
  {'year': 189, 'title': '寿宴定计', 'description': '王允寿宴上旧臣相对而哭，曹操自请借七宝刀往刺董卓。', 'importance': 3},
  {'year': 189, 'title': '献刀脱身', 'description': '操拔刀欲刺，卓见镜中刀光回身；布牵马至。操托名献刀，飞马出东门。', 'importance': 3},
  {'year': 189, 'title': '画影图形', 'description': '李儒提醒「操必有异」，卓悟，遍行文书捉拿曹操。', 'importance': 2},
  {'year': 189, 'title': '中牟被擒', 'description': '操为中牟军士所获，县令陈宫闻其志，亲释其缚，弃官同逃。', 'importance': 2},
  {'year': 189, 'title': '误杀吕伯奢', 'description': '成皋庄上闻磨刀声而尽杀其家，复杀伯奢。「宁教我负天下人」出自此处。', 'importance': 3},
  {'year': 189, 'title': '陈宫弃操', 'description': '宫见操「狼心之徒」，本欲杀之，念「为国家可惜此人」，弃之自去。', 'importance': 2},
 ],
 'passage_ids': refs(
  (4, '今日老夫贱降'), (4, '曹操佩着宝刀'), (4, '适来曹操似有行刺之状'),
  (4, '操与宫坐久'),
 ),
})

# =============== 4. 十八路诸侯讨董（190–191） ===============
tao_dong_id = 'tao_dong_shi_ba_lu'
A({
 'id': tao_dong_id, 'name': '十八路诸侯讨董', 'kind': '军事行动',
 'start_year': 190, 'end_year': 191, 'date_text': '初平元年（190）正月—二年（191）',
 'summary': '曹操发矫诏，十八路诸侯会盟共讨董卓，袁绍为盟主。孙坚先破汜水关，刘关张虎牢关前战吕布；董卓焚洛阳迁都长安，联军队形涣散，止于虎牢——讨董无功而散。',
 'detail': '曹操逃归陈留，得卫弘资助，矫诏发丧，檄文告天下。十八路诸侯应诏而至，袁绍凭四世三公之望被推为盟主，歃血为誓。孙坚请为前部攻汜水关：鲍信暗拨其弟鲍忠抢功被斩；袁术不发粮草，孙坚军自乱，被华雄掩杀，祖茂换帻死之。华雄下关搦战，连斩数将，关羽温酒斩华雄。董卓亲与吕布领十五万屯虎牢关：吕布连败方悦、穆顺、武安国，公孙瓒亦败走，张飞出战，刘关张三英合围，吕布败退上关。董卓纳李儒之议焚洛阳宫室、迁都长安，挟数百万口西行；曹操请追击，诸侯不从，操独引兵追至荥阳，中徐荣之伏大败，曹洪让马得免。孙坚先入洛阳，救灭宫火——联军名义上是讨逆，实际各怀异心，盟约自此瓦解。',
 'place_id': 'chen_liu', 'parent_event_id': None,
 'participants': [
  {'person_id': 'cao_cao', 'role_desc': '发矫诏起兵，后独追董卓败于荥阳'},
  {'person_id': 'yuan_shao', 'role_desc': '盟主，屯河内'},
  {'person_id': 'yuan_shu', 'role_desc': '总督粮草，不发孙坚粮秣致其军自乱'},
  {'person_id': 'sun_jian', 'role_desc': '前部先锋，攻汜水关，先入洛阳'},
  {'person_id': 'hua_xiong', 'role_desc': '董卓部将，下关搦战，为关羽所斩'},
  {'person_id': 'lv_bu', 'role_desc': '虎牢关前连败联军数将，为三英所退'},
  {'person_id': 'dong_zhuo', 'role_desc': '焚洛阳、迁长安'},
  {'person_id': 'li_ru', 'role_desc': '谋主，献迁都之策'},
  {'person_id': 'li_jue', 'role_desc': '与郭汜引兵五万把住汜水关'},
  {'person_id': 'guo_si', 'role_desc': '同守汜水关'},
  {'person_id': 'xu_rong', 'role_desc': '荥阳太守，伏兵大败曹操'},
  {'person_id': 'gongsun_zan', 'role_desc': '北平太守，携刘关张赴盟'},
  {'person_id': 'liu_bei', 'role_desc': '随瓒赴盟，虎牢关前三英战吕布'},
  {'person_id': 'guan_yu', 'role_desc': '温酒斩华雄；虎牢关合战吕布'},
  {'person_id': 'zhang_fei', 'role_desc': '虎牢关首先出战吕布'},
  {'person_id': 'bao_xin', 'role_desc': '济北相，暗拨其弟鲍忠抢功，被华雄斩之'},
 ],
 'timeline': [
  {'year': 190, 'title': '矫诏起兵', 'description': '曹操归陈留，得卫弘资财，发矫诏，檄文遍告天下。', 'importance': 3},
  {'year': 190, 'title': '十八镇应诏', 'description': '十八路诸侯各领兵赴会，兵各数万，营寨连接二百余里。', 'importance': 3},
  {'year': 190, 'title': '歃血立盟', 'description': '袁绍为盟主，其弟袁术总督粮草，长沙孙坚请为前部。', 'importance': 3},
  {'year': 190, 'title': '汜水折将', 'description': '鲍忠抢功被斩；袁术断粮，坚军自乱，华雄掩杀，祖茂死之。', 'importance': 2},
  {'year': 190, 'title': '温酒斩华雄', 'description': '华雄搦战连斩数将，关羽出阵，酒尚温时斩华雄回报。', 'importance': 3},
  {'year': 190, 'title': '三英战吕布', 'description': '吕布连败联军四将，张飞出战，刘关张合围，布败退上关。', 'importance': 3},
  {'year': 190, 'title': '焚洛阳迁都', 'description': '卓纳李儒之议，尽驱洛阳之民西赴长安，焚烧宗庙宫府。', 'importance': 3},
  {'year': 190, 'title': '荥阳中伏', 'description': '诸侯不肯追击，曹操独引兵追至荥阳，中徐荣之伏大败，曹洪让马得免。', 'importance': 2},
  {'year': 191, 'title': '盟散', 'description': '孙坚入洛阳救火，得传国玉玺而匿之；联军各归本镇，盟约瓦解。', 'importance': 2},
 ],
 'passage_ids': refs(
  (5, '操等谨以大义布告天下'), (5, '第一镇，后将军南阳太守袁术'),
  (5, '且说北平太守公孙瓒'), (5, '读毕歃血'), (5, '长沙太守孙坚出曰'),
  (5, '华雄引铁骑下关'), (5, '卓遂起兵二十万'), (5, '董卓屯兵虎牢'),
  (5, '翻身飞上虎牢关'), (6, '儒曰："温侯新败'), (6, '放火烧宗庙宫府'),
  (6, '董卓行至荥阳'), (6, '人报曹操追董卓'),
 ),
})
B({
 'id': 'si_shui_guan_zhi_zhan', 'name': '汜水关之战', 'year': 190, 'date_text': '初平元年（190）正月—二月',
 'place_id': 'si_shui_guan', 'event_id': tao_dong_id,
 'belligerents': [
  {'side': '关东联军', 'faction_ids': ['warlord'], 'commanders': ['sun_jian', 'guan_yu', 'zu_mao', 'cheng_pu', 'huang_gai', 'han_dang'], 'troops_desc': '孙坚本部为前部，另有鲍忠一支'},
  {'side': '董卓军', 'faction_ids': ['warlord'], 'commanders': ['hua_xiong', 'li_jue', 'guo_si'], 'troops_desc': '李傕、郭汜五万把关，华雄为骁将'},
 ],
 'result': '联军胜（华雄被斩），此前孙坚两度受挫',
 'casualties_note': '联军折鲍忠、祖茂；董卓军折华雄。演义写孙坚「帻落」由祖茂代死，史实为华雄败于孙坚（演义归功关羽，孙坚卡已注明）。',
 'summary': '孙坚攻汜水关先胜后败（袁术断粮），华雄下关搦战连斩联军数将，关羽温酒斩华雄，关前大振。',
 'detail': '孙坚请为前部，杀奔汜水关。鲍信怕孙坚夺头功，暗遣其弟鲍忠先趋关下搦战，被华雄手起刀落斩之。坚大破关上守军，遣使报捷并催粮——袁术忌坚，不发粮草，坚军自乱，李肃乘乱掩杀，坚折了祖茂（茂换其赤帻引开追兵）。华雄遂下关搦战，以长竿挑孙太守赤帻，连斩袁绍部将，众诸侯失色；关羽请战，曹操斟热酒一杯，云长停盏而出，「酒且斟下，某去便来」——出帐提刀，飞身上马，众诸侯听得关外鼓声大振、喊声大举，云长提华雄之头掷于地上，「其酒尚温」。',
 'front_line': [
  nd(1, '集结', '诸侯屯酸枣', '十八路诸侯陆续到齐，营寨连接二百余里。', 'suan_zao', 0, 0, 190),
  nd(2, '行军', '坚为前部', '孙坚引程普、黄盖、韩当四将杀奔汜水关来。', 'si_shui_guan', 0.05, 0.03, 190),
  nd(3, '受挫', '华雄掩杀', '鲍忠抢功被斩；袁术断粮，坚军自乱，华雄夜袭，祖茂战死。', 'si_shui_guan', -0.03, 0.04, 190),
  nd(4, '搦战', '雄挑赤帻', '华雄引铁骑下关，以长竿挑孙太守赤帻，连斩联军诸将。', 'si_shui_guan', 0.04, -0.04, 190),
  nd(5, '决战', '温酒斩华雄', '关羽出阵，鼓声大振处提华雄之头掷于地上，其酒尚温。', 'si_shui_guan', -0.05, -0.02, 190),
 ],
})
B({
 'id': 'hu_lao_guan_zhi_zhan', 'name': '虎牢关之战', 'year': 190, 'date_text': '初平元年（190）',
 'place_id': 'hu_lao_guan', 'event_id': tao_dong_id,
 'belligerents': [
  {'side': '关东联军', 'faction_ids': ['warlord'], 'commanders': ['yuan_shao', 'cao_cao', 'liu_bei', 'guan_yu', 'zhang_fei', 'gongsun_zan', 'wang_kuang'], 'troops_desc': '八路诸侯分八队迎敌'},
  {'side': '董卓军', 'faction_ids': ['warlord'], 'commanders': ['dong_zhuo', 'lv_bu', 'li_ru'], 'troops_desc': '十五万，吕布领三万为先锋'},
 ],
 'result': '吕布败退上关，联军不能进',
 'casualties_note': '联军折方悦（一合）、穆顺（一合）、武安国（断腕）；演义「三英战吕布」为虚构名场面，史无其事（卡片已注）。',
 'summary': '吕布虎牢关前连败联军数将，张飞出战、关羽夹攻、刘备掣双股剑，三英合围，吕布倒拖画戟退上虎牢关。',
 'detail': '董卓起兵二十万：李傕、郭汜把住汜水关，自与吕布领十五万屯虎牢关，截联军中路。吕布搦战，八路诸侯齐出——河内王匡部将方悦战不五合被刺于马下；张杨部将穆顺被一戟刺穿咽喉；孔融部将武安国使铁锤战十余合被砍断手腕。公孙瓒亲战吕布，数合即败走，布纵赤兔马赶来，张飞圆睁环眼、倒竖虎须，挺丈八蛇矛出战，连斗五十余合不分胜负；关羽掣青龙偃月刀夹攻，三十合战不倒吕布；刘备掣双股剑骤马助战——三英围住吕布，转灯儿般厮杀。布遮拦不住，虚刺一戟，倒拖画杆方天戟飞马而回，诸侯掩杀，卓兵大败退上虎牢关。',
 'front_line': [
  nd(1, '对峙', '分兵把关', '李傕、郭汜把汜水关；董卓与吕布自领大军屯虎牢关。', 'si_shui_guan', -0.02, -0.02, 190),
  nd(2, '集结', '董卓屯虎牢', '卓军十五万据关，截联军中路，袁绍聚众商议。', 'hu_lao_guan', 0, 0, 190),
  nd(3, '搦战', '吕布连斩三将', '方悦五合被刺、穆顺一戟毙命、武安国断腕而逃。', 'hu_lao_guan', 0.04, 0.03, 190),
  nd(4, '决战', '三英战吕布', '张飞先出，关羽夹攻，刘备掣剑——三英围住吕布厮杀。', 'hu_lao_guan', -0.05, 0.02, 190),
  nd(5, '败退', '布走上关', '吕布虚刺一戟，倒拖画戟飞马而回，卓兵大败。', 'hu_lao_guan', 0.03, -0.04, 190),
 ],
})
B({
 'id': 'xing_yang_fu_ji_zhan', 'name': '荥阳伏击战', 'year': 190, 'date_text': '初平元年（190）二月',
 'place_id': 'xing_yang', 'event_id': tao_dong_id,
 'belligerents': [
  {'side': '曹操部', 'faction_ids': ['warlord'], 'commanders': ['cao_cao', 'xiahou_dun'], 'troops_desc': '万余人（独追）'},
  {'side': '董卓军', 'faction_ids': ['warlord'], 'commanders': ['xu_rong', 'li_ru'], 'troops_desc': '荥阳太守徐荣伏军城外山坞'},
 ],
 'result': '董卓军胜，曹操大败',
 'casualties_note': '操中箭中枪，坐骑被擒；曹洪让马、负操渡河得免。「曹操中徐荣伏兵」史有明文，演义细节（洪让马）与史略同而文学化。',
 'summary': '诸侯不肯追击，曹操独引兵追董卓；至荥阳中徐荣之伏，大败，曹洪让马扶操渡河，仅以身免。',
 'detail': '董卓焚洛阳西走，曹操请袁绍「追击其半」，诸侯皆言「不可轻动」。操怒曰「竖子不足与谋」，自引万余人追击。李儒早料「操必有奇兵」，教徐荣伏军荥阳城外山坞之旁。操军至，伏兵四出，徐荣杀得操大败：中箭中枪，为徐荣所擒（演义写两军相夺操之坐骑），曹洪舍命让马——「天下可无洪，不可无公」——扶操下渡过黄河。操归营，见诸侯置酒高会，愤而出走，自此与联军分道。',
 'front_line': [
  nd(1, '西走', '焚洛阳弃城', '卓焚宫室、驱百万口西赴长安，留徐荣断后设伏。', 'luo_yang', 0.03, 0, 190),
  nd(2, '设伏', '伏军山坞', '李儒教徐荣伏军荥阳城外山坞之旁，以待追兵。', 'xing_yang', -0.04, 0.02, 190),
  nd(3, '追击', '操军轻进', '诸侯不从，操独引万余人连夜追来。', 'xing_yang', 0.03, -0.03, 190),
  nd(4, '伏发', '大败中箭', '伏兵四出，操中箭中枪，坐骑被夺，赖曹洪让马得免。', 'xing_yang', 0.05, 0.03, 190),
  nd(5, '败归', '愤别联军', '操归营见诸侯置酒高会，愤而出走，联军自此离析。', 'suan_zao', 0, 0, 190),
 ],
})

# =============== 5. 孙坚匿玺（191） ===============
A({
 'id': 'sun_jian_ni_xi', 'name': '孙坚匿玺', 'kind': '政治事件',
 'start_year': 191, 'end_year': 191, 'date_text': '初平二年（191）',
 'summary': '孙坚入洛阳救火，于南殿井中得传国玉玺，匿而辞归江东；袁绍索之不得，密令刘表于路截击——孙刘由此结怨，埋下孙坚之死。',
 'detail': '孙坚先入洛阳，救灭宫火，屯兵城内。建章殿南井中五色毫光起，军士捞起一妇人尸，项下锦囊内有传国玉玺——方圆四寸，上镌五龙交纽，缺一角以黄金镶之，乃昔年张让作乱投井之物。程普曰「今天授主公，必有登九五之分」，劝坚速归江东别图大事。坚曰「吾自有之」，托病辞归。军士中有袁绍乡人，夜出告绍。绍索玺，坚指天为誓「吾若有此物，死于刀箭之下」；绍出 「军士」对质，坚拔剑欲斩之，二人于阵前几乎火并——坚遂引兵离洛阳，归路必经荆州。绍密书刘表，教就路上截而夺之。坚至，表不肯还玺，两军相攻，孙刘自此结下死仇。',
 'place_id': 'luo_yang', 'parent_event_id': None,
 'participants': [
  {'person_id': 'sun_jian', 'role_desc': '得玺者，指天为誓而匿之'},
  {'person_id': 'cheng_pu', 'role_desc': '「天授主公，必登九五」，劝速归江东'},
  {'person_id': 'yuan_shao', 'role_desc': '索玺不得，密令刘表截击'},
  {'person_id': 'liu_biao', 'role_desc': '受绍之托，于路截击孙坚'},
  {'person_id': 'cai_mao', 'role_desc': '刘表部将，出城迎击'},
 ],
 'timeline': [
  {'year': 191, 'title': '井中得玺', 'description': '建章殿南井中捞起传国玉玺，缺角以金镶之。', 'importance': 3},
  {'year': 191, 'title': '程普劝归', 'description': '「今天授主公，必有登九五之分」，劝坚速归江东。', 'importance': 2},
  {'year': 191, 'title': '指天为誓', 'description': '袁绍索玺，坚誓「吾若有此物，死于刀箭之下」，几乎阵前火并。', 'importance': 3},
  {'year': 191, 'title': '密令截击', 'description': '绍密书刘表，教于路夺玺；孙刘自此结怨。', 'importance': 3},
 ],
 'passage_ids': refs(
  (6, '五色毫光起于井中'), (6, '连夜偷出营寨'), (6, '汝匿传国玺'),
  (6, '玉玺得来无用处'),
 ),
})

# =============== 6. 磐河之战（191–192） ===============
A({
 'id': 'pan_he_xiang_zheng', 'name': '磐河相争（界桥之战）', 'kind': '军事行动',
 'start_year': 191, 'end_year': 192, 'date_text': '初平二年（191）—三年（192）',
 'summary': '袁绍用逢纪之策赚取冀州，又杀公孙越激怒公孙瓒；两军会于磐河，麴义斩严纲、瓒军大败，赵云突阵救主，刘关张来援，绍败走——董卓假天子诏和解。',
 'detail': '袁绍屯河内缺粮，逢纪献策「智取冀州」：密约公孙瓒共攻韩馥，馥惧，果如绍愿让出冀州。瓒遣弟公孙越来分地，绍使麴义暗杀之（演义写越为乱箭所杀而归罪于董卓），瓒大怒起兵。两军会于磐河：绍军桥东，瓒军桥西。瓒以白马义从为锋，严纲为先锋；麴义伏兵盾下，斩严纲，瓒军大败。瓒奔桥时绍铁骑合围，危急之际赵云单骑突阵救主（云新投瓒而不得重用）。正酣战间刘关张引兵冲阵，绍军溃退。相拒月余，董卓以和解为名（实为笼络），假天子诏封二人官，各罢兵。此战让赵云看清瓒「非可托之人」，为后来归刘备伏笔。',
 'place_id': 'pan_he', 'parent_event_id': None,
 'participants': [
  {'person_id': 'yuan_shao', 'role_desc': '赚取冀州，磐河桥东'},
  {'person_id': 'feng_ji', 'role_desc': '献「智取冀州」之策'},
  {'person_id': 'han_fu', 'role_desc': '冀州牧，畏瓒而让州于绍'},
  {'person_id': 'gongsun_zan', 'role_desc': '弟公孙越被杀，起兵攻绍，磐河桥西'},
  {'person_id': 'qu_yi', 'role_desc': '绍部将，伏盾斩严纲，大破瓒军'},
  {'person_id': 'tian_feng', 'role_desc': '绍谋士，劝绍坚守'},
  {'person_id': 'zhao_yun', 'role_desc': '新投瓒不得重用，单骑突阵救瓒'},
  {'person_id': 'liu_bei', 'role_desc': '应瓒之请引兵来援'},
  {'person_id': 'guan_yu', 'role_desc': '与张飞同来援，冲阵击退绍军'},
  {'person_id': 'zhang_fei', 'role_desc': '同来援'},
 ],
 'timeline': [
  {'year': 191, 'title': '智赚冀州', 'description': '逢纪献策，密约瓒攻馥；馥惊惧，以州让绍。绍自领冀州牧。', 'importance': 3},
  {'year': 191, 'title': '公孙越之死', 'description': '瓒遣弟越来分地，越为「乱箭」所杀（演义归罪董卓），瓒怒而兴兵。', 'importance': 2},
  {'year': 191, 'title': '会于磐河', 'description': '两军会于磐河之上，绍军桥东、瓒军桥西，隔河相拒。', 'importance': 3},
  {'year': 191, 'title': '麴义斩严纲', 'description': '瓒以白马义从冲阵，麴义伏兵盾下突起，斩严纲，瓒军大败。', 'importance': 3},
  {'year': 191, 'title': '赵云救主', 'description': '绍兵合围，瓒几不能免；赵云单骑突入，护瓒且战且退。', 'importance': 3},
  {'year': 191, 'title': '三雄来援', 'description': '刘关张引兵冲阵，绍军溃退。云与备相见恨晚，已有相从之意。', 'importance': 2},
  {'year': 192, 'title': '诏和罢兵', 'description': '相拒月余，董卓假天子诏和解，二人各罢兵。', 'importance': 2},
 ],
 'passage_ids': refs(
  (7, '且说袁绍屯兵河内'), (7, '馥慌聚荀谌'), (7, '遣弟公孙越来见绍'),
  (7, '二军会于磐河'), (7, '瓒将军马分作左右两队'), (7, '令其另领一军在后'),
  (7, '回报麴义斩将搴旗'), (7, '闪出一彪人马'), (7, '有人来长安报知董卓'),
 ),
})
B({
 'id': 'pan_he_zhi_zhan', 'name': '磐河·界桥之战', 'year': 191, 'date_text': '初平二年（191）冬',
 'place_id': 'pan_he', 'event_id': 'pan_he_xiang_zheng',
 'belligerents': [
  {'side': '公孙瓒（幽州）', 'faction_ids': ['warlord'], 'commanders': ['gongsun_zan', 'zhao_yun', 'liu_bei', 'guan_yu', 'zhang_fei'], 'troops_desc': '燕、代之众，白马义从为锋'},
  {'side': '袁绍（冀州）', 'faction_ids': ['warlord'], 'commanders': ['yuan_shao', 'qu_yi', 'tian_feng', 'feng_ji'], 'troops_desc': '新并韩馥之众，弩兵伏盾'},
 ],
 'result': '前段袁绍胜（斩严纲），后段公孙瓒得刘关张之援转安，双方罢兵',
 'casualties_note': '瓒军折先锋严纲；绍军折麴义（为赵云所杀，演义第7回）。史实麴义此后仍为绍将多年，演义提前处死（卡片已注）。',
 'summary': '绍军磐河桥东、瓒军桥西；麴义伏盾斩严纲大破白马义从，赵云单骑救主，刘关张来援，董卓假诏和解。',
 'detail': '磐河之战是河北两雄的第一次正面碰撞。瓒以白马义从（因瓒善与羌胡战，所部多白马）为锋，绍以八百弩兵伏于盾下——阵中「白毦披发」诱敌，瓒军轻进，伏盾突起，千弩齐发，严纲被斩，瓒军大败。绍铁骑合围时赵云突阵救主；随后刘关张引幽州兵冲阵，云护瓒突围。演义在此安排了赵云与刘备的初见，「云愿效犬马之劳」为日后千里来投伏笔。',
 'front_line': [
  nd(1, '起兵', '瓒出幽州', '公孙越被杀，瓒尽起幽州之兵攻绍，以报弟仇。', 'you_zhou', 0, 0, 191),
  nd(2, '夺州', '绍据冀州', '逢纪献策赚韩馥，绍不费一兵而得冀州，兼并其众。', 'ji_zhou', 0, 0, 191),
  nd(3, '对峙', '会于磐河', '两军会于磐河之上，绍军桥东、瓒军桥西。', 'pan_he', 0, 0, 191),
  nd(4, '伏发', '麴义斩严纲', '白马义从轻进，盾下弩发，严纲被斩，瓒军大败。', 'pan_he', 0.05, 0.02, 191),
  nd(5, '救主', '赵云突阵', '绍兵合围，赵云单骑突入救瓒，且战且退。', 'pan_he', -0.04, -0.02, 191),
  nd(6, '来援', '三雄冲阵', '刘关张引兵冲阵，绍军溃退，自此相拒月余。', 'pan_he', 0.02, -0.05, 191),
 ],
})

# =============== 7. 孙坚之死（192） ===============
A({
 'id': 'sun_jian_zhi_si', 'name': '孙坚之死', 'kind': '军事事件',
 'start_year': 192, 'end_year': 192, 'date_text': '初平三年（192）',
 'summary': '孙坚以刘表截击之恨起兵伐荆州，围襄阳；蒯良使吕公突围求救并诱坚追击，坚于岘山中伏，为乱箭滚石所杀——年仅三十七，孙策继业。',
 'detail': '袁绍密令刘表截击孙坚，表使蔡瑁出城迎战为坚所败。坚以「刘表截路，必欲报之」，起兵荆州：坚军连胜，黄祖败入襄阳，坚围之。蒯良献策：使吕公率死士二百突围出城，多带弓弩手奔岘山——吕公下山搦战诈败，坚恃勇轻进，追入山中日暮，吕公放起连珠号炮，山上乱箭滚石俱下，坚脑浆迸流，人马皆死于岘山之内，寿止三十七岁。坚部将程普、黄盖、韩当死战得脱。孙策时年十七，以黄祖换父尸，罢战回江东，葬父于曲阿。演义此段「岘山伏杀」脉络清晰，史实为初平三年坚击黄祖，为流矢所中（演义归因吕公设伏，细节有异，孙坚卡已注）。',
 'place_id': 'xian_shan', 'parent_event_id': None,
 'participants': [
  {'person_id': 'sun_jian', 'role_desc': '伐荆州，岘山中伏而亡'},
  {'person_id': 'liu_biao', 'role_desc': '荆州刺史，据城拒守'},
  {'person_id': 'huang_zu', 'role_desc': '江夏太守，首战败退，后以换尸'},
  {'person_id': 'kuai_liang', 'role_desc': '献「吕公诱敌」之策'},
  {'person_id': 'lv_gong_jingzhou', 'role_desc': '率死士突围，诈败诱坚入岘山'},
  {'person_id': 'cai_mao', 'role_desc': '出战为坚所败'},
  {'person_id': 'cheng_pu', 'role_desc': '死战得脱'},
  {'person_id': 'sun_ce', 'role_desc': '以黄祖换父尸，继父业'},
  {'person_id': 'wu_furen', 'role_desc': '坚妻，扶柩东归'},
 ],
 'timeline': [
  {'year': 192, 'title': '起兵伐表', 'description': '坚以「截路夺玺」之恨，尽起江东之兵伐刘表。', 'importance': 3},
  {'year': 192, 'title': '樊城首捷', 'description': '黄祖出战败走，坚乘胜围襄阳。', 'importance': 2},
  {'year': 192, 'title': '吕公出城', 'description': '蒯良使吕公率死士二百突围，诈败奔岘山。', 'importance': 2},
  {'year': 192, 'title': '岘山中伏', 'description': '坚夜追入山，号炮起处乱箭滚石俱下，坚卒，年三十七。', 'importance': 3},
  {'year': 192, 'title': '换尸罢兵', 'description': '孙策以黄祖换父尸，葬坚于曲阿之原，引军居江都。', 'importance': 2},
 ],
 'passage_ids': refs(
  (7, '却说孙坚有四子'), (7, '黄祖伏弓弩手'), (7, '吕公截住三十骑'),
  (7, '孙策回到汉水'), (8, '孙策换回黄祖'),
 ),
})
B({
 'id': 'xian_shan_zhi_zhan', 'name': '岘山之战', 'year': 192, 'date_text': '初平三年（192）',
 'place_id': 'xian_shan', 'event_id': 'sun_jian_zhi_si',
 'belligerents': [
  {'side': '江东军（孙坚）', 'faction_ids': ['wu', 'warlord'], 'commanders': ['sun_jian', 'cheng_pu', 'huang_gai', 'han_dang'], 'troops_desc': '江东之兵，水陆并进'},
  {'side': '荆州军（刘表）', 'faction_ids': ['warlord'], 'commanders': ['liu_biao', 'huang_zu', 'kuai_liang', 'lv_gong_jingzhou', 'cai_mao'], 'troops_desc': '据襄阳，蒯良运筹'},
 ],
 'result': '荆州胜，孙坚战死',
 'casualties_note': '孙坚殁于岘山（演义写中伏乱箭，史书为流矢所中）；荆州军折损不明。孙策以黄祖换父尸。',
 'summary': '孙坚破樊城、围襄阳；蒯良遣吕公诱敌，坚夜追入岘山，伏兵四起，中箭滚石而亡，年三十七。',
 'detail': '坚军破黄祖于樊城，进围襄阳。蒯良料「坚恃勇轻进」，使吕公率死士二百、弓弩手百人，乘夜缒城而出——吕公先犯坚寨诈败，坚轻骑三十余骑追之，吕公且战且走引入岘山小路，一声炮响，山上乱箭如雨、滚石而下，坚脑浆迸流而死。江东诸将拼死夺回尸首。此战让十七岁的孙策直面家业崩塌，「以黄祖换父尸」是孙策第一次出现在外交舞台；「引军居江都，招延俊秀」则是后来借兵渡江的起点。',
 'front_line': [
  nd(1, '起兵', '坚出长沙', '坚以夺玺截路之恨，尽起江东兵伐刘表，水陆并进。', 'chang_sha', 0, 0, 192),
  nd(2, '首捷', '樊城破黄祖', '黄祖出战败走，坚乘胜进围襄阳。', 'fan_cheng', 0, 0, 192),
  nd(3, '围城', '坚围襄阳', '蒯良守城运筹，遣吕公夜缒出城求救并诱敌。', 'xiang_yang', 0, 0, 192),
  nd(4, '中伏', '岘山殒命', '坚追吕公入山，号炮起处乱箭滚石俱下，坚卒，年三十七。', 'xian_shan', 0, 0, 192),
 ],
})

# =============== 8. 连环计·凤仪亭（192） ===============
A({
 'id': 'lian_huan_ji', 'name': '连环计·凤仪亭', 'kind': '政治事件',
 'start_year': 192, 'end_year': 192, 'date_text': '初平三年（192）',
 'summary': '王允以貂蝉许吕布而献董卓，离间其父子；吕布与貂蝉私会凤仪亭，卓掷戟相向——父子仇隙既成，王允收吕布，诛董之局成。',
 'detail': '王允忧董卓弄权，后园遇歌伎貂蝉长叹，遂定连环计：先以金冠明珠许布，宴上许以貂蝉；数日后复献于卓，卓载归相府。布疑之，乘卓入朝，私会貂蝉于凤仪亭——蝉泣诉「身在卓府，恨不得即死」，布依依相顾。卓回府撞见，抢布画戟掷之，布飞身而走。李儒劝「以蝉赐布，布感大恩必效死」，卓以「爱妾不可失」却之；貂蝉以「宁死不污布」固卓之宠。儒叹「吾等皆死于妇人之手矣」。布自此与卓有隙，王允乘机收布——「司徒妙算托红裙，不用干戈不用兵」。',
 'place_id': 'chang_an', 'parent_event_id': None,
 'participants': [
  {'person_id': 'wang_yun', 'role_desc': '定连环计者'},
  {'person_id': 'diao_chan', 'role_desc': '歌伎，周旋于卓布之间'},
  {'person_id': 'lv_bu', 'role_desc': '先许婚而后失之，凤仪亭与蝉私会'},
  {'person_id': 'dong_zhuo', 'role_desc': '纳蝉，掷戟逐布'},
  {'person_id': 'li_ru', 'role_desc': '劝卓以蝉赐布，不听'},
 ],
 'timeline': [
  {'year': 192, 'title': '后园定计', 'description': '王允见貂蝉长叹，定连环计：先许吕布，后献董卓。', 'importance': 3},
  {'year': 192, 'title': '许嫁吕布', 'description': '金冠明珠为聘，宴上许以貂蝉，布大喜拜谢。', 'importance': 2},
  {'year': 192, 'title': '复献董卓', 'description': '数日后卓至允府，允命貂蝉把盏献舞，卓载归相府。', 'importance': 3},
  {'year': 192, 'title': '凤仪亭相会', 'description': '布乘卓入朝私会貂蝉，蝉泣诉布抱之，卓回府撞见。', 'importance': 3},
  {'year': 192, 'title': '掷戟逐布', 'description': '卓抢布画戟掷之，布飞身而走，父子仇隙既成。', 'importance': 3},
  {'year': 192, 'title': '李儒之谏', 'description': '儒劝以蝉赐布，卓不纳；儒叹「吾等皆死于妇人之手」。', 'importance': 2},
 ],
 'passage_ids': refs(
  (8, '司徒王允归到府中'), (8, '便将家藏明珠数颗'), (8, '允欲屈太师车骑'),
  (8, '卓见貂蝉颜色美丽'), (8, '汝可去后园中凤仪亭'), (8, '正见吕布和貂蝉在凤仪亭'),
  (9, '却说那撞倒董卓的人'), (9, '可将貂蝉送与吕布'),
 ),
})

# =============== 9. 董卓之死（192） ===============
A({
 'id': 'dong_zhuo_zhi_si', 'name': '董卓之死', 'kind': '政治事件',
 'start_year': 192, 'end_year': 192, 'date_text': '初平三年（192）四月',
 'summary': '王允与吕布定计，使李肃奉诏诱卓出郿坞；卓入朝至受禅台，布戟刺其喉——百姓歌舞于道，卓尸置市燃之，郿坞抄没。',
 'detail': '卓自凤仪亭后归郿坞。王允与吕布、李肃定计：使人传「天子欲禅位于太师」，卓大喜，连夜回长安。临行折轮、马嘶、狂风骤起，行人与道人皆以凶兆警之，卓不听。次日入朝，至受禅台前，王允等伏甲士——布于怀中取出诏书「有诏讨贼臣」，卓大呼「吾儿奉先何在」，布应声「有诏讨贼臣！」一戟直刺咽喉。李儒、李肃等皆被诛，卓尸置市曹，体肥，看守尸首之军士以火置脐中为灯，光明照彻——「百姓过者，莫不手掷其头，足蹈其尸」。郿坞抄没，坞中珍藏、美女尽入官库。',
 'place_id': 'chang_an', 'parent_event_id': None,
 'participants': [
  {'person_id': 'dong_zhuo', 'role_desc': '被诛者，「吾儿奉先何在」'},
  {'person_id': 'wang_yun', 'role_desc': '主谋，伏甲士于受禅台'},
  {'person_id': 'lv_bu', 'role_desc': '「有诏讨贼臣」，戟刺其喉'},
  {'person_id': 'li_su', 'role_desc': '奉诏诱卓出郿坞'},
  {'person_id': 'li_ru', 'role_desc': '谋主，事发被诛'},
 ],
 'timeline': [
  {'year': 192, 'title': '定计收布', 'description': '王允以「汉家四百年天下」说吕布，布誓诛国贼。', 'importance': 3},
  {'year': 192, 'title': '奉诏诱卓', 'description': '李肃至郿坞，传「天子禅位」之诏，卓大喜而回长安。', 'importance': 2},
  {'year': 192, 'title': '凶兆屡见', 'description': '车折轮、马嘶不前、狂风骤雨，青袍道人缚布书「口」——卓皆不悟。', 'importance': 2},
  {'year': 192, 'title': '受禅台之变', 'description': '卓入朝，布出诏「有诏讨贼臣」，一戟刺喉。', 'importance': 3},
  {'year': 192, 'title': '曝尸市曹', 'description': '卓尸置市，看尸军士以火置脐中为灯；郿坞抄没。', 'importance': 2},
 ],
 'passage_ids': refs(
  (9, '次日，李肃引十数骑'), (9, '卓出坞上车'), (9, '青袍白巾'),
  (9, '李傕、郭汜、张济、樊稠闻董卓已死'),
 ),
})

# =============== 10. 李傕郭汜之乱（192–196） ===============
A({
 'id': 'li_jue_guo_si_zhi_luan', 'name': '李傕郭汜之乱', 'kind': '军事行动',
 'start_year': 192, 'end_year': 196, 'date_text': '初平三年（192）—兴平、建安之际（196 前）',
 'summary': '贾诩一言激起凉州兵反攻长安，吕布出走、王允殉难；此后李傕郭汜把持朝政、自相攻杀，献帝颠沛——汉室名存实亡，曹操得迎奉之机。',
 'detail': '董卓既诛，李傕、郭汜、张济、樊稠逃居陕西，使人求赦，王允不许——「卓之跋扈，皆此四人助之」。贾诩时为卓校尉，献策「激众西攻长安，事济，奉国家以正天下；不济，走亦未迟」。四人遂聚十余万西凉兵杀奔长安。吕布迎战失利，城内叱降兵反戈，长安遂破。王允拒降，坠楼而死，宗族被戮。此后四将把持朝政，朱儁忧死；马腾、韩遂兴兵讨贼，为贾诩所败，马超阵斩李蒙、王方；继而傕汜自相攻杀，劫帝劫臣，长安化为丘墟——献帝颠沛流离，为后来曹操「奉天子以令不臣」留下空位。',
 'place_id': 'chang_an', 'parent_event_id': None,
 'participants': [
  {'person_id': 'li_jue', 'role_desc': '首恶，自为大司马车骑将军'},
  {'person_id': 'guo_si', 'role_desc': '同恶，后与傕相攻杀'},
  {'person_id': 'jia_xu', 'role_desc': '献「激众攻长安」之策（文和乱武）'},
  {'person_id': 'zhang_ji', 'role_desc': '四将之一'},
  {'person_id': 'fan_chou', 'role_desc': '四将之一，后为傕所杀'},
  {'person_id': 'wang_yun', 'role_desc': '拒赦激变，城破坠楼殉难'},
  {'person_id': 'lv_bu', 'role_desc': '迎战失利，弃家出走投袁术'},
  {'person_id': 'liu_xie', 'role_desc': '献帝，为傕汜所挟'},
  {'person_id': 'ma_teng', 'role_desc': '西凉太守，兴兵讨贼'},
  {'person_id': 'han_sui', 'role_desc': '与腾同讨，兵败'},
 ],
 'timeline': [
  {'year': 192, 'title': '求赦不许', 'description': '四将使人求赦，王允不许——「四人助卓为虐，必当赦之不可」之争。', 'importance': 2},
  {'year': 192, 'title': '文和乱武', 'description': '贾诩献策激众西攻：「事济，奉国家以正天下」。', 'importance': 3},
  {'year': 192, 'title': '长安城破', 'description': '吕布迎战失利，城内降兵反戈，长安遂破。', 'importance': 3},
  {'year': 192, 'title': '王允殉难', 'description': '允拒降坠楼而死，宗族老幼被戮，士民下泪。', 'importance': 3},
  {'year': 192, 'title': '四将专权', 'description': '李傕自为大司马车骑将军，郭汜、张济、樊稠各领兵权，把持朝政。', 'importance': 2},
  {'year': 192, 'title': '马腾韩遂讨贼', 'description': '西凉兵起，为贾诩所败；马超阵斩李蒙、王方，威名初显。', 'importance': 2},
  {'year': 195, 'title': '傕汜相攻', 'description': '二贼自相攻杀，劫帝劫臣，长安化为丘墟，帝东逃洛阳。', 'importance': 2},
 ],
 'passage_ids': refs(
  (9, '便引了飞熊军连夜奔凉州'), (9, '使人至长安上表求赦'), (9, '遂引李肃'),
  (9, '李傕、郭汜纵兵大掠'), (9, '众贼杀了王允'),
  (10, '却说李、郭二贼欲弑献帝'), (10, '且说李傕、郭汜既掌大权'),
  (10, '李傕、郭汜听知李蒙'), (10, '李傕、郭汜自战败西凉兵'),
 ),
})
B({
 'id': 'chang_an_zhi_zhan', 'name': '长安之战', 'year': 192, 'date_text': '初平三年（192）五月—六月',
 'place_id': 'chang_an', 'event_id': 'li_jue_guo_si_zhi_luan',
 'belligerents': [
  {'side': '凉州叛军', 'faction_ids': ['warlord'], 'commanders': ['li_jue', 'guo_si', 'zhang_ji', 'fan_chou', 'jia_xu'], 'troops_desc': '十余万，昼夜兼程'},
  {'side': '朝廷（王允·吕布）', 'faction_ids': ['han'], 'commanders': ['wang_yun', 'lv_bu'], 'troops_desc': '城内禁军及布部飞熊军'},
 ],
 'result': '叛军胜，长安城破，王允殉难',
 'casualties_note': '城中死者数万；王允坠楼死，宗族被戮。吕布出走武关。贾诩自评此策「何功之有」。',
 'summary': '贾诩一言激起凉州兵十万西攻长安；吕布迎战失利，城内降兵反戈，城破，王允殉难，四将专权。',
 'detail': '王允不许四将之赦，贾诩曰「诸君若弃军单行，则一亭长能缚君矣；不如相率而西，以攻长安，为董公报仇。事济，奉国家以正天下；不济，走亦未迟」。四将遂聚十余万人马昼夜兼程。吕布出迎，傕退上山；布怒冲杀，山上矢石如雨。郭汜自后杀至，布首尾受敌；城中叱降兵反戈内应，长安遂破。布欲召王允同走，允曰「若蒙社稷之灵，上安国家，吾之愿也；如其不获，则奉身以死之」——坠楼而死。四将纵兵大掠，把持朝政四年，长安化为丘墟。',
 'front_line': [
  nd(1, '起兵', '贾诩献策', '四将逃居陕西，诩曰「不如相率而西，攻长安」。', 'liang_zhou', 0.02, 0, 192),
  nd(2, '进军', '昼夜兼程', '聚十余万凉州兵，杀奔长安，沿途收卓旧部。', 'chang_an', -0.05, 0.02, 192),
  nd(3, '会战', '布迎失利', '吕布出迎，傕退山以矢石困之，郭汜自后夹击。', 'chang_an', 0.04, -0.02, 192),
  nd(4, '城破', '降兵内应', '城中叱降兵反戈，长安遂破，死者数万。', 'chang_an', 0, 0.01, 192),
  nd(5, '结局', '王允殉难', '允拒降坠楼而死，四将纵兵大掠，把持朝政。', 'chang_an', -0.03, 0.04, 192),
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
 'comment': 'P1-D（2026-10-27）：第 2–10 回的 9 组事件 + 6 场战役。事件与「军事行动」类统摄事件、战役与父事件的对应关系见 docs/规则手册.md 第七章。passage_ids 由 scripts/gen_events_p1d.py 从构建产物解析生成，禁止手改。',
 'events': events, 'battles': battles,
}
io.open(os.path.join(DATA, 'event_battle_ch002_010.json'), 'w', encoding='utf-8').write(
    json.dumps(out, ensure_ascii=False, indent=1))
print('生成事件 %d 组、战役 %d 场、战线节点 %d 个' % (
    len(events), len(battles), sum(len(b['front_line']) for b in battles)))
for e in events:
    print('  事件 %-26s 段落 %d 处  人物 %d' % (e['id'], len(e['passage_ids']), len(e['participants'])))
for b in battles:
    print('  战役 %-26s 节点 %d  挂 %s' % (b['id'], len(b['front_line']), b['event_id']))
