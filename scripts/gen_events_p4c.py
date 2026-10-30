#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P4-C 联动：生成第 91–100 回的 4 组事件 + 2 场战役（data/event_battle_ch091_100.json）。
约束同 gen_events_p3a.py：passage_ids 解析生成；participants/commanders 仅已建档 id。
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


events, battles = [], []

# ---- E1 武侯上表 / 一出祁山（91–92 回，227–228） ----
e1 = {
    'id': 'chushi_biao_yichu_qishan', 'name': '武侯上表一出祁山', 'kind': '征伐',
    'start_year': 227, 'end_year': 228, 'date_text': '建兴五年春至六年春（227–228）',
    'summary': '马谡反间计去司马懿，孔明上《出师表》北驻汉中；一出祁山，却魏延子午谷奇计，从陇右大路进兵。',
    'detail': '孔明用马谡反间计，布散流言、伪造榜文，曹睿疑司马懿欲反，削职回乡，命曹休总督雍凉。南方已平，孔明上《出师表》：先帝创业未半而中道崩殂，今天下三分，益州罢敝，此诚危急存亡之秋也；愿陛下托臣以讨贼兴复之效，不效则治臣之罪。谯周以天象谏，不听。分拨诸将，留蒋琬为参军、郭攸之董允费祎侍中。赵云厉声请为先锋，孔明乃使云与邓芝出箕谷为疑兵。魏延献子午谷奇计：五千精兵循秦岭当子午谷而北，十日可到长安；孔明以为非万全之计不用，自陇右取平坦大路依法进兵，一出祁山，兵临渭水之西，关中震动。',
    'place_id': 'qi_shan',
    'parent_event_id': None,
    'participants': [
        {'person_id': 'zhuge_liang', 'role_desc': '上《出师表》，统大军北驻汉中、一出祁山'},
        {'person_id': 'liu_shan', 'role_desc': '后主，览表敕令出师，亲送北门十里'},
        {'person_id': 'ma_su', 'role_desc': '献反间计，流言伪榜使曹睿削司马懿兵权'},
        {'person_id': 'zhao_yun', 'role_desc': '厉声请缨，年七十为前部先锋，与邓芝出箕谷'},
        {'person_id': 'wei_yan', 'role_desc': '献子午谷奇计，孔明不用，随军进陇右'},
    ],
    'passage_ids': refs(91, ['出师表', '谯周', '司马懿']) + refs(92, ['子午谷', '赵云']),
}

# ---- E2 姜维归降（93 回，228，含骂死王朗） ----
e2 = {
    'id': 'jiangwei_guixiang', 'name': '姜维归降', 'kind': '人物',
    'start_year': 228, 'end_year': 228, 'date_text': '建兴六年（228）',
    'summary': '天水姜伯约识破蜀计战赵云，遭反间为马遵所拒，被困降蜀；孔明执手曰今遇伯约吾愿足矣。祁山阵前武乡侯骂死王朗。',
    'detail': '孔明识破其才，用夏侯楙行反间：遣形貌相似者假扮姜维夜攻天水，马遵、梁虔果疑维已降蜀，闭门乱箭拒之。维夺路奔上邽又被拒，两眼泪流，仰天长叹；关兴截路，孔明小车转出，维寻思无路下马投降。孔明下车执其手：吾自出茅庐遍求贤者，欲传平生之学，恨未得其人，今遇伯约，吾愿足矣。维献密书之计，梁绪尹赏献天水，梁虔降上邽。孔明曰：吾放夏侯楙如放一鸭，今得伯约，得一凤也。是役孔明尽提汉中之兵前出祁山，曹真拜大都督、王朗为军师；两阵之前朗夸大魏带甲百万劝亮倒戈，亮斥其助逆篡位：皓首匹夫！苍髯老贼！朗气满胸膛，撞死于马下，诗云轻摇三寸舌骂死老奸臣。',
    'place_id': 'tian_shui',
    'parent_event_id': None,
    'participants': [
        {'person_id': 'jiang_wei', 'role_desc': '识破蜀计战赵云，遭反间被困，降于孔明车前'},
        {'person_id': 'zhuge_liang', 'role_desc': '设反间赚姜维，执手许以平生之学'},
        {'person_id': 'wang_lang', 'role_desc': '阵前劝降，被孔明痛斥气满胸膛撞死于马下'},
        {'person_id': 'zhao_yun', 'role_desc': '袭天水中姜维之计，力战败走'},
        {'person_id': 'wei_yan', 'role_desc': '诈败诱维入冀城，后袭破其城'},
    ],
    'passage_ids': refs(93, ['姜维', '王朗', '冀城', '伯约']),
}

# ---- E3 + B1 街亭之战（95–96 回，228） ----
b1 = {
    'id': 'jieting_battle', 'name': '街亭之战', 'year': 228,
    'date_text': '建兴六年春（228）',
    'place_id': 'jie_ting', 'event_id': 'jieting_zhi_zhan',
    'belligerents': [
        {'side': '蜀军（马谡）', 'faction_ids': ['shu'], 'commanders': ['ma_su', 'wang_ping', 'wei_yan'],
         'troops_desc': '马谡二万五千守街亭，王平五千为辅，魏延高翔接应'},
        {'side': '魏军（司马懿）', 'faction_ids': ['wei'], 'commanders': ['zhang_he', 'sim_yi', 'guo_huai'],
         'troops_desc': '司马懿十五万出关，张郃为先锋，郭淮别取列柳城'},
    ],
    'result': '马谡违令舍水上山，张郃断其汲道围山放火，蜀兵自乱；街亭列柳城俱失，亮被迫全军退汉中，挥泪斩马谡。',
    'casualties_note': '蜀失街亭列柳城，弃三郡；马谡伏法。魏军几无折损。',
    'summary': '马谡熟读兵书而纸上谈兵，山上屯军被张郃断水围困，兵败失街亭；孔明借空城计退司马懿十五万，归而挥泪斩谡、自贬三等。',
    'detail': '懿料亮必出街亭断其咽喉，张郃引兵径取。谡立军令状守亭，笑拒王平当道下寨之谏：凭高视下势如劈竹，置之死地而后生。郃断汲道，围山自辰至戌，山上无水军不得食，半夜大开寨门降魏；谡禁止不住，驱残兵杀下逃奔。魏延复夺街亭又被懿抄后围困，王平杀入救出；三人劫寨复失，郭淮袭列柳城，诸路皆溃。懿引十五万趋西城，时亮止二千五百军，乃大开四门，焚香操琴于城楼，城门内外二十余百姓洒扫傍若无人；懿疑有伏兵，望北山而退，是为空城计（弹琴退仲达）。亮退军，赵云箕谷断后不折一人一骑。归汉中，谡自缚请罪，亮流涕正军法；蒋琬驰至高叫留人引楚杀得臣典救之不听。亮痛哭曰：非为谡哭，先帝临危曾嘱马谡言过其实不可大用，今果应此言，深恨己之不明。遂上表自贬三等，为右将军行丞相事。',
    'front_line': [
        {'time': 228, 'time_seq': 1, 'kind': '布防', 'label': '谡违平谏', 'desc': '马谡舍五路总口当道之地，屯兵山上；王平引五千离山十里下寨，画图星夜报孔明。', 'lng': 105.66, 'lat': 34.88},
        {'time': 228, 'time_seq': 2, 'kind': '围困', 'label': '郃断汲道', 'desc': '张郃断水围山自辰至戌，蜀兵不战自乱，半夜开寨门降魏。', 'lng': 105.69, 'lat': 34.84},
        {'time': 228, 'time_seq': 3, 'kind': '溃败', 'label': '延复失亭', 'desc': '魏延复夺街亭反被懿抄后围困，王平杀入救出，郭淮袭取列柳城。', 'lng': 105.63, 'lat': 34.9},
        {'time': 228, 'time_seq': 4, 'kind': '奇计', 'label': '空城退敌', 'desc': '懿十五万趋西城，亮二千五百人焚香操琴大开四门，懿疑伏而退。', 'lng': 105.7, 'lat': 34.83},
        {'time': 228, 'time_seq': 5, 'kind': '正法', 'label': '挥泪斩谡', 'desc': '归汉中明正军法斩马谡，蒋琬救之不听；亮自贬三等。', 'lng': 107.0, 'lat': 33.1},
    ],
}
check_persons(b1, 'belligerents')
battles.append(b1)
e3 = {
    'id': 'jieting_zhi_zhan', 'name': '街亭之战', 'kind': '征伐',
    'start_year': 228, 'end_year': 228, 'date_text': '建兴六年春（228）',
    'summary': '马谡违令失街亭，诸葛亮空城退仲达、挥泪斩马谡、自贬三等，一出祁山无功而返。',
    'detail': '详见战役「街亭之战」。此败使蜀弃天水、南安、安定三郡，孔明论败因曰：此病不在兵之多寡，在主将耳；明罚思过，减兵省将以为后图。',
    'place_id': 'jie_ting',
    'parent_event_id': None,
    'participants': [
        {'person_id': 'ma_su', 'role_desc': '立军令状守街亭，违令上山致败，伏法被斩'},
        {'person_id': 'wang_ping', 'role_desc': '力谏当道下寨不听，独率千人鸣鼓自持全军而还'},
        {'person_id': 'zhang_he', 'role_desc': '魏军先锋，断汲道围山，击溃马谡'},
        {'person_id': 'sim_yi', 'role_desc': '都督关西，破街亭后兵指西城，为空城计所退'},
        {'person_id': 'zhuge_liang', 'role_desc': '布防失察，空城退敌，归而斩谡自贬三等'},
        {'person_id': 'wei_yan', 'role_desc': '屯街亭之后接应，复夺街亭又被围，力战得脱'},
    ],
    'passage_ids': refs(95, ['街亭', '马谡', '王平', '操琴']) + refs(96, ['马谡', '蒋琬']),
    'battle_ids': ['jieting_battle'],
}
check_persons(e3, 'participants')
events.append(e3)

# ---- E4 + B2 陈仓之战（97–98 回，229） ----
b2 = {
    'id': 'chencang_battle', 'name': '陈仓之战', 'year': 229,
    'date_text': '建兴六年末至七年初（229）',
    'place_id': 'chen_cang', 'event_id': 'chencang_zhi_zhan',
    'belligerents': [
        {'side': '蜀军（诸葛亮）', 'faction_ids': ['shu'], 'commanders': ['zhuge_liang', 'wei_yan', 'jiang_wei'],
         'troops_desc': '三十万精兵出陈仓道口攻城，魏延拒王双，姜维献袭祁山之计'},
        {'side': '魏军（曹真）', 'faction_ids': ['wei'], 'commanders': ['hao_zhao', 'wang_shuang', 'cao_zhen'],
         'troops_desc': '郝昭三千人守陈仓城，王双二万兵城外为援，曹真都督关西'},
    ],
    'result': '郝昭以三千人拒亮大军二十余日，云梯冲车地道皆破；王双追击中魏延伏计被斩。亮粮尽而退，旋乘郝昭病重袭破陈仓，斩王双取散关。',
    'casualties_note': '蜀折谢雄、龚起二将，张嶷重伤；魏折王双，郝昭病殁。',
    'summary': '郝昭死守陈仓二十余日，说降、云梯、冲车、地道诸法皆破；孔明粮尽退兵，密计使魏延斩王双；旋乘昭病重袭取陈仓，姜维计赚斩费耀。',
    'detail': '懿举郝昭守陈仓道口，料亮必效韩信暗度陈仓之计。亮至，魏延连攻不克；旧交靳祥两度说降，昭拔箭拒之：吾事魏汝事蜀，但有死而已。亮起云梯，昭以火箭齐发烧之；用冲车，昭运石凿眼葛绳穿定飞打折之；令廖化掘地道，昭城中掘重壕横截。昼夜相攻二十余日无计可破。王双来援，三合斩谢雄龚起，流星锤重伤张嶷。姜维献计：守险不战，统大军去袭祁山，假密书诈降曹真。费耀引五万接应，中伏自刎，余众尽降；孔明连夜驱兵直出祁山。粮尽，亮乘魏兵新败密令退军，魏延受计：伏三十骑于双营侧，双追蜀军，营中火起；双勒马回至山坡，魏延骤出林中一刀斩之。旋探得郝昭病重，魏延姜维星夜取陈仓，昭惊死，亮入城令其妻小扶柩归魏；又袭散关败张郃，出建威，三度进逼祁山。',
    'front_line': [
        {'time': 229, 'time_seq': 1, 'kind': '拒降', 'label': '昭拒靳祥', 'desc': '靳祥两度入城说降，郝昭拈弓厉声：但有死而已！', 'lng': 107.24, 'lat': 34.37},
        {'time': 229, 'time_seq': 2, 'kind': '攻城', 'label': '火箭烧梯', 'desc': '云梯冲车地道轮番进攻，昭以火箭飞石重壕一一破之，相持二十余日。', 'lng': 107.25, 'lat': 34.34},
        {'time': 229, 'time_seq': 3, 'kind': '斩将', 'label': '双挫蜀锋', 'desc': '王双连斩谢雄龚起，流星锤重伤张嶷，蜀兵折伤甚多。', 'lng': 107.28, 'lat': 34.32},
        {'time': 229, 'time_seq': 4, 'kind': '诈降', 'label': '维赚费耀', 'desc': '姜维假密书诈降曹真，费耀五万兵中伏自刎，孔明直出祁山。', 'lng': 105.2, 'lat': 34.18},
        {'time': 229, 'time_seq': 5, 'kind': '伏杀', 'label': '延斩王双', 'desc': '亮粮尽密退，王双追击，营中火起回军，山坡上被魏延一刀斩之。', 'lng': 107.21, 'lat': 34.39},
        {'time': 229, 'time_seq': 6, 'kind': '破城', 'label': '袭取陈仓', 'desc': '郝昭病重，魏延姜维星夜袭城，昭惊死；亮怜其忠，扶柩归魏。', 'lng': 107.24, 'lat': 34.35},
    ],
}
check_persons(b2, 'belligerents')
battles.append(b2)
e4 = {
    'id': 'chencang_zhi_zhan', 'name': '陈仓之战', 'kind': '征伐',
    'start_year': 229, 'end_year': 229, 'date_text': '建兴六年末至七年初（229）',
    'summary': '二次北伐顿兵陈仓，郝昭死守二十余日不克；王双中伏被斩，孔明乘虚破城，三出祁山。',
    'detail': '详见战役「陈仓之战」。吴石亭大捷后遣使约蜀伐魏，孔明上后出师表：鞠躬尽瘁，死而后已；遂起三十万精兵以魏延为先锋出陈仓道口。',
    'place_id': 'chen_cang',
    'parent_event_id': None,
    'participants': [
        {'person_id': 'zhuge_liang', 'role_desc': '统大军攻陈仓，粮尽密退，密计斩王双，乘虚破城'},
        {'person_id': 'hao_zhao', 'role_desc': '三千人死守陈仓，拒降破梯折车，惊病而亡'},
        {'person_id': 'wang_shuang', 'role_desc': '虎威将军救陈仓，连斩蜀将；追击中伏被魏延斩'},
        {'person_id': 'wei_yan', 'role_desc': '先锋攻城不克，后受密计斩王双、袭取陈仓散关'},
        {'person_id': 'jiang_wei', 'role_desc': '献袭祁山之计，假密书赚曹真，斩费耀'},
    ],
    'passage_ids': refs(97, ['陈仓', '郝昭', '王双', '流星锤']) + refs(98, ['郝昭', '王双', '魏延']),
    'battle_ids': ['chencang_battle'],
}
check_persons(e4, 'participants')
events.append(e4)

events.insert(0, e1)
events.insert(1, e2)

out = {'comment': 'P4-C（2026-10-29）：第 91–100 回的 4 组事件 + 2 场战役。passage_ids 由本脚本解析生成，禁止手改。',
       'events': events, 'battles': battles}
p = os.path.join(DATA, 'event_battle_ch091_100.json')
io.open(p, 'w', encoding='utf-8').write(json.dumps(out, ensure_ascii=False, indent=2))
print('写出 %s：事件 %d，战役 %d' % (p, len(events), len(battles)))
