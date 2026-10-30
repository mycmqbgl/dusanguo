#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P4-E 联动：生成第 111–120 回的 5 组事件 + 2 场战役（data/event_battle_ch111_120.json）。
约束同 gen_events_p3a.py：passage_ids 解析生成，禁止手写；
participants/commanders 仅已建档 id + 本批次新卡 + 其他批次预分配 id。
"""
import json, io, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, 'build')
DATA = os.path.join(ROOT, 'data')

FACTIONS = {'han', 'warlord', 'wei', 'wu', 'shu', 'jin', 'barbarian', 'mystic'}

# 其他批次预分配的人物 id（卡片由别的代理写，此处直接引用，不重复建档）
PREALLOC = {
    'sim_yi', 'lu_xun', 'liu_shan', 'li_yan', 'meng_huo', 'cao_zhen', 'jiang_wei',
    'ma_su', 'wang_ping', 'cao_rui', 'hao_zhao', 'wang_shuang', 'jiang_wan',
    'deng_ai', 'guo_huai', 'cao_shuang', 'gongsun_yuan', 'sun_liang', 'zhuge_ke',
    'wen_yang', 'cao_fang', 'sun_jun', 'yang_yi',
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
person_ids |= PREALLOC


def ref(no, kw):
    hits = [(s, t) for (n, s), t in passages.items() if n == no and kw in t]
    if not hits:
        raise SystemExit('出处解析失败：第 %d 回找不到关键词「%s」' % (no, kw))
    return pids[(no, hits[0][0])]


def refs(no, kws):
    return [ref(no, kw) for kw in kws]


def check_place(pid):
    if pid not in places:
        raise SystemExit('未知地点 %s' % pid)


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


def check_front_line(obj):
    for node in obj['front_line']:
        for k in ('time', 'time_seq', 'kind', 'label', 'desc', 'lng', 'lat'):
            if k not in node:
                raise SystemExit('%s：front_line 节点缺字段 %s' % (obj['id'], k))
        # 坐标须落在某个 place 的 ±0.05 之内
        for pid, p in places.items():
            lng, lat = p.get('lng'), p.get('lat')
            if lng is None or lat is None:
                continue
            if abs(node['lng'] - lng) <= 0.05 and abs(node['lat'] - lat) <= 0.05:
                break
        else:
            raise SystemExit('%s：front_line 坐标 (%s, %s) 不在任何 place 附近' % (obj['id'], node['lng'], node['lat']))


def check_factions(obj):
    for b in obj.get('belligerents', []):
        for f in b['faction_ids']:
            if f not in FACTIONS:
                raise SystemExit('%s：非法 faction_id %s' % (obj['id'], f))


P_SHOUCHUN = 'shou_chun'
P_LUOYANG = 'luo_yang'
P_QISHAN = 'qi_shan'
P_MIANZHU = 'mian_zhu'
P_CHENGDU = 'cheng_du'
P_JIANYE = 'jian_ye'

events, battles = [], []

# ---- B1 + E1 淮南三叛·诸葛诞之役（111–112 回，257–258） ----
b1 = {
    'id': 'huainan_sanzhong_battle', 'name': '淮南三叛·诸葛诞之役', 'year': 257,
    'date_text': '魏甘露二年—三年（257–258）',
    'place_id': P_SHOUCHUN, 'event_id': 'huainan_sanzhong_zhuge_dan',
    'belligerents': [
        {'side': '淮南军（诸葛诞）并吴援', 'faction_ids': ['wei', 'wu'], 'commanders': ['zhuge_dan', 'sun_chen', 'wen_yang'],
         'troops_desc': '诸葛诞聚两淮屯田十余万、新降兵四万，孙綝遣全怿文钦等七万来援'},
        {'side': '魏军（司马昭）', 'faction_ids': ['wei'], 'commanders': ['cao_mao', 'zhong_hui'],
         'troops_desc': '司马昭挟太后天子，起两都之兵二十六万，钟会为谋主'},
    ],
    'result': '钟会以利诱敌、三面围城留南门纵敌，粮尽援绝，文鸯文虎降魏致城内人心瓦解，寿春城破，诸葛诞死于胡奋刀下，淮南三叛至此俱平。',
    'casualties_note': '吴将于诠死节；诸葛诞麾下数百人无一降者尽被杀；吴兵大半降魏，钟会谏昭放归江南以显宽大。',
    'summary': '诸葛诞讨司马昭，联吴困守寿春；钟会献策攻心，围城经年城破，诞死节，三叛俱平。',
    'detail': '贾充试探禅代之言，诞怒斥：朝廷有难，吾当以死报之！知乐綝密告，遂杀綝举兵，送子诸葛靓入吴为质，聚兵十六万。昭挟魏主曹髦亲征二十六万。初战王基破朱异、唐咨。诞、钦会合吴兵来决战，钟会曰：吴兵之助诸葛诞，实为利也；以利诱之，则必胜矣。魏军弃牛马驴骡于阵，南兵争取无心恋战，两路伏兵杀出，诞大败入城。会又献三面围城、留南门纵走之策，昭抚其背曰：君真吾之子房也！孙綝怒斩累败之朱异，自回建业，外援遂绝。城中粮尽，诞杀文钦，其二子文鸯文虎越城降魏，昭纳钟会之谏赦而用之，绕城宣示，城内人人思降。魏兵四面攻城，守将曾宣献北门，诞出走被胡奋斩于吊桥边。昭灭诞三族；其部卒数百人缚于城外逐一问降，无一人屈者，昭叹而尽杀之。',
    'front_line': [
        {'time': 257, 'time_seq': 1, 'kind': '起兵', 'label': '斩乐綝举兵', 'desc': '诞知贾充告变，攻扬州斩乐綝，聚兵十余万，质子入吴求援。', 'lng': 116.78, 'lat': 32.58},
        {'time': 257, 'time_seq': 2, 'kind': '野战', 'label': '以利诱敌', 'desc': '钟会令弃牛马驴骡遍野，南兵争取无心恋战，伏兵杀出，诞大败退入寿春。', 'lng': 116.6, 'lat': 32.2},
        {'time': 257, 'time_seq': 3, 'kind': '围城', 'label': '三面留门', 'desc': '钟会献策留南门大路容贼自走，走而击之，并断吴兵粮道。', 'lng': 116.78, 'lat': 32.58},
        {'time': 257, 'time_seq': 4, 'kind': '援绝', 'label': '朱异被斩', 'desc': '孙綝怒斩累败之朱异，自回建业；全怿全端得家书开门出降。', 'lng': 117.66, 'lat': 32.88},
        {'time': 258, 'time_seq': 5, 'kind': '攻心', 'label': '文鸯来投', 'desc': '诞杀文钦，鸯虎兄弟越壕降魏获封，绕城劝降，城内人心瓦解。', 'lng': 116.78, 'lat': 32.58},
        {'time': 258, 'time_seq': 6, 'kind': '破城', 'label': '寿春城破', 'desc': '曾宣献北门，诞出走被胡奋斩于吊桥；部曲数百人无一降者。', 'lng': 116.78, 'lat': 32.58},
    ],
}
check_persons(b1, 'belligerents')
check_factions(b1)
check_place(b1['place_id'])
check_front_line(b1)
battles.append(b1)

e1 = {
    'id': 'huainan_sanzhong_zhuge_dan', 'name': '淮南三叛·诸葛诞之役', 'kind': '征伐',
    'start_year': 257, 'end_year': 258, 'date_text': '魏甘露二年—三年（257–258）',
    'summary': '诸葛诞拒贾充试探，起兵寿春讨司马昭，联吴拒守经年，城破死节，淮南三叛至此俱平。',
    'detail': '详见战役「淮南三叛·诸葛诞之役」。诞部曲数百人缚于城外无一降者，昭尽杀而葬之；钟会因谏放归吴兵、宽大收心，威名日盛。姜维乘淮南之役伐魏，闻诞已败，引兵还汉中。',
    'place_id': P_SHOUCHUN, 'parent_event_id': None,
    'participants': [
        {'person_id': 'zhuge_dan', 'role_desc': '起兵讨司马昭，困守寿春，城破死节'},
        {'person_id': 'zhong_hui', 'role_desc': '司马昭谋主，献以利诱敌、三面围城之策'},
        {'person_id': 'cao_mao', 'role_desc': '被司马昭挟持同征淮南'},
        {'person_id': 'sun_chen', 'role_desc': '吴辅政，遣七万兵援寿春，怒斩朱异而回'},
        {'person_id': 'wen_yang', 'role_desc': '随父文钦守城，父被诞杀，与弟文虎降魏获封'},
        {'person_id': 'jiang_wei', 'role_desc': '乘虚伐魏取长城，闻寿春已平而退兵'},
    ],
    'passage_ids': refs(111, ['诸葛诞', '贾充', '孙綝', '寿春']) + refs(112, ['寿春', '文鸯', '钟会', '于诠']),
    'battle_ids': ['huainan_sanzhong_battle'],
}
check_persons(e1, 'participants')
events.append(e1)

# ---- E2 曹髦驱车死南阙（114 回，260） ----
e2 = {
    'id': 'cao_mao_nan_que', 'name': '曹髦驱车死南阙', 'kind': '人物',
    'start_year': 260, 'end_year': 260, 'date_text': '魏甘露五年（260）',
    'summary': '曹髦不堪坐受废辱，率宿卫三百人仗剑讨司马昭，被成济一戟刺死于南阙辇旁；陈泰披麻哭灵，言独斩贾充可谢天下。',
    'detail': '司马昭带剑上殿求加九锡，髦低头不答，昭冷笑下殿。髦归宫泣召王沈、王经、王业：司马昭将怀篡逆，人所共知！朕不能坐受废辱！经泣谏：重权已归司马氏久矣，陛下若不隐忍，祸莫大焉。髦曰：是可忍也，孰不可忍也！朕意已决，便死何惧！遂率宿卫苍头官僮三百余人，仗剑升辇，径出南阙。贾充戎服引数千铁甲禁兵拒之，禁兵见天子皆不敢动，充呼成济：司马公养你何用？济撚戟刺髦，刃从背上透出，死于辇傍。昭佯惊以头撞辇而哭。陈泰独不至，披麻带孝哭拜灵前，曰：独斩贾充，少可以谢天下耳；再问其次，泰曰：惟有进于此者，不知其次。昭卒诛成济以塞责，收王经全家，经母子含笑受刑。是年六月昭立曹奂，改元景元。',
    'place_id': P_LUOYANG, 'parent_event_id': None,
    'participants': [
        {'person_id': 'cao_mao', 'role_desc': '魏主，仗剑率三百宿卫讨司马昭，死于成济戟下'},
        {'person_id': 'chen_tai', 'role_desc': '尚书仆射，披麻哭灵，言独斩贾充可谢天下'},
        {'person_id': 'zhong_hui', 'role_desc': '昭府心腹，预司马氏篡魏之局'},
    ],
    'passage_ids': refs(114, ['南阙', '成济', '潜龙诗']),
}
check_persons(e2, 'participants')
check_place(e2['place_id'])
events.append(e2)

# ---- E3 姜维斗阵破邓艾（113 回，256） ----
e3 = {
    'id': 'qishan_douzhen', 'name': '姜维祁山斗阵破邓艾', 'kind': '征伐',
    'start_year': 256, 'end_year': 256, 'date_text': '蜀景耀元年（256）',
    'summary': '姜维按武侯八阵法布阵，变长蛇卷地阵困邓艾于垓心，夺祁山九寨；邓艾遂行反间计，黄皓谗言召维班师。',
    'detail': '孙休即位诛孙綝后，姜维大起蜀兵二十万出祁山。邓艾先度地脉，挖地道夜袭蜀左寨，维按兵不动以弓弩却敌，艾叹：兵在夜而不惊，将闻变而不乱，真将才也！次日两军斗阵：维按天地风云鸟蛇龙虎布八阵，艾效之；维把旗一招，变长蛇卷地阵，将艾困于垓心，蜀兵齐叫邓艾早降，艾仰天叹：我一时自逞其能，中姜维之计矣！赖司马望从西北角杀入救出，祁山九寨尽被蜀夺。望识阵法因幼年游学荆南。艾复使望斗阵为饵、自袭山后，廖化斩先锋郑伦，艾身被四箭大败。艾遂用反间：党均赍金宝结黄皓，布散流言，后主星夜宣维还朝，维叹：又成画饼矣。廖化谏将在外君命有所不受，维以蜀人怨望，依法退兵。',
    'place_id': P_QISHAN, 'parent_event_id': None,
    'participants': [
        {'person_id': 'jiang_wei', 'role_desc': '大将军，布八阵变长蛇卷地阵困邓艾，夺祁山九寨'},
        {'person_id': 'deng_ai', 'role_desc': '地道夜袭、效布八阵被困，败后行反间计'},
        {'person_id': 'liu_shan', 'role_desc': '听信黄皓谗言，星夜诏维班师'},
    ],
    'passage_ids': refs(113, ['斗阵', '八阵', '长蛇', '邓艾']),
}
check_persons(e3, 'participants')
check_place(e3['place_id'])
events.append(e3)

# ---- B2 + E4 偷度阴平·绵竹之战（117 回，263） ----
b2 = {
    'id': 'toudu_yinping_battle', 'name': '偷度阴平·绵竹之战', 'year': 263,
    'date_text': '魏景元四年（263）',
    'place_id': P_MIANZHU, 'event_id': 'toudu_yinping_mianzhu',
    'belligerents': [
        {'side': '魏军（邓艾）', 'faction_ids': ['wei'], 'commanders': ['deng_ai', 'zhong_hui'],
         'troops_desc': '邓艾裹毡滚下摩天岭，二千疲兵偷度阴平；钟会以云梯炮架攻剑阁牵制姜维'},
        {'side': '蜀军（诸葛瞻）', 'faction_ids': ['shu'], 'commanders': ['zhuge_zhan', 'jiang_wei'],
         'troops_desc': '瞻领成都兵七万拒于绵竹；维、廖化、张翼守剑阁'},
    ],
    'result': '邓艾先破江油、涪城，绵竹之下诸葛瞻拒降力战自刎，子诸葛尚战死，绵竹陷落；后主听谯周之言出降，蜀汉灭亡。',
    'casualties_note': '诸葛瞻、诸葛尚、张遵、黄崇、李球皆死；马邈之妻李氏骂夫自缢；邓艾怜瞻父子忠，合葬之。',
    'summary': '邓艾自阴平凿山裹毡七百里无人之境，江油纳降、涪城降附，绵竹力战破诸葛瞻父子，蜀汉遂亡。',
    'detail': '钟会、邓艾分道伐蜀，维守剑阁，会久攻不下。艾献计出阴平小路：行七百余里无人之地，至摩天岭峻壁不能开凿，艾取毡自裹其身先滚下去，无毡者以绳索束腰攀木挂树而下，二千余人尽度。岭傍石碣刻武侯题：二火初兴，有人越此；二士争衡，不久自死。江油守将马邈不备，其妻李氏唾面责之忠义，邈出降，李氏自缢，艾厚葬致祭。涪城官吏军民疑天降尽降。瞻受三诏领兵七万，子尚为先锋：列八阵、车上木刻孔明遗像，师纂邓忠惊走，蜀兵掩杀二十余里。艾遗书许封琅琊王，瞻扯书斩使。艾两伏兵夹击，瞻困于垓心中箭，大呼：吾力竭矣，当以一死报国！自刎而死；尚策马死于阵中。艾得绵竹，兵临成都，后主用谯周之议，面缚舆榇出降，汉亡。',
    'front_line': [
        {'time': 263, 'time_seq': 1, 'kind': '偷渡', 'label': '裹毡下岭', 'desc': '邓艾自阴平行七百里无人之境，裹毡滚下摩天岭，二千余人尽度。', 'lng': 104.68, 'lat': 32.94},
        {'time': 263, 'time_seq': 2, 'kind': '纳降', 'label': '江油献城', 'desc': '马邈不备出降，其妻李氏骂夫自缢；涪城军民尽降。', 'lng': 104.68, 'lat': 31.47},
        {'time': 263, 'time_seq': 3, 'kind': '对阵', 'label': '木像退敌', 'desc': '诸葛瞻列八阵，木刻武侯遗像惊走师纂邓忠，蜀兵掩杀二十余里。', 'lng': 104.2, 'lat': 31.34},
        {'time': 263, 'time_seq': 4, 'kind': '死战', 'label': '瞻父子殉国', 'desc': '瞻扯书斩使，被围自刎报国，诸葛尚策马死于阵中，绵竹陷落。', 'lng': 104.2, 'lat': 31.34},
        {'time': 263, 'time_seq': 5, 'kind': '亡国', 'label': '后主出降', 'desc': '谯周力主降魏，后主面缚舆榇出北门十里而降，姜维在剑阁闻讯大惊失语。', 'lng': 104.07, 'lat': 30.66},
    ],
}
check_persons(b2, 'belligerents')
check_factions(b2)
check_place(b2['place_id'])
check_front_line(b2)
battles.append(b2)

e4 = {
    'id': 'toudu_yinping_mianzhu', 'name': '偷度阴平·绵竹之战', 'kind': '征伐',
    'start_year': 263, 'end_year': 263, 'date_text': '魏景元四年（263）',
    'summary': '邓艾裹毡偷度阴平七百里险径，绵竹力战灭诸葛瞻父子，后主舆榇出降，蜀汉灭亡。',
    'detail': '详见战役「偷度阴平·绵竹之战」。钟会兵困剑阁之功尽为艾所夺，自此二人有隙。维得后主敕命，帐下众将拔刀砍石，号哭之声闻数十里；维以善言抚之，密谋复汉，遍竖降旗赴钟会军前诈降。',
    'place_id': P_MIANZHU, 'parent_event_id': None,
    'participants': [
        {'person_id': 'deng_ai', 'role_desc': '偷度阴平，破江油涪城，绵竹破瞻，受后主之降'},
        {'person_id': 'zhuge_zhan', 'role_desc': '受诏拒敌，绵竹拒降，父子死国'},
        {'person_id': 'zhong_hui', 'role_desc': '以重兵牵制剑阁姜维，为艾偷度创造战机'},
        {'person_id': 'jiang_wei', 'role_desc': '守剑阁拒钟会，闻绵竹陷、后主降，设计诈降钟会'},
        {'person_id': 'liu_shan', 'role_desc': '听谯周之议，面缚舆榇出降，蜀汉亡'},
    ],
    'passage_ids': refs(117, ['阴平', '摩天岭', '江油', '绵竹', '诸葛瞻']),
    'battle_ids': ['toudu_yinping_battle'],
}
check_persons(e4, 'participants')
events.append(e4)

# ---- E5 二士争功·姜维计败（118–119 回，264） ----
e5 = {
    'id': 'ershi_zhenggong', 'name': '二士争功·姜维计败', 'kind': '人物',
    'start_year': 264, 'end_year': 264, 'date_text': '魏咸熙元年（264）',
    'summary': '钟会诬收邓艾，姜维诈降教会据蜀谋反；魏将内外相应兵变，会死于乱箭、维自刎、艾死于田续之手，复汉之谋终败。',
    'detail': '姜维降钟会，会折箭为誓结为兄弟。维以密书与后主：望陛下忍数日之辱，维将使社稷危而复安，日月幽而复明。会与维相谮，司马昭疑艾专恣，令会收之；维教先遣卫瓘往，艾若杀瓘则反情实矣。瓘先发檄文二三十道，鸡鸣突入缚艾父子于槛车。会既并艾军马，威声大震，维以韩信、文种之祸动之：何不泛舟绝迹，登峨嵋之岭？会笑曰：吾年未四旬，方思进取！遂矫郭太后遗诏讨司马昭，元宵宴上逼诸将佥名，不从者困于宫中，欲坑杀之。胡烈、胡渊父子以丘建通消息，密约正月十八日兵变。卫瓘深喜其谋。维领武士方欲杀诸将，心疼昏倒，外兵已砍开殿门，会掣剑立杀数人，被乱箭射倒枭首；维往来冲突，仰天大叫：吾计不成，乃天命也！自刎而死，时年五十九，魏兵共剖其腹，胆大如鸡卵。邓艾父子亦死于田续刀下。后主迁洛阳，昭封安乐公，问：颇思蜀否？答：此间乐，不思蜀也。',
    'place_id': P_CHENGDU, 'parent_event_id': None,
    'participants': [
        {'person_id': 'jiang_wei', 'role_desc': '诈降钟会，密书后主谋复汉室；事败自刎，年五十九'},
        {'person_id': 'zhong_hui', 'role_desc': '诬收邓艾，据成都矫诏谋反，兵变中死于乱箭'},
        {'person_id': 'deng_ai', 'role_desc': '为会所收槛车赴洛，田续追斩于绵竹'},
        {'person_id': 'liu_shan', 'role_desc': '迁洛阳封安乐公，乐不思蜀'},
    ],
    'passage_ids': refs(118, ['姜维', '钟会', '邓艾']) + refs(119, ['卫瓘', '胡渊', '自刎']),
}
check_persons(e5, 'participants')
check_place(e5['place_id'])
events.append(e5)

# ---- E6 三分归晋（120 回，280） ----
e6 = {
    'id': 'sanfen_gui_jin', 'name': '三分归晋', 'kind': '征伐',
    'start_year': 280, 'end_year': 280, 'date_text': '晋太康元年（280）',
    'summary': '杜预王濬大举伐吴，铁索横江一夕而破，王濬先入石头城，孙皓舆榇出降，三国归晋，天下一统。',
    'detail': '羊祜临终荐杜预，遗策灭吴。炎拜预为大都督，与王濬、王浑、司马伷、王戎、胡奋六路伐吴。预夜遣周旨八百人渡江袭乐乡，阵斩吴帅孙歆，克江陵，谓诸将：今兵威大振，如破竹之势，数节之后皆迎刃而解。王濬楼船顺流：吴以铁索横江、铁锥置水，濬作大筏拔锥、燃炬烧索，须臾融断，所至无前。张悌、沈莹战死于牛渚之役。吴人碎割岑昏，张象开城，孙皓效安乐公故事舆榇自缚出降，濬释缚焚榇，吴四州四十三郡皆归晋。炎执杯流涕曰：此羊太傅之功也，惜其不亲见之耳！皓至洛阳，帝曰：朕设此座以待卿久矣；皓对：臣于南方亦设此座以待陛下。封归命侯。自此三国归于晋帝司马炎，为一统之基矣——天下大势，合久必分，分久必合。',
    'place_id': P_JIANYE, 'parent_event_id': None,
    'participants': [
        {'person_id': 'wang_jun', 'role_desc': '龙骧将军，楼船顺流烧索拔锥，先入石头城受孙皓之降'},
        {'person_id': 'du_yu', 'role_desc': '伐吴大都督，夜袭乐乡克江陵，势如破竹'},
        {'person_id': 'sun_hao', 'role_desc': '吴末帝，拒谏失政，舆榇自缚出降，封归命侯'},
    ],
    'passage_ids': refs(120, ['王濬', '铁索', '石头城', '孙皓']),
}
check_persons(e6, 'participants')
check_place(e6['place_id'])
events.append(e6)

out = {'comment': 'P4-E（2026-10-29）：第 111–120 回的 5 组事件 + 2 场战役。passage_ids 由本脚本解析生成，禁止手改。',
       'events': events, 'battles': battles}
p = os.path.join(DATA, 'event_battle_ch111_120.json')
io.open(p, 'w', encoding='utf-8').write(json.dumps(out, ensure_ascii=False, indent=2))
print('写出 %s：事件 %d，战役 %d' % (p, len(events), len(battles)))
