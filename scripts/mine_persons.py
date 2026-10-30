#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
严谨人名抽取器（铺量 1200+ 人物 · 第一步）

为什么不用 discover_entities.py：它的 P5「单称回推」把「却说」「只见」拆成
「马却 756 次」「马只 252 次」，噪声淹没真人。本脚本改用**高精度模式 +
多模式投票 + 频次门槛 + 黑名单**，宁可漏、不可滥。

模式（精度降序）：
  M1 自报家门  「姓X，名Y，字Z」/「姓X名Y字Z」/「X，字Y，Z人也」   → 全名+字，最可信
  M2 复姓      「司马懿曰」「夏侯惇引兵」「诸葛亮曰」              → 复姓表命中姓，抽 2–3 字
  M3 单姓+名+动词 「邓芝曰」「张苞大怒」「金祎谓」                  → 姓表 +(1~2 字名)+ 强动词
  M4 全名指代  「(刘)玄德谓」「关云长曰」——交回指/单称处理，不新建卡

判定：候选必须在 ≥1 个高精度模式命中，且：
  · 末字 ∈ NAME_TAIL（人名常用末字）或由 M1 直接给出
  · 不在 PLACES（454 地名 + 别名）、不在 STOPWORDS（常用词/官职/爵称）
  · 全书出现次数 ≥ min_count
  · 不在已建档 known 集合
输出 data/mined_persons.json：{candidates:[{name,count,first_ch,evidence,modes,courtesy?}]}

用法：python3 scripts/mine_persons.py [--min 3] [--top 400]
"""
import json, io, os, re, glob, argparse
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
SRC = os.path.join(DATA, 'source')

# ---- 复姓表（复姓后接 1~2 字名，覆盖「司马懿/司马昭/夏侯惇/诸葛亮/公孙瓒…」）----
COMPOUND = ['诸葛', '司马', '夏侯', '公孙', '太史', '皇甫', '上官', '欧阳', '淳于',
            '单于', '令狐', '慕容', '宇文', '长孙', '尉迟', '万俟', '毌丘', '毋丘',
            '钟离', '濮阳', '鲜于', '拓跋', '秃发', '乞伏', '百里', '东郭', '南宫',
            '羊舌', '微生', '颛孙', '巫马', '乐正', '漆雕', '公西', '左丘', '谷梁',
            '轩辕', '令狐', '呼延', '淳于', '申屠', '东方', '独孤', '赫连', '澹台']

# ---- 单姓表（常见 + 三国多见）----
SURNAMES = set('''
王李张刘陈杨黄赵吴周徐孙马朱胡郭何高林罗郑梁谢宋唐许韩冯邓曹彭曾萧田董袁潘
于蒋蔡余杜叶程苏魏吕丁任沈姚卢姜崔钟谭陆汪范金石廖贾夏韦付方白邹孟熊秦邱
江尹薛段雷侯龙史陶黎贺顾毛郝龚邵万钱严覃武戴莫孔向汤纪舒屈项祝董阮蓝闵席
季麻强路娄危童颜梅盛林刁骆樊凌霍虞支柯管莫经房裘缪干解应宗宣贲邓郁单杭洪
包诸左石崔吉钮龚程嵇邢滑裴陆荣翁荀羊惠甄曲家封芮羿储靳汲邴糜松井富巫乌
焦巴弓牧隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘厉戎祖武符景詹束龙叶幸
司韶郜黎蓟薄印宿白怀蒲邰从鄂索咸籍赖卓蔺屠蒙池乔阴胥能苍双闻莘党翟谭贡
劳逄姬申扶堵冉宰郦雍桑桂濮牛寿通边扈燕冀郏浦尚农温别庄晏柴瞿阎充慕连茹
习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广禄阙沃利蔚越夔隆师
巩厍聂晁勾敖融冷訾辛阚那简饶空毋沙乜养鞠须丰巢关蒯相查后荆红游竺权逯盖
益桓法度真戏俭岑徐管辂华陀陀岱
'''.split())
SURNAMES = set(''.join(SURNAMES)) - set('，。、')

# ---- 人名末字：这些字作姓名末字很常见；用于给 M2/M3 候选背书 ----
NAME_TAIL = set('''
德操坚策权备禅亮瑜肃蒙逊抗昭师炎懿昭丕睿芳髦奂渊惇洪仁纯休尚禁辽郃晃惇
韦典许褚庞德张飞关羽赵云超马岱延仪维遵会艾预濬浑济充秀瓘廙
嘉彧攸诩表琦琮瑁焉璋备度获平统峻芝苞翼嶷化预忠云飞超
布布宫诩汜傕汜奉暹承辑硕让忠珪登圭纪配谭尚熙干
坚策翊匡朗肃瑜程普盖当宁统蒙逊
获孟火锋鹿获
良丑文颜文进选
平特翼
冯习张南傅肜程畿
'''.replace('\n', '').replace(' ', ''))
# 放宽：末字是常见汉字且非明显动词/虚词/时间字即可
BAD_TAIL = set('曰道说讲问答话言语云谓令使唤叫令命请劝谏奏报知闻见看视观望瞧'
               '军队兵马将帅士卒众贼寇敌攻伐征讨战击杀斩诛灭破败胜取夺占据守'
               '退走进出到至来去回归还返逃奔降附叛离分立坐行起伏拜谢辞送迎从随'
               '是为作做成了却在正将要会能可应当须必欲想思意心怒惊喜欢忧惧怕'
               '时年月日岁春夏秋冬初中后前后左右上下内外东西南北方处所里间'
               '一二三四五六七八九十百千万两Sizeof多少众诸各每某此其之乎者也矣焉哉'
               '不无未非莫勿休别弗皆尽悉俱并共同相互与及和以及而且但若则即乃遂'
               '大小长短高低深浅远近新旧好恶美丑善恶真假难易强弱盛衰兴亡生死存'
               '国家朝庭宫府郡州县城乡村寨营寨关隘渡津道路桥山水河江海湖池林')
# 地名/常用词黑名单（整体命中即丢弃）
STOPWORDS = set('''
天子皇帝陛下主公丞相太尉司徒司空大将军将军校尉都尉太守刺史县令县长大人
先主后主先帝今上圣上主上君主诸侯大王殿下阁下足下将军元帅先锋都督总管
先生夫人公子娘子老子孔子孟子孙子墨子庄子
却说且说话说再说不说传说听说闻说闻得只见但见忽见只见却见只见
次日当日即日来日明日今日昨日次日翌日
众将诸将众官百官群臣诸臣众军军士士卒兵士人马军马大军兵将
天下国家朝廷社稷中原四方四海九州
'''.split())

# 强动词：跟在人名后，判定"这是个人在动作/说话"
VERB = '曰谓问应答奏谏怒大怒大喜大惊笑大笑喝叱呼令命引率将带领拜谢辞见闻知视观'
VERB_SET = set('曰谓问答奏谏怒喜惊笑喝叱呼令命引率将带领拜谢辞见闻知视观望')


def load_known():
    """已建档：name + match_surfaces + display_aliases + courtesy"""
    known = set()
    for f in glob.glob(os.path.join(DATA, 'persons_*.json')):
        for p in json.load(io.open(f, encoding='utf-8')).get('persons', []):
            known.add(p['name'])
            for a in (p.get('match_surfaces') or []) + (p.get('display_aliases') or []):
                known.add(a)
            if p.get('courtesy'):
                known.add(p['courtesy'])
    return known


def load_places():
    places = set()
    for p in json.load(io.open(os.path.join(ROOT, 'build', 'places.json'), encoding='utf-8')):
        places.add(p['name'])
        for a in (p.get('aliases') or []):
            places.add(a)
    return places


def load_chapters():
    out = []
    for f in sorted(glob.glob(os.path.join(SRC, 'ch*.txt'))):
        m = re.search(r'ch(\d+)', f)
        out.append((int(m.group(1)), io.open(f, encoding='utf-8').read()))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--min', type=int, default=3)
    ap.add_argument('--top', type=int, default=500)
    a = ap.parse_args()

    known = load_known()
    places = load_places()
    chapters = load_chapters()
    full = ''.join(t for _, t in chapters)
    ch_of_pos = []  # 不精确，用逐章扫描代替

    # {name: {count, modes:set, courtesy:set, evidence:list}}
    hits = defaultdict(lambda: {'count': 0, 'modes': set(), 'courtesy': set(), 'evidence': [], 'first_ch': 999})

    def add(name, mode, ch, ctx, courtesy=None):
        if not name or len(name) < 2 or len(name) > 4:
            return
        if name in known or name in places or name in STOPWORDS:
            return
        # 末字必须是可信人名末字，或来自 M1 自报家门
        if mode != 'M1' and name[-1] in BAD_TAIL:
            return
        h = hits[name]
        h['count'] += 1
        h['modes'].add(mode)
        if courtesy:
            h['courtesy'].add(courtesy)
        if ch < h['first_ch']:
            h['first_ch'] = ch
        if len(h['evidence']) < 4:
            h['evidence'].append({'ch': ch, 'ctx': ctx})

    for ch, text in chapters:
        # M1 自报家门：姓X(，|,)名Y[,，]字Z  —— 最可信
        for m in re.finditer(r'姓([\u4e00-\u9fa5])[，,]?\s*名([\u4e00-\u9fa5]{1,2})[，,]?\s*字([\u4e00-\u9fa5]{1,2})', text):
            add(m.group(1) + m.group(2), 'M1', ch, text[max(0, m.start()-6):m.end()+6], m.group(3))
        for m in re.finditer(r'姓([\u4e00-\u9fa5])[，,]?\s*名([\u4e00-\u9fa5]{1,2})', text):
            add(m.group(1) + m.group(2), 'M1', ch, text[max(0, m.start()-6):m.end()+6])
        # M1b 「(姓名)，字(字)，(某地)人也」
        for m in re.finditer(r'([\u4e00-\u9fa5]{2,3})[，,]\s*字([\u4e00-\u9fa5]{1,2})[，,]\s*[\u4e00-\u9fa5]{2,6}人也', text):
            nm = m.group(1)
            if nm[0] in SURNAMES or nm[:2] in COMPOUND:
                add(nm, 'M1', ch, text[max(0, m.start()-6):m.end()+6], m.group(2))

        # M2 复姓 + 1~2 字名 + 强动词/标点
        for cx in COMPOUND:
            for m in re.finditer(re.escape(cx) + r'([\u4e00-\u9fa5]{1,2})(?=[' + ''.join(VERB_SET) + r'，,。、：:；;！？\s])', text):
                add(cx + m.group(1), 'M2', ch, text[max(0, m.start()-4):m.end()+6])

        # M3 单姓 + 1~2 字名 + 强动词/标点
        # 用「姓」字符类 + 1~2 汉字 + 强动词，贪婪控制
        for m in re.finditer(r'([\u4e00-\u9fa5])([\u4e00-\u9fa5]{1,2})(?=[' + ''.join(VERB_SET) + r'])', text):
            if m.group(1) not in SURNAMES:
                continue
            name = m.group(1) + m.group(2)
            # 名部分末字不能是明显动词/虚词
            if m.group(2)[-1] in BAD_TAIL:
                continue
            add(name, 'M3', ch, text[max(0, m.start()-4):m.end()+6])
        # M3b 单姓 + 单名 + 说话动词（「芝曰」「苞曰」——单名，交由回指，这里只记不建）
        # 暂不启用，避免「却曰」类噪声

    # 二次过滤：频次 + 至少命中 M1 或 (M2/M3 且 count 达标且末字可信)
    result = []
    for name, h in hits.items():
        if h['count'] < a.min:
            continue
        modes = h['modes']
        # 高精度：M1 直接收；M2 复姓收；M3 需更高频次背书
        if 'M1' in modes or 'M2' in modes:
            pass
        elif 'M3' in modes and h['count'] >= a.min * 2:
            pass
        else:
            continue
        result.append({
            'name': name, 'count': h['count'], 'first_ch': h['first_ch'],
            'modes': sorted(modes), 'courtesy': sorted(h['courtesy']),
            'evidence': h['evidence'],
        })
    result.sort(key=lambda x: (-x['count'], x['first_ch']))
    result = result[:a.top]

    out = os.path.join(DATA, 'mined_persons.json')
    json.dump({'total_hits': len(hits), 'kept': len(result), 'candidates': result},
              io.open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'原始候选 {len(hits)} → 过滤后 {len(result)} 条（min={a.min}）')
    print(f'已写出 {out}')
    print('--- 前 60 条（次数|首回|模式|名|样例上下文）---')
    for r in result[:60]:
        ev = r['evidence'][0]['ctx'] if r['evidence'] else ''
        print(f"{r['count']:4d} ch{r['first_ch']:3d} {','.join(r['modes']):7s} {r['name']:5s} {ev}")


if __name__ == '__main__':
    main()
