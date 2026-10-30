#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P2-A 联动：生成第 31–40 回的 4 组事件 + 2 场战役（data/event_battle_ch031_040.json）。

用法：先跑一次 build.py（让新地名拿到坐标），再跑本脚本，再跑一次 build.py。

设计约束（沿用 gen_events_p1f.py）：
- passage_ids 不手填：出处写成 (回数, 关键词)，脚本解析出段落 id 并断言命中。
- participants/commanders 只允许引用已建档 person id。
- front_line 坐标从 build/places.json 取。
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


def refs(no, kws):
    return [ref(no, kw) for kw in kws]


def lnglat(name, dx=0.0, dy=0.0):
    p = places[name]
    return round(p['lng'] + dx, 3), round(p['lat'] + dy, 3)


def check_persons(obj, *id_fields):
    for f in id_fields:
        for item in obj.get(f, []):
            if isinstance(item, str):
                pids_ = [item]
            elif 'commanders' in item:
                pids_ = item.get('commanders', [])
            else:
                pids_ = [item.get('person_id')]
            for pid_ in pids_:
                assert pid_ in person_ids, 'person id 未建档: %s (%s)' % (pid_, obj.get('id'))


DATA_OUT = {'comment': 'P2-A（2026-10-28）：第 31–40 回的 4 组事件 + 2 场战役。passage_ids 由 scripts/gen_events_p2a.py 从构建产物解析生成，禁止手改。', 'events': [], 'battles': []}

# ── 事件 1：袁氏兄弟相争（第 31–32 回）────────────────────────────
e1 = {
    'id': 'yuanshi_xiangzheng',
    'name': '袁氏兄弟相争',
    'kind': '权位之争',
    'start_year': 202,
    'end_year': 203,
    'date_text': '建安七年至八年（202–203）',
    'summary': '袁绍病死，废长立幼传位袁尚；袁谭不服，兄弟构兵于黎阳、平原。曹操坐收渔利，谭请操助，吕旷吕翔兄弟阵亡，袁氏自此分崩。',
    'detail': '官渡败后袁绍呕血而亡，审配逢纪矫遗命立三子袁尚为大司马将军领冀州牧，长子袁谭不得立，自请出镇青州。曹操渡河攻谭，谭告急于尚，尚恐谭得兵自立不发救兵，谭怒而攻尚，兄弟相争至此公开化。尚遣吕旷吕翔助谭，二吕暗受曹操封赏倒戈。谭用郭图之计诈降请操攻冀州，操知其诈而将计就计，以女许婚谭为饵。吕旷吕翔请为媒具见投曹之心，旋于攻平原时为赵云张飞所杀。',
    'place_id': 'ji_zhou',
    'parent_event_id': None,
    'participants': [
        {'person_id': 'yuan_shang', 'role_desc': '袁绍三子，受遗立继位，与兄构兵'},
        {'person_id': 'yuan_tan', 'role_desc': '长子，不得立，自号车骑将军攻尚，后诈降请操'},
        {'person_id': 'yuan_xi', 'role_desc': '次子，出镇幽州，置身局外'},
        {'person_id': 'shen_pei', 'role_desc': '审配，矫遗命立尚'},
        {'person_id': 'feng_ji', 'role_desc': '逢纪，与审配同立尚，后被谭杀'},
        {'person_id': 'guo_jia', 'role_desc': '曹操谋士，谏操缓攻以观兄弟内变'},
        {'person_id': 'xin_pi', 'role_desc': '袁谭使者，为操陈降计说谭'},
        {'person_id': 'wang_xiu', 'role_desc': '袁谭别驾，谏谭不听'},
        {'person_id': 'lv_kuang', 'role_desc': '袁尚大将，降曹为媒，阵亡'},
        {'person_id': 'lv_xiang', 'role_desc': '吕旷之弟，同降曹，阵亡'},
        {'person_id': 'cao_cao', 'role_desc': '司空，坐观成败，将计就计'},
    ],
    'timeline': [
        {'year': 202, 'title': '袁绍病死', 'description': '绍呕血死，审配逢纪矫命立尚，谭不得立。', 'importance': 3},
        {'year': 202, 'title': '黎阳相攻', 'description': '操攻谭，尚不发救兵，谭怒攻尚，兄弟构兵。', 'importance': 3},
        {'year': 202, 'title': '二吕倒戈', 'description': '吕旷吕翔受操封赏，暗通款曲。', 'importance': 2},
        {'year': 203, 'title': '诈降请操', 'description': '谭用郭图计诈降，操以女许婚将计就计；二吕攻平原被赵云张飞所杀。', 'importance': 3},
    ],
    'battle_ids': [],
}
e1['passage_ids'] = refs(31, ['袁绍','审配']) + refs(32, ['吕旷','许谭'])
DATA_OUT['events'].append(e1)

# ── 事件 2：冀州平定·郭嘉遗计（第 32–34 回）────────────────────
e2 = {
    'id': 'jizhou_pingding_guojia',
    'name': '冀州平定·郭嘉遗计',
    'kind': '征伐',
    'start_year': 203,
    'end_year': 205,
    'date_text': '建安八年至十年（203–205）',
    'summary': '操决漳河灌邺城擒审配；谭背约被斩于南皮；尚熙投辽东，郭嘉病亡遗计，公孙康斩二袁首献曹，河北平定。',
    'detail': '曹操会谭攻尚，决漳河之水灌邺城，城中粮尽，审配被侄审荣开门献城，擒而骂曹死。谭趁操攻冀州掠取甘陵等县并攻尚于中山，操责其负约进兵讨之，谭溃逃南皮，为曹洪所斩，王修乞收其尸。尚熙穷蹙投辽东公孙康，时郭嘉已病死于易州，操哀恸。嘉临终遗书：勿加兵辽东，公孙康与二袁必自相图。操按兵不动，康果然伏兵斩尚熙，首级献许。操引兵西击乌桓始定河北，于铜雀台大会诸将。',
    'place_id': 'ye_cheng',
    'parent_event_id': None,
    'participants': [
        {'person_id': 'cao_cao', 'role_desc': '司空，决漳灭邺，纳郭嘉遗计定辽东'},
        {'person_id': 'yuan_tan', 'role_desc': '背约掠地，败死南皮'},
        {'person_id': 'yuan_shang', 'role_desc': '邺城陷后与熙奔辽东，为公孙康所斩'},
        {'person_id': 'yuan_xi', 'role_desc': '与尚同奔辽东，同被斩'},
        {'person_id': 'shen_pei', 'role_desc': '守邺被擒，骂曹而死'},
        {'person_id': 'xin_pi', 'role_desc': '降操，其侄审荣开门献城之见证者（辛毗家在城中）'},
        {'person_id': 'guo_jia', 'role_desc': '从征乌桓病亡，遗计使辽东自相图'},
        {'person_id': 'gongsun_kang', 'role_desc': '辽东太守，伏兵斩二袁献首'},
        {'person_id': 'wang_xiu', 'role_desc': '乞收袁谭尸，操义之'},
    ],
    'timeline': [
        {'year': 204, 'title': '决漳灌邺', 'description': '操决漳河灌邺城，审荣献门，审配被擒死。', 'importance': 3},
        {'year': 205, 'title': '谭死南皮', 'description': '谭背约，操进兵，谭为曹洪所斩于南皮。', 'importance': 3},
        {'year': 205, 'title': '郭嘉病亡', 'description': '从征途中病死于易州，临终遗书定辽东之策。', 'importance': 3},
        {'year': 205, 'title': '二袁授首', 'description': '公孙康伏兵斩尚熙献首，河北平定。', 'importance': 3},
    ],
    'battle_ids': [],
}
e2['passage_ids'] = refs(32, ['决漳河','审配']) + refs(33, ['公孙康','郭嘉'])
DATA_OUT['events'].append(e2)

# ── 事件 3：三顾茅庐定三分（第 35–38 回）────────────────────────
e3 = {
    'id': 'sangu_miaolu',
    'name': '三顾茅庐定三分',
    'kind': '人才归附',
    'start_year': 207,
    'end_year': 208,
    'date_text': '建安十二年至十三年（207–208）',
    'summary': '徐庶走马荐诸葛，司马徽再荐卧龙；刘备三顾茅庐，亮以隆中对定三分之策，出山相佐。',
    'detail': '徐庶化名单福辅佐刘备破曹仁八门金锁阵，操囚其母诱庶归许都，庶走马荐诸葛：卧龙先生诸葛孔明。司马徽亦言「得其主不得其时」。刘备三往隆中：一顾遇崔州平怅然而返；二顾值隆冬遇石广元孟公威黄承彦，留书而去；三顾春日方得相见，亮未出而知三分，隆中对析曹操不可与争锋、孙权可以为援、跨荆益以图中原。亮初出茅庐，博望新野两把火，夏侯惇曹仁先后败绩，众将始服。',
    'place_id': 'long_zhong',
    'parent_event_id': None,
    'participants': [
        {'person_id': 'liu_bei', 'role_desc': '豫州牧，三顾茅庐请出诸葛亮'},
        {'person_id': 'zhuge_liang', 'role_desc': '卧龙，隆中对定三分之策，出山为军师'},
        {'person_id': 'xu_shu', 'role_desc': '单福，破曹仁八门金锁阵，因母归曹，走马荐诸葛'},
        {'person_id': 'sima_hui', 'role_desc': '水镜先生，再荐卧龙'},
        {'person_id': 'guan_yu', 'role_desc': '随往三顾，初不以为然，博望坡领右军'},
        {'person_id': 'zhang_fei', 'role_desc': '扬言缚孔明，三顾同行，火烧新野立功'},
        {'person_id': 'zhao_yun', 'role_desc': '刘备部将，随征破阵'},
        {'person_id': 'cao_cao', 'role_desc': '囚徐母诱庶，遣将攻新野'},
    ],
    'timeline': [
        {'year': 207, 'title': '单福破阵', 'description': '徐庶助备破曹仁八门金锁阵，取樊城。', 'importance': 2},
        {'year': 207, 'title': '走马荐诸葛', 'description': '操囚徐母诱庶归许，庶荐卧龙于备。', 'importance': 3},
        {'year': 207, 'title': '三顾茅庐', 'description': '备三往隆中，冬雪不辍，亮感其诚。', 'importance': 3},
        {'year': 208, 'title': '隆中对', 'description': '亮析天下势：跨荆益、联孙权、抗曹操，三分定策。', 'importance': 3},
        {'year': 208, 'title': '初出茅庐', 'description': '博望坡火烧夏侯惇十万军，众将始服。', 'importance': 3},
    ],
    'battle_ids': ['bo_wang_po'],
}
e3['passage_ids'] = refs(36, ['走马荐','草庐']) + refs(37, ['隆中','司马徽']) + refs(38, ['三顾','隆中'])
DATA_OUT['events'].append(e3)

# ── 事件 4：荆州易主·火烧新野（第 40 回）────────────────────────
e4 = {
    'id': 'jingzhou_yizhu_huoshaoinye',
    'name': '荆州易主·火烧新野',
    'kind': '政权更替',
    'start_year': 208,
    'end_year': 208,
    'date_text': '建安十三年（208）',
    'summary': '刘表病亡，蔡瑁张允矫诏立刘琮降曹；刘备携民渡江不忍弃百姓，遂走江夏；曹仁入新野中孔明之火，狼狈败退。',
    'detail': '刘表病重托荆州于备，备固辞。表死，蔡夫人与蔡瑁张允伪造遗嘱立幼子刘琮，未告备即举荆州降曹操，遣宋忠赍降书赴宛城。备大惊，孔明定计：先取江陵。备不忍弃随行百姓，携民渡江日行十余里。孔明引兵袭新野，留空城，曹仁大军入城屯扎，半夜火起，满县皆火，曹军自相践踏，出城又遇关张截杀，弃樊城退走。荆州六郡至此易主曹操，备退保江夏，赤壁之役自此而起。',
    'place_id': 'xin_ye',
    'parent_event_id': None,
    'participants': [
        {'person_id': 'liu_bei', 'role_desc': '携民渡江不忍弃百姓，退保江夏'},
        {'person_id': 'zhuge_liang', 'role_desc': '定计火烧新野'},
        {'person_id': 'guan_yu', 'role_desc': '截杀溃军，水淹后续接应'},
        {'person_id': 'zhang_fei', 'role_desc': '新野城外截杀曹军'},
        {'person_id': 'zhao_yun', 'role_desc': '护卫家眷随行'},
        {'person_id': 'cai_furen', 'role_desc': '伪造遗嘱立刘琮'},
        {'person_id': 'cai_mao', 'role_desc': '与张允矫诏立琮，主降曹'},
        {'person_id': 'cao_ren', 'role_desc': '领大军入新野中计，惨败'},
        {'person_id': 'cao_cao', 'role_desc': '受荆州之降，挥师南下'},
    ],
    'timeline': [
        {'year': 208, 'title': '刘表病亡', 'description': '表托国于备而卒。', 'importance': 3},
        {'year': 208, 'title': '琮举州降曹', 'description': '蔡瑁等矫诏立琮，即降曹操。', 'importance': 3},
        {'year': 208, 'title': '火烧新野', 'description': '孔明空城诱敌，火起满县，曹仁大败。', 'importance': 3},
        {'year': 208, 'title': '携民渡江', 'description': '备不忍弃百姓，携民渡江赴江夏。', 'importance': 2},
    ],
    'battle_ids': ['xin_ye_battle'],
}
e4['passage_ids'] = refs(40, ['刘琮','新野','火起'])
DATA_OUT['events'].append(e4)

# ── 战役 1：博望坡之战（第 39 回）────────────────────────────────
b1 = {
    'id': 'bo_wang_po',
    'name': '博望坡之战',
    'year': 208,
    'date_text': '建安十三年（208）',
    'place_id': 'bo_wang_po',
    'event_id': 'sangu_miaolu',
    'belligerents': [
        {'side': '曹军', 'faction_ids': ['wei'], 'commanders': ['xiahou_dun', 'yu_jin', 'li_dian'], 'troops_desc': '夏侯惇十万大军直逼新野'},
        {'side': '刘备军', 'faction_ids': ['shu'], 'commanders': ['liu_bei', 'zhuge_liang', 'guan_yu', 'zhang_fei', 'zhao_yun'], 'troops_desc': '新野兵不满三千 + 关羽张飞各五百 + 博望坡两侧芦苇伏兵'},
    ],
    'result': '孔明初出茅庐第一功：火攻大破夏侯惇十万军',
    'casualties_note': '曹军死伤极众，自相践踏；夏侯惇冒烟突走。',
    'summary': '操遣夏侯惇十万攻新野。孔明新拜军师，众将不服；亮调关羽张飞屯博望坡两侧山林候火，赵云诈败诱敌。惇追至博望坡芦苇狭道，火起满山，曹军大溃。',
    'detail': '夏侯惇领兵十万杀奔新野。张飞言「用孔明如水」，亮请剑印压众：关羽引一千伏博望坡左侧豫山，张飞引一千伏安林后，关平刘封备引火之物候敌入坡，赵云为诱兵只许败不许胜，备自引一军为援。惇至博望，与赵云交战佯败，追入狭窄芦苇坡道，天色晚风大起，火发两翼，曹军烧死踩死者众，惇冒烟突围而走。李典于禁劝阻不及，回军宛城请罪。',
    'front_line': [
        {'time': 208, 'time_seq': 1, 'kind': '进兵', 'label': '夏侯惇十万压境', 'desc': '操遣惇领兵十万直逼新野。', 'lng': 113.1, 'lat': 33.0},
        {'time': 208, 'time_seq': 2, 'kind': '诱敌', 'label': '赵云诈败', 'desc': '赵云出战只败不胜，诱惇入博望坡狭道。', 'lng': 112.9, 'lat': 33.25},
        {'time': 208, 'time_seq': 3, 'kind': '火攻', 'label': '火烧博望坡', 'desc': '火起两翼芦苇山林，曹军大溃。', 'lng': 112.9, 'lat': 33.25},
        {'time': 208, 'time_seq': 4, 'kind': '结局', 'label': '惇突围走', 'desc': '夏侯惇冒烟突走，回宛城请罪；孔明初战立威。', 'lng': 112.53, 'lat': 33.0},
    ],
}
DATA_OUT['battles'].append(b1)

# ── 战役 2：新野之战（第 40 回）──────────────────────────────────
b2 = {
    'id': 'xin_ye_battle',
    'name': '新野之战',
    'year': 208,
    'date_text': '建安十三年（208）',
    'place_id': 'xin_ye',
    'event_id': 'jingzhou_yizhu_huoshaoinye',
    'belligerents': [
        {'side': '曹军', 'faction_ids': ['wei'], 'commanders': ['cao_ren', 'li_dian', 'xu_chu'], 'troops_desc': '曹仁曹洪大军 + 许褚三千铁甲军先锋'},
        {'side': '刘备军', 'faction_ids': ['shu'], 'commanders': ['liu_bei', 'zhuge_liang', 'guan_yu', 'zhang_fei', 'zhao_yun'], 'troops_desc': '弃新野走樊城，空城设伏 + 关张两翼截杀'},
    ],
    'result': '孔明再火攻破曹仁，刘备弃樊城携民南走',
    'casualties_note': '曹军被火烧水淹者不计其数，自相践踏而死者甚众。',
    'summary': '曹仁曹洪大军继至。孔明令百姓避入樊城，空新野设伏：曹仁大军入城屯扎，夜半火起满县，溃军出城遭关张截杀，白河水又淹，大败而退。',
    'detail': '操遣曹仁曹洪继夏侯惇之后再来，许褚为先锋。孔明知新野不可守，令百姓尽迁樊城，虚设空城，城屋上藏硫磺引火之物。仁军入城抢掠屯扎，饥夜造饭，夜半狂风大作，火起满县，仁冒火夺路出城，遭赵云冲杀；出至东门又遇关羽引军截杀，白河上游放水淹其下游之军；张飞别路再截。仁大败退走樊城，见备已携百姓南行，遂还许都。',
    'front_line': [
        {'time': 208, 'time_seq': 1, 'kind': '进兵', 'label': '曹仁曹洪继至', 'desc': '操再遣大军，许褚为先锋攻新野。', 'lng': 112.36, 'lat': 32.52},
        {'time': 208, 'time_seq': 2, 'kind': '设伏', 'label': '空城藏火', 'desc': '孔明迁民樊城，空城伏火待敌。', 'lng': 112.36, 'lat': 32.52},
        {'time': 208, 'time_seq': 3, 'kind': '火攻', 'label': '火烧新野', 'desc': '夜半火起满县，曹军自相践踏。', 'lng': 112.36, 'lat': 32.52},
        {'time': 208, 'time_seq': 4, 'kind': '截杀', 'label': '关张白河截击', 'desc': '溃军出城遭关羽张飞截杀，白河水又淹之。', 'lng': 112.13, 'lat': 32.04},
        {'time': 208, 'time_seq': 5, 'kind': '结局', 'label': '仁败退', 'desc': '曹仁败还，备携民渡江走江夏，荆州易主。', 'lng': 114.3, 'lat': 30.6},
    ],
}
DATA_OUT['battles'].append(b2)

# ── 校验 + 写出 ────────────────────────────────────────────────
for e in DATA_OUT['events']:
    check_persons(e, 'participants')
for b in DATA_OUT['battles']:
    check_persons(b, 'belligerents')

out = os.path.join(DATA, 'event_battle_ch031_040.json')
json.dump(DATA_OUT, io.open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('写出 %s：事件 %d 组，战役 %d 场' % (out, len(DATA_OUT['events']), len(DATA_OUT['battles'])))
