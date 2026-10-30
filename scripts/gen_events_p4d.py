#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P4-D 联动：生成第 101–110 回的 4 组事件 + 2 场战役（data/event_battle_ch101_110.json）。
约束同 gen_events_p3a.py：passage_ids 解析生成；participants/commanders 仅已建档 id 或其他批次预分配 id。
"""
import json, io, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, 'build')
DATA = os.path.join(ROOT, 'data')

# 其他批次预分配、可引用但本批次不建档的 id
PREALLOCATED = {
    'sim_yi', 'lu_xun', 'liu_shan', 'li_yan', 'meng_huo', 'cao_zhen', 'jiang_wei',
    'ma_su', 'wang_ping', 'cao_rui', 'hao_zhao', 'wang_shuang', 'jiang_wan',
    'deng_ai', 'guo_huai', 'zhong_hui', 'zhuge_dan', 'chen_tai', 'sun_xiu',
    'sun_hao', 'cao_mao', 'zhuge_zhan', 'wang_jun', 'du_yu', 'yang_hu',
    'sun_chen', 'lu_kang',
}

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
ALLOWED = person_ids | PREALLOCATED


def ref(no, kw):
    hits = [(s, t) for (n, s), t in passages.items() if n == no and kw in t]
    if not hits:
        raise SystemExit('出处解析失败：第 %d 回找不到关键词「%s」' % (no, kw))
    return pids[(no, hits[0][0])]


def refs(no, kws):
    return [ref(no, kw) for kw in kws]


def check_place(pid):
    if pid not in places:
        raise SystemExit('未收录地点：%s' % pid)


def check_persons(obj, *id_fields):
    for f in id_fields:
        if f == 'participants':
            ids = [p['person_id'] for p in obj['participants']]
        elif f == 'belligerents':
            ids = [c for b in obj['belligerents'] for c in b['commanders']]
        else:
            ids = obj[f]
        bad = [i for i in ids if i not in ALLOWED]
        if bad:
            raise SystemExit('%s：未建档人物 %s' % (obj['id'], bad))


FACTIONS = {'han', 'warlord', 'wei', 'wu', 'shu', 'jin', 'barbarian', 'mystic'}

events, battles = [], []

# ---- E1 木门道张郃之死（101 回，231） ----
e1 = {
    'id': 'mumen_dao_zhang_he',
    'name': '木门道张郃之死',
    'kind': '人物',
    'start_year': 231, 'end_year': 231,
    'date_text': '建兴九年（231）',
    'summary': '诸葛亮第四次北伐退军，以伏兵诱张郃追至剑阁木门道，万弩齐发，郃死于乱箭之下。',
    'detail': '孔明知祁山兵已回，令杨仪、马忠引一万弓弩手伏于剑阁木门道，又令魏延、关兴轮流诈败诱敌。张郃怒追不舍，一追再追，直入木门道中；一声炮响，大石乱柴滚下截断归路，两下万弩齐发，郃并百余部将皆射死于木门道中。诗曰：伏弩齐飞万点星，木门道上射雄兵。张郃之死，魏国良将折损，诸葛亮北伐以此收束第四次出师。',
    'place_id': 'jian_ge',
    'parent_event_id': None,
    'participants': [
        {'person_id': 'zhang_he', 'role_desc': '奉司马懿命追击，中伏死于木门道'},
        {'person_id': 'zhuge_liang', 'role_desc': '设伏授计，以魏延关兴诱郃入木门道'},
        {'person_id': 'wei_yan', 'role_desc': '诈败诱敌，引郃深入'},
        {'person_id': 'wang_ping', 'role_desc': '受密计断后设伏（演义部署之一）'},
    ],
    'passage_ids': refs(101, ['木门', '张郃', '魏延']),
}
check_persons(e1, 'participants')
check_place(e1['place_id'])
events.append(e1)

# ---- E2 + B1 五丈原之战 / 秋风五丈原（103–104 回，234） ----
b1 = {
    'id': 'wu_zhang_yuan_battle',
    'name': '五丈原之战',
    'year': 234,
    'date_text': '建兴十二年（234）',
    'place_id': 'wu_zhang_yuan',
    'event_id': 'wu_zhang_yuan_zhi_zhan',
    'belligerents': [
        {'side': '蜀军', 'faction_ids': ['shu'],
         'commanders': ['zhuge_liang', 'jiang_wei', 'yang_yi', 'wei_yan', 'ma_dai', 'wang_ping'],
         'troops_desc': '诸葛亮屯五丈原与魏相持，累令人搦战'},
        {'side': '魏军', 'faction_ids': ['wei'],
         'commanders': ['sim_yi', 'guo_huai'],
         'troops_desc': '司马懿渭北坚壁不出，据守渭南'},
    ],
    'result': '两军相持百余日，亮积劳成疾病卒军中；蜀依遗策徐退，木像退追兵，"死诸葛走生仲达"。',
    'casualties_note': '蜀汉丞相诸葛亮薨于五丈原军中；上方谷一役魏兵几尽，天雨得免。',
    'summary': '诸葛亮与司马懿相持五丈原，遗巾帼激战不得；禳星不果，秋风五丈原丞相归天，姜维杨仪按遗计退兵，木像惊走仲达。',
    'detail': '亮引一军屯五丈原，懿据渭南坚守不出。亮以上方谷（葫芦谷）诱懿，火烧魏兵，忽降大雨救之，懿遂坚壁愈固。亮以巾帼妇衣遗懿，懿受之不怒，反问使者寝食，曰：食少事烦，岂能长久。亮禳星祈禳已及六夜，魏延飞步告警扑灭主灯，亮叹死生有命。亮病笃，授杨仪锦囊、以兵法授姜维，遍观各营，长叹悠悠苍天，卒于军中。懿见大星坠蜀营引兵追之，姜维令回旗返鼓推出木像，懿惊奔五十余里，摸头问：我有头否？闻木像之叹：吾能料其生，不能料其死也！蜀人谚曰：死诸葛能走生仲达。',
    'front_line': [
        {'time': 234, 'time_seq': 1, 'kind': '对峙', 'label': '屯兵五丈原', 'desc': '亮屯五丈原与懿隔渭相持，懿曰：若出渭南西止五丈原，方无事也。', 'lng': 107.65, 'lat': 34.35},
        {'time': 234, 'time_seq': 2, 'kind': '火攻', 'label': '上方谷之计', 'desc': '懿父子中伏上方谷，忽天降大雨扑灭地雷火，懿得脱，遂坚壁不出。', 'lng': 107.67, 'lat': 34.37},
        {'time': 234, 'time_seq': 3, 'kind': '激将', 'label': '巾帼之辱', 'desc': '亮遗巾帼妇衣激懿决战，懿受之不怒，问使寝食，食少事烦岂能长久。', 'lng': 107.66, 'lat': 34.34},
        {'time': 234, 'time_seq': 4, 'kind': '禳星', 'label': '主灯扑灭', 'desc': '亮禳星六夜，魏延飞步入告扑灭主灯，死生有命不可禳也。', 'lng': 107.64, 'lat': 34.36},
        {'time': 234, 'time_seq': 5, 'kind': '病卒', 'label': '秋风五丈原', 'desc': '亮强病遍观各营，叹再不能临阵讨贼，卒于军中，年五十四。', 'lng': 107.65, 'lat': 34.35},
        {'time': 234, 'time_seq': 6, 'kind': '疑兵', 'label': '死诸葛走生仲达', 'desc': '姜维杨仪推木像回旗返鼓，懿惊奔五十余里，蜀中谚传死诸葛走生仲达。', 'lng': 107.63, 'lat': 34.33},
    ],
}
check_persons(b1, 'belligerents')
check_place(b1['place_id'])
battles.append(b1)
e2 = {
    'id': 'wu_zhang_yuan_zhi_zhan',
    'name': '五丈原之战',
    'kind': '征伐',
    'start_year': 234, 'end_year': 234,
    'date_text': '建兴十二年（234）',
    'summary': '诸葛亮第五次北伐与司马懿相持五丈原，丞相积劳病卒军中，蜀军依遗计全师而退。',
    'detail': '详见战役「五丈原之战」。亮卒后杨仪总军、姜维断后，魏延不服构兵为马岱所斩；蜀汉自此转入后诸葛亮时代，蒋琬费祎相继秉政。',
    'place_id': 'wu_zhang_yuan',
    'parent_event_id': None,
    'participants': [
        {'person_id': 'zhuge_liang', 'role_desc': '统帅，相持禳星，卒于五丈原军中'},
        {'person_id': 'sim_yi', 'role_desc': '魏统帅，坚壁不战，追击遇木像惊走'},
        {'person_id': 'jiang_wei', 'role_desc': '受兵法遗命，断后回旗返鼓'},
        {'person_id': 'yang_yi', 'role_desc': '受锦囊遗令，总军退兵'},
        {'person_id': 'wei_yan', 'role_desc': '夜扑主灯；亮卒后拒后构兵'},
        {'person_id': 'ma_dai', 'role_desc': '受密计，阵斩魏延'},
        {'person_id': 'guo_huai', 'role_desc': '魏将，渭南参赞军务'},
        {'person_id': 'wang_ping', 'role_desc': '蜀将，遗表所荐忠义可委用之人'},
    ],
    'passage_ids': refs(103, ['五丈原', '上方谷', '巾帼', '主灯']) + refs(104, ['遗表', '秋风', '木人', '死诸葛']),
    'battle_ids': ['wu_zhang_yuan_battle'],
}
check_persons(e2, 'participants')
check_place(e2['place_id'])
events.append(e2)

# ---- E3 + B2 公孙渊之叛 / 襄平之战（106 回，238） ----
b2 = {
    'id': 'xiang_ping_battle',
    'name': '襄平之战',
    'year': 238,
    'date_text': '景初二年（238）',
    'place_id': 'xiang_ping',
    'event_id': 'gongsun_yuan_zhi_pan',
    'belligerents': [
        {'side': '魏军', 'faction_ids': ['wei'],
         'commanders': ['sim_yi', 'cao_rui'],
         'troops_desc': '司马懿率马步官军四万东征辽东，弃辽隧径趋襄平'},
        {'side': '燕军（辽东兵）', 'faction_ids': ['warlord'],
         'commanders': ['gongsun_yuan'],
         'troops_desc': '公孙渊自号燕王，卑衍杨祚将辽兵十五万'},
    ],
    'result': '司马懿围困襄平，雨困粮尽，渊父子突围被擒斩，辽东平定。',
    'casualties_note': '卑衍阵斩；公孙渊宗族同谋七十余首级号令；渊父子对面受戳。',
    'summary': '公孙渊僭号燕王，司马懿东征：弃辽隧捣虚襄平，围城一月不避大雨，城破斩渊父子，传首洛阳。',
    'detail': '渊自号燕王改元绍汉，起辽兵十五万杀奔中原。睿命懿率四万兵往征，懿曰四千里地往百日攻百日还百日约一年足矣。卑衍杨祚八万众屯辽隧固守，懿笑曰贼众大半在此巢穴空虚，勒兵径趋襄平；衍祚回救，中伏败走首山，卑衍为夏侯霸一刀斩于马下。渊奔入襄平固守。时秋雨连绵一月不止，平地水深三尺，运粮船直抵城下，懿斩谏移营者，坚坐待变。夜观大星坠于襄平东南，懿曰五日之后星落处必斩公孙渊。渊粮尽请降，懿不许；渊与子修开南门突围，行不及十里四面围合，父子下马受缚，懿即令斩之。宗族同谋七十余首级号令，班师回洛阳。',
    'front_line': [
        {'time': 238, 'time_seq': 1, 'kind': '对峙', 'label': '辽隧僵持', 'desc': '卑衍杨祚八万兵屯辽隧围堑二十余里，魏兵不与交战。', 'lng': 123.15, 'lat': 41.25},
        {'time': 238, 'time_seq': 2, 'kind': '捣虚', 'label': '直趋襄平', 'desc': '懿弃辽隧从小路径奔襄平，贼必往救，中途伏击。', 'lng': 123.17, 'lat': 41.27},
        {'time': 238, 'time_seq': 3, 'kind': '围困', 'label': '雨困襄平', 'desc': '秋雨一月平地水深三尺，懿斩谏移营者，运粮船直抵城下。', 'lng': 123.19, 'lat': 41.29},
        {'time': 238, 'time_seq': 4, 'kind': '破城', 'label': '斩渊父子', 'desc': '渊父子突围南走，四面围合就缚受戳，宗族七十余首级号令。', 'lng': 123.18, 'lat': 41.28},
    ],
}
check_persons(b2, 'belligerents')
check_place(b2['place_id'])
battles.append(b2)
e3 = {
    'id': 'gongsun_yuan_zhi_pan',
    'name': '公孙渊之叛',
    'kind': '叛乱',
    'start_year': 238, 'end_year': 238,
    'date_text': '景初二年（238）',
    'summary': '辽东公孙渊自立燕王起兵反魏，司马懿奉命东征，襄平城破斩渊，辽东复平。',
    'detail': '详见战役「襄平之战」。渊斩孙权使者、受魏上公之爵而心不足，终僭号叛乱；贾范、伦直谏止皆被杀，懿破城后封其墓而荣其子孙。此役之后辽东公孙氏割据五十年终结，魏东北遂安。',
    'place_id': 'xiang_ping',
    'parent_event_id': None,
    'participants': [
        {'person_id': 'gongsun_yuan', 'role_desc': '自立燕王起兵，襄平兵败被斩'},
        {'person_id': 'sim_yi', 'role_desc': '奉命东征统帅，捣虚围城斩渊'},
        {'person_id': 'cao_rui', 'role_desc': '魏主，命懿兴师征讨'},
    ],
    'passage_ids': refs(106, ['公孙渊', '襄平', '司马懿', '燕王']),
    'battle_ids': ['xiang_ping_battle'],
}
check_persons(e3, 'participants')
check_place(e3['place_id'])
events.append(e3)

# ---- E4 高平陵之变（107 回，249） ----
e4 = {
    'id': 'gaoping_ling_zhi_bian',
    'name': '高平陵之变',
    'kind': '政变',
    'start_year': 249, 'end_year': 249,
    'date_text': '嘉平元年正月（249）',
    'summary': '曹爽兄弟随驾谒高平陵，司马懿闭城据武库屯洛水浮桥，赚爽纳印归府，诛爽三族，魏政自此归司马氏。',
    'detail': '爽兄弟及何晏等随魏主曹芳出城谒明帝墓畋猎，懿入奏郭太后废爽，引兵据武库，令蒋济司马孚写表，司马昭守洛水浮桥。桓范矫诏出城劝爽奉天子幸许都发外兵，蒋济断言驽马恋栈豆必不能用。爽思虑一昼夜，掷剑叹曰：我不起兵，情愿弃官，但为富家翁足矣！范哭骂：曹子丹以智谋自矜，今兄弟三人真豚犊耳！爽纳印绶归府，懿遣人送粮示无相害；旋取张当供词，坐爽与何晏邓飏等谋逆，皆斩于市曹灭三族。自此魏之大权尽归司马氏，曹氏名存实亡。',
    'place_id': 'luo_yang',
    'parent_event_id': None,
    'participants': [
        {'person_id': 'sim_yi', 'role_desc': '称病阴谋，闭城据武库屯浮桥，诛爽夷三族'},
        {'person_id': 'cao_shuang', 'role_desc': '大将军辅政，谒陵被赚，纳印归府被诛'},
        {'person_id': 'cao_fang', 'role_desc': '魏主随驾谒陵，受懿表后政归司马氏'},
    ],
    'passage_ids': refs(107, ['谒明帝墓', '曹爽', '司马懿', '洛水', '桓范']),
}
check_persons(e4, 'participants')
check_place(e4['place_id'])
events.append(e4)

# 校验 tenure faction
person_file = json.load(io.open(os.path.join(DATA, 'persons_ch101_110.json'), encoding='utf-8'))
for p in person_file['persons']:
    for t in p.get('tenure', []):
        if t['faction_id'] not in FACTIONS:
            raise SystemExit('人物 %s tenure faction 非法：%s' % (p['id'], t['faction_id']))

out = {'comment': 'P4-D（2026-10-29）：第 101–110 回的 4 组事件 + 2 场战役。passage_ids 由本脚本解析生成，禁止手改。',
       'events': events, 'battles': battles}
p = os.path.join(DATA, 'event_battle_ch101_110.json')
io.open(p, 'w', encoding='utf-8').write(json.dumps(out, ensure_ascii=False, indent=2))
print('写出 %s：事件 %d，战役 %d' % (p, len(events), len(battles)))
