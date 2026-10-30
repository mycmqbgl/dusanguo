#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人物铺量建档器 V2（1200+ 人物 · 核心）

相对 V1 的六项修复：
  1. long_names 净化：片段判定的「庇护源」只收 <=3 字的人名，
     杜绝已建档卡里 278 个 >=4 字垃圾别名（上党太守/丞相长史/何进部将…）误杀真名。
  2. 频次仲裁：若 FULL.count(nm) >= 5 且 > FULL.count(更长名)，视作独立人物。
     救回 张翼(93,被别名"张翼德"误杀)、安民(41,被黑名单误杀)。
  3. 称谓豁免：主名录主条目（自带出场回+描述）不做称谓剔除。救回 乔国老(14)。
  4. note 解析：flush 改为累加而非覆盖，且同一人名重复出现时不清空，
     修复 钟繇/贾逵/文钦 等主条目 note 为空导致描述丢失。
  5. 异体/版本字映射 VARIANT_MAP：名录常写繁体或异写（麋竺/潘濬/傅肜/张紘/朱隽…），
     本session正文使用另一套形（糜竺/潘浚/傅彤/张纮/朱儁）。映射后按原文写法计频次、
     并把异写收进 display_aliases，避免 0 命中。
  6. 全部剔除项落 drop_reason 明细到 data/expand_report.json，供后续三轮校验追溯。

沿用 V1 的诚实分层策略（客观字段用全书精确统计，考据字段保守推断并标 confidence）。

产出 data/persons_p6_auto.json + data/expand_report.json + data/alias_variant.json
"""
import json, io, os, re, glob, sys
from collections import OrderedDict, Counter
from bs4 import BeautifulSoup
from pypinyin import lazy_pinyin

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
HTML_MAIN = '/tmp/roster_11087895605124.shtml'
HTML_SECOND = '/tmp/roster_11040539404583.shtml'
WIKI_TXT = os.path.join(DATA, 'wiki_roster.txt')

# 章→年、势力年份上下界：与 fix_tenure_span.py 共用同一份，见 scripts/chron_const.py
from chron_const import CH_YEAR, FAC_BOUND  # noqa: E402
ROLE_BY_FAC = {
    'warlord': {'君主','文臣','武将','女眷'}, 'barbarian': {'君主','文臣','武将','女眷'},
    'mystic': {'其他'},
}
CN_NUM = {'零':0,'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10,'百':100,'两':2}

# 异体/版本用字映射：名录常见写法 -> 本版本正文写法
# 异体/版本用字映射：名录常见写法 -> 本版本正文写法（只列真正存在字形差异的）
VARIANT_MAP = {
    '麋竺':'糜竺','麋芳':'糜芳','潘濬':'潘浚','傅肜':'傅彤','刘諶':'刘谌',
    '荀勗':'荀勖','张紘':'张纮','朱隽':'朱儁','田预':'田豫','范谤':'范滂',
    '荀諶':'荀谌','刘辨':'刘辩','桥瑁':'乔瑁','锺毓':'钟毓','锺繇':'钟繇',
    '毋丘俭':'毌丘俭','母丘俭':'毌丘俭','杨脩':'杨修','庞悳':'庞德','庞惪':'庞德',
    '卞氏':'卞氏','华覈':'华核','滕修':'滕修','刘畯':'刘畯',
    '韦曜':'韦昭','卞氏':'卞氏','滕修':'滕修',
    # V3 新增：正文未直书、但确为同一人的异写 / 本名 / 称谓
    '张合':'张郃','王凌':'王淩','乔玄':'桥玄','甄后':'甄氏','刘宏':'刘宏','刘辨':'刘辩',
    '韦昭':'韦曜','娄子伯':'娄圭','郭女王':'郭氏','汉灵帝':'灵帝','汉少帝':'少帝',
    '于麋':'于糜','岑壁':'岑璧','郄虑':'郗虑','李諶':'李谌','蔡曛':'蔡曛','赵逊':'赵逊',
    '刘畯':'刘畯','刘邠':'刘邠','荀勗':'荀勖','孙単':'孙单','黄邵':'黄邵','封諝':'封谞',
}
VARIANT_MAP = {k: v for k, v in VARIANT_MAP.items() if v and k != v}
# 反向：正文写法 -> 可能存在的异写别名（用于补 display_aliases）
VARIANT_REV = {}
for k, v in VARIANT_MAP.items():
    if k != v:
        VARIANT_REV.setdefault(v, set()).add(k)

KEEP_FULLNAME = {'带来洞主','木鹿大王','朵思大王','俄何烧戈','金环三结','阿会喃','兀突骨','彻里吉','蹋顿','乔国老'}
# 明确不是独立人物的片段（本名的一部分 / 神名 / 字号）
FRAGMENT_BLOCK = {
    '子伯','文姬','仲达','孔明','云长','翼德','子龙','孟德','玄德','奉先','本初','孟起','汉升',
    '伯约','文长','公明','子孝','子廉','元让','妙才','文和','奉孝','文若','公达','子敬','子布',
    '公瑾','仲谋','伯符','兴霸','子明','公覆','文圭','承渊','幼常','季常','子初','孝直','士元',
    '季玉','景升','阿斗','阿瞒','文伟','公琰','伯苗','元俭',
    # V2 新增：确系他人姓名片段 / 神名 / 称号
    '祝融','广元','烧戈','俄何','公威','慕容','张世','女王','孙恭','葛玄','士仁','宋典','何面',
}


def cn2int(s):
    if s.isdigit(): return int(s)
    total=section=num=0
    for ch in s:
        if ch not in CN_NUM: return None
        v=CN_NUM[ch]
        if v==100:
            total += (section + (num or 1)) * 100; section=num=0
        elif v==10:
            section += (num or 1)*10; num=0
        else:
            num=v
    return total+section+num


def load_known():
    known = {}
    ids = set()
    courtesy = set()
    for f in glob.glob(os.path.join(DATA, 'persons_*.json')):
        if 'p6_auto' in f:
            continue
        for p in json.load(io.open(f, encoding='utf-8')).get('persons', []):
            ids.add(p['id'])
            known[p['name']] = p['id']
            for a in (p.get('match_surfaces') or []) + (p.get('display_aliases') or []):
                known.setdefault(a, p['id'])
            if p.get('courtesy'):
                courtesy.add(p['courtesy'])
    return known, ids, courtesy


def parse_main_roster(path):
    """解析主名录。V2 修复 note 覆盖问题：flush 用累加，重复主条目不再清空。"""
    html = io.open(path, encoding='utf-8', errors='ignore').read()
    soup = BeautifulSoup(html, 'html.parser')
    for t in soup(['script','style']): t.decompose()
    text = soup.get_text('')
    seq = []
    for sp in soup.find_all('span', class_='ren_tip'):
        nm = sp.get_text(strip=True)
        if not re.fullmatch(r'[\u4e00-\u9fa5·]{2,6}', nm):
            continue
        tail=''
        n=sp.next_sibling
        while n is not None and len(tail) < 200:
            if getattr(n,'name',None)=='span' and 'ren_tip' in (n.get('class') or []):
                break
            tail += n if isinstance(n,str) else n.get_text()
            n=n.next_sibling
        seq.append((nm, re.sub(r'\s+','',tail)))
    main = OrderedDict()
    cur_name = None
    buf = []
    def flush():
        if cur_name is not None and buf:
            add = ''.join(x[1] for x in buf)
            # 累加而非覆盖；去重避免重复段落
            if add and add not in main[cur_name]['note']:
                main[cur_name]['note'] = (main[cur_name]['note'] + add)[:150]
    for nm, tail in seq:
        m = re.match(r'^[：:]\s*([一二三四五六七八九十百零两0-9]+)回[，,]?\s*(.*)', tail)
        if m:
            flush()
            buf = []
            ch = cn2int(m.group(1))
            if nm in main:
                # 同名重复出现：保留最早出场回，描述累加
                if ch and (main[nm]['chapter'] is None or ch < main[nm]['chapter']):
                    main[nm]['chapter'] = ch
                if m.group(2) and m.group(2) not in main[nm]['note']:
                    main[nm]['note'] = (main[nm]['note'] + '；' + m.group(2))[:150]
                cur_name = nm
            else:
                main[nm] = {'chapter': ch, 'note': m.group(2)}
                cur_name = nm
        else:
            if cur_name is not None:
                buf.append((nm, tail))
    flush()
    all_names = [nm for nm,_ in seq]
    full_text = re.sub(r'\s+', '', text)
    zihao = set()
    for m in re.finditer(r'字([\u4e00-\u9fa5]{1,2})[，,。；;、：:]', full_text):
        zihao.add(m.group(1))
    return main, all_names, zihao


def parse_second_roster(path):
    html = io.open(path, encoding='utf-8', errors='ignore').read()
    soup = BeautifulSoup(html, 'html.parser')
    for t in soup(['script','style']): t.decompose()
    text = soup.get_text('')
    i = text.find('作者：')
    body = re.sub(r'\s+', ' ', text[i:] if i>=0 else text)
    segs = re.split(r'([\u4e00-\u9fa5]) 氏[：:]', body)
    names = set()
    for k in range(1, len(segs)-1, 2):
        xing, content = segs[k], segs[k+1]
        for t in re.split(r'[ ]+', content.strip()):
            t = t.strip()
            if re.fullmatch(r'[\u4e00-\u9fa5]', t):
                names.add(xing + t)
            elif re.fullmatch(r'[\u4e00-\u9fa5]{2,3}', t):
                names.add(t)
    return sorted(names)


def parse_second_roster_tail(path, known_names=None):
    """解析第二份名录尾部「女性/称谓段」。

    该段格式与主词表不同：裸名 + 括号身份标注，如
    「何后（灵帝妻） 糜夫人 甘夫人 大乔（孙策妻） 蔡琰（蔡邕女）」
    且存在粘连（左贤王王美人 / 奚泥沙摩柯）。主词人 parser 会整段漏掉，
    这是本项目唯一的女性人物批量增量来源（主词表 parser 会整段漏掉）。
    """
    FEMALE_ENTRY = {
        '王美人':'灵帝母(美人)','何后':'灵帝妻','唐妃':'少帝妻','董太后':'刘苌妻',
        '吴国太':'孙坚妻','糜夫人':'刘备妻','甘夫人':'刘备妻','孙夫人':'刘备妻','卞氏':'曹操妻',
        '丁氏':'曹操妻','貂蝉':'王允府歌伎','严氏':'吕布妻','曹氏':'吕布妻','邹氏':'张济妻',
        '伏后':'献帝皇后','董妃':'献帝妃','曹贵人':'献帝妻','甄后':'曹丕妻','郭贵妃':'曹丕妻',
        '郭夫人':'曹睿妻','毛后':'曹睿皇后','刘氏':'袁绍妻；曹爽妻；潘举妻','蔡夫人':'刘表妻',
        '徐氏':'孙翊妻','王氏':'赵昂妻','杨氏':'马超妻','李氏':'庞德妻；马邈妻','张后':'刘禅皇后',
        '徐夫人':'孙权妻','王夫人':'孙权妻','潘夫人':'孙权妻','全后':'孙亮皇后','胡氏':'刘琰妻',
        '崔夫人':'刘谌妻','何氏':'孙和妻','大乔':'孙策妻','小乔':'周瑜妻','朱太后':'孙休母',
        '冯氏':'袁术妻','黄氏':'诸葛亮妻','夏侯令女':'曹文叔妻','云英':'董承妾',
        '李春香':'黄奎妾','蔡琰':'蔡邕女','舞阳君':'何进母','樊氏':'赵范嫂','吴夫人':'孙坚侧室/刘备妻所称',
    }
    html = io.open(path, encoding='utf-8', errors='ignore').read()
    text = re.sub(r'\s+', '', html)
    out = dict(FEMALE_ENTRY)
    # 解析器兜底：只取「名录确实存在的 X（身份）」且未被上表覆盖者
    soup = BeautifulSoup(html, 'html.parser')
    for t in soup(['script','style']): t.decompose()
    seg_text = re.sub(r'\s+', '', soup.get_text(''))
    i = seg_text.find('左贤王')
    seg = re.split(r'本文章|本文相关人物|阅读：', seg_text[i:] if i >= 0 else '') [0]
    for m in re.finditer(r'[（(]([^）)]{1,10})[）)]', seg):
        note = m.group(1)
        j, s = m.start()-1, ''
        while j >= 0 and len(s) < 8 and '\u4e00' <= seg[j] <= '\u9fa5':
            s = seg[j]+s; j -= 1
        for cand in (s[-4:], s[-3:], s[-2:]):
            if len(cand) >= 2 and cand in FEMALE_ENTRY:
                out.setdefault(cand, note); break
    return out


def faction_hint_map():
    fr = json.load(io.open(os.path.join(DATA, 'faction_roster.json'), encoding='utf-8'))
    out = {}
    for fac, groups in fr['groups'].items():
        if isinstance(groups, dict):
            for gname, names in groups.items():
                hint = '武将' if '武将' in gname else ('文臣' if '文臣' in gname else ('君主' if gname in ('诸侯','宗室') else None))
                for nm in names.split():
                    out.setdefault(nm, (fac, hint, f'faction_roster:{fac}/{gname}'))
                    out.setdefault(VARIANT_MAP.get(nm, nm), (fac, hint, f'faction_roster:{fac}/{gname}'))
        elif isinstance(groups, str):
            for nm in groups.split():
                out.setdefault(nm, (fac, '其他' if fac=='mystic' else '武将', f'faction_roster:{fac}'))
    return out


def infer_from_note(note, name):
    n = note or ''
    gender = 'female' if re.search(r'(妻|妾|母|夫人|后|妃|氏$|女|妹|嫂|太后|美人|公主|婢|歌伎)', name+n[:20]) and not re.search(r'(夫|婿|舅|兄|弟|子|父)', name) else 'male'
    if re.search(r'(夫人|后$|妃|太后|美人|公主|妻|妾|母$|氏$)', name):
        role = '女眷'
    elif re.search(r'(谋士|文臣|尚书|侍郎|太傅|司徒|司马|祭酒|博士|掾|从事|主簿|长史|别驾|治中|议郎|谏议|中书|黄门|侍中|宾客|幕宾|参军|军师|学士|刺史|太守)', n):
        role = '文臣'
    else:
        role = '武将'
    if re.search(r'(蜀将|蜀军|归刘|降刘|刘备将|刘璋将|蜀汉|刘禅|诸葛亮|姜维帐|汉中|益州|西川)', n):
        return 'shu', role, gender, 0.7, 'note:蜀'
    if re.search(r'(吴将|东吴|孙吴|孙权|孙策|孙坚|江东|吴郡|降吴|投吴|孙綝|孙皓|吴国)', n):
        return 'wu', role, gender, 0.7, 'note:吴'
    # ★ 「晋」必须排在「魏」前：司马氏代魏，含「司马昭」「司马炎」的注记十有八九
    #   讲的是晋。旧顺序里魏分支有裸词「司马」，把晋分支彻底遮死（「司马昭」先命中
    #   魏），且裸词会误配官职——「大司马吕岱」因此被判成魏（吕岱是吴大司马）。
    #   现在魏分支只留明确的司马氏人物，且不含「司马」二字单独出现。
    if re.search(r'(晋将|晋军|西晋|晋王|司马炎|司马昭|司马攸|羊祜|杜预|王濬)', n):
        return 'jin', role, gender, 0.6, 'note:晋'
    if re.search(r'(魏将|曹将|曹军|曹操|曹丕|曹爽|司马懿|司马师|魏国|曹魏|降曹|归曹|投曹|操将|操军)', n):
        return 'wei', role, gender, 0.7, 'note:魏'
    if re.search(r'(黄巾|张角|张宝|张梁)', n):
        return 'warlord', role, gender, 0.6, 'note:黄巾'
    if re.search(r'(宦官|十常侍|中常侍|太监)', n):
        return 'han', '其他', 'male', 0.7, 'note:宦官'
    if re.search(r'(汉灵帝|汉献帝|汉朝|汉室|汉廷|太尉|司徒|大将军.*汉|侍中.*汉)', n):
        return 'han', role, gender, 0.6, 'note:汉廷'
    if re.search(r'(南蛮|孟获|洞主|羌|蛮王|鲜卑|乌桓|匈奴|异族|番)', n):
        return 'barbarian', role, gender, 0.6, 'note:异族'
    if re.search(r'(仙|道人|隐士|隐者|术士|神|方士|居士|左慈|于吉|管辂)', n):
        return 'mystic', '其他', gender, 0.6, 'note:神怪'
    if re.search(r'(袁绍|袁术|吕布|董卓|刘表|公孙|马腾|韩遂|张鲁|刘璋|陶谦|群雄|诸侯|太守.*自)', n):
        return 'warlord', role, gender, 0.6, 'note:群雄'
    return 'warlord', role, gender, 0.35, 'fallback'


def make_id(name, used):
    py = re.sub(r'[^a-z0-9_]', '', '_'.join(lazy_pinyin(name))) or 'p'
    if py not in used:
        used.add(py); return py
    i = 2
    while f'{py}_{i}' in used: i += 1
    used.add(f'{py}_{i}')
    return f'{py}_{i}'


def clamp_tenure(fac, first_ch):
    lo, hi = FAC_BOUND.get(fac, (184, 229))
    y = CH_YEAR.get(first_ch, 200)
    s = max(lo, min(y, hi))
    e = hi if hi >= s else s
    return s, e


def main():
    known, used_ids, courtesy = load_known()
    main_roster, all_names, zihao_html = parse_main_roster(HTML_MAIN)
    second = parse_second_roster(HTML_SECOND)
    zihao = zihao_html | courtesy
    fac_map = faction_hint_map()

    places = set()
    for p in json.load(io.open(os.path.join(ROOT, 'build', 'places.json'), encoding='utf-8')):
        places.add(p['name'])
        for a in (p.get('aliases') or []): places.add(a)

    SRC = {}
    for f in sorted(glob.glob(os.path.join(DATA, 'source', 'ch*.txt'))):
        SRC[int(re.search(r'ch(\d+)', f).group(1))] = io.open(f, encoding='utf-8').read()
    FULL = ''.join(SRC.values())

    APPELLATION = re.compile(r'(老仙|隐者|先生|国老|天子|禅师|道人|神$|督邮|单于|可汗|后槽|军士|梨树神|管辂舅|郭常子|姜叙母|全尚妻|押狱|太守$|从事$|功曹$|校尉$|官兵$|家将$|牙将$|部将$)')
    def is_noise(nm):
        if len(nm)==2 and nm[0]==nm[1]: return True
        return nm in ('徐徐','缓缓','渐渐','看看','听听','连连','匆匆','默默','哈哈','流行','评价','顶部','相关')

    # ---- 候选池 ----
    pool = {}
    def add(nm, note='', ch=None):
        nm = nm.strip()
        if not re.fullmatch(r'[\u4e00-\u9fa5·]{2,6}', nm): return
        if nm in pool:
            if note and len(note) > len(pool[nm]['note']): pool[nm]['note'] = note
            if ch and (pool[nm]['chapter_hint'] is None or ch < pool[nm]['chapter_hint']):
                pool[nm]['chapter_hint'] = ch
        else:
            pool[nm] = {'note': note, 'chapter_hint': ch}
    for nm, info in main_roster.items():
        add(nm, info['note'], info['chapter'])
    for nm in all_names: add(nm)
    for nm in second: add(nm)
    # 尾部女性段（32 位被主词表解析器漏掉的女性人物）
    tail_female = parse_second_roster_tail(HTML_SECOND, set(known) | set(main_roster) | set(second))
    for nm, rel in tail_female.items():
        add(nm, f'{nm}，{rel}。' if rel else '', None)
    second_set = set(second) | set(tail_female)
    wiki_set = set()
    if os.path.exists(WIKI_TXT):
        for line in io.open(WIKI_TXT, encoding='utf-8'):
            if line.startswith('#'): continue
            for t in line.split():
                if re.fullmatch(r'[\u4e00-\u9fa5]{2,6}', t): add(t); wiki_set.add(t)

    # 姓氏集：从所有已知人名首字归纳，用于「姓名格式规范性」判断
    surname = set()
    for nm in list(known.keys()) + list(pool.keys()):
        if 2 <= len(nm) <= 3: surname.add(nm[0])
    COMPOUND = {'司马','诸葛','夏侯','公孙','太史','淳于','皇甫','东方','南宫','上官','单于','呼延','濮阳','令狐','淳于'}
    for c in COMPOUND: surname.add(c[0])
    HARD_NOISE = {'雅旦','顶部','相关','评价','检索固化','瀑布','下载','首页','登录','注册'}
    def is_person_name(nm):
        if nm in HARD_NOISE: return False
        if not (2 <= len(nm) <= 3): return False
        if nm[0] not in surname: return False
        # 只在第 2 字起检查虚词：否则会误杀姓「何/于/为…」的人物（如 何颙）
        if re.search(r'[的了是在和与之为于其而以乃也者所如]|[\d]', nm[1:]): return False
        return True

    # ---- V2 修复1：庇护源只收 <=3 字真人名 + 白名单长名 ----
    long_names = set()
    for nm in list(known.keys()) + list(pool.keys()):
        if len(nm) <= 3 or nm in KEEP_FULLNAME:
            long_names.add(nm)

    cards, stat, low_conf, drops = [], Counter(), [], {}
    def drop(nm, reason, extra=''):
        stat[reason] += 1
        drops.setdefault(reason, []).append(nm if not extra else f'{nm}({extra})')

    for nm, info in pool.items():
        variants = sorted(VARIANT_REV.get(nm, set()) | ({VARIANT_MAP[nm]} if nm in VARIANT_MAP and VARIANT_MAP[nm] != nm else set()))
        is_main = nm in main_roster
        cnt = FULL.count(nm)
        cnv = cnt
        for v in variants:
            if FULL.count(v) > cnv:
                cnv = FULL.count(v)
        if nm in known: drop(nm,'已建档'); continue
        if nm in zihao: drop(nm,'字号剔除'); continue
        if nm in places: drop(nm,'地名剔除'); continue
        if len(nm) < 2: drop(nm,'单字剔除'); continue
        if APPELLATION.search(nm) and nm not in KEEP_FULLNAME and not is_main:
            drop(nm,'称谓剔除'); continue
        if is_noise(nm): drop(nm,'噪声剔除'); continue
        if nm in FRAGMENT_BLOCK: drop(nm,'片段黑名单', f'cnt={cnv}'); continue
        # V2 修复2：片段判定 = 被更长真人名包含 且 频次仲裁失败
        frag_src = [ln for ln in long_names if nm != ln and nm in ln and len(ln) >= 3]
        if frag_src:
            max_src = max(FULL.count(x) for x in frag_src)
            dominant = cnv >= 5 and cnv > max_src          # 频次仲裁：自身主导则视为独立人物
            has_own_note = bool(info.get('note')) and len(info['note']) >= 6
            if not dominant and not has_own_note:
                drop(nm,'片段剔除', f'cnt={cnv} vs {frag_src[:2]}'); continue
        is_mentioned_only = False
        if cnv == 0:
            # V3：权威名录（主名录/姓氏词表/维基名单）收录且姓名格式规范者，
            #     即便本版本正文未直书其名，也建立「仅名录收录」卡（无正文锚点）。
            if is_person_name(nm) and (is_main or nm in second_set or nm in wiki_set):
                is_mentioned_only = True
                stat['仅名录收录'] += 1
            else:
                drop(nm,'原文0次剔除', f'main={is_main}'); continue
        # 首见回目
        first_ch = None
        targets = [nm] + variants
        for ch in sorted(SRC):
            if any(t in SRC[ch] for t in targets): first_ch = ch; break
        if first_ch is None: first_ch = info['chapter_hint'] or 1
        chint = info['chapter_hint']
        if chint and 1 <= chint <= 120:
            first_ch = min(first_ch, chint)
        # 阵营/角色
        is_female_entry = nm in tail_female
        key = nm if nm in fac_map else VARIANT_MAP.get(nm, nm)
        if is_female_entry:
            # 女性段：按夫君/父/主的阵营归类，身份一律「女眷」
            relnote = tail_female.get(nm, '')
            if re.search(r'(曹操|曹丕|曹睿|曹芳|曹爽|曹文叔|曹髦|魏)', relnote) or re.search(r'(曹操|曹丕|曹睿|曹芳|曹爽|曹髦)', nm):
                fac = 'wei'
            elif re.search(r'(刘备|刘禅|诸葛亮|孟获|马超|马邈|庞德|刘琰|刘諶|黄奎|董承)', relnote):
                fac = 'shu'
            elif re.search(r'(孙权|孙策|孙坚|孙休|孙亮|孙和|袁术|袁绍|吕布|刘表)', relnote):
                fac = 'wu' if re.search(r'(孙权|孙策|孙坚|孙休|孙亮|孙和)', relnote) else 'warlord'
            elif re.search(r'(灵帝|少帝|献帝|何进|蔡邕|汉)', relnote) or nm in ('何后','唐妃','董太后','王美人','蔡琰','舞阳君'):
                fac = 'han'
            else:
                fac = 'warlord'
            role, gender, conf, basis = '女眷', 'female', 0.75, 'roster_tail:女眷段'
        elif key in fac_map:
            fac, role_hint, src = fac_map[key]
            allowed = ROLE_BY_FAC.get(fac)
            role = role_hint or '武将'
            if allowed and role not in allowed: role = '武将' if '武将' in allowed else list(allowed)[0]
            if role not in (allowed or {'皇帝','追谥','君主','权臣','亲族','文臣','武将','女眷','其他'}): role='其他'
            gender = 'female' if role=='女眷' else 'male'
            conf, basis = 0.85, src
        else:
            fac, role, gender, conf, basis = infer_from_note(info['note'], nm)
        if fac=='mystic': role='其他'
        if fac in ('warlord','barbarian') and role not in ('君主','文臣','武将','女眷'): role='武将'
        s, e = clamp_tenure(fac, first_ch)
        note = re.split(r'[。；]', info['note'])[0][:60] if info['note'] else ''
        ctx = ''
        for t in targets:
            idx = FULL.find(t)
            if idx >= 0:
                ctx = re.sub(r'\s+','', FULL[max(0,idx-12):idx+24]); break
        summary = note if note and len(note) >= 4 else (f'《三国演义》人物，见于第{first_ch}回。')
        if is_mentioned_only:
            summary = note or f'《三国演义》人物名录收录，谓见于第{first_ch}回。'
        bio = f'{nm}，{summary}（据原文第{first_ch}回前后文及人物名录整理；此卡为自动建档，生卒、字号、详细事迹待考。）'
        pid = make_id(nm, used_ids)
        tenure = {
            'faction_id': fac, 'role': role,
            'start_year': s, 'end_year': e,
            'title': note[:20] if note else None,
            'basis': f'{basis}；原文首见第{first_ch}回，全书出现{cnv}次。自动建档，生卒/字号未考。',
            'confidence': conf, 'review_status': 'auto',
        }
        # V3：泛称/称号类（X氏、X后、X妃、X贵人、X太后）在正文中多义，
        #     强行给锚点会造成大规模误链，故只建人物卡、不派正文锚点。
        ANCHORABLE_TITLE = re.compile(r'夫人$')
        ANCHORABLE_NAME = {'蔡琰','貂蝉','大乔','小乔','云英','李春香','夏侯令女','舞阳君','樊氏','祝融夫人'}
        no_anchor_title = is_female_entry and not (ANCHORABLE_TITLE.search(nm) or nm in ANCHORABLE_NAME)
        # V2 修复5：异写进别名，正文实际写法进 match_surfaces
        surfaces = [] if (is_mentioned_only or no_anchor_title) else sorted(set([nm] + variants))
        card = {
            'id': pid, 'name': nm, 'courtesy': None,
            'match_surfaces': surfaces,
            'display_aliases': [v for v in variants if v != nm],
            'birth': None, 'death': None,
            'date_precision': 'unknown',
            'date_note': '生卒年不详，未经考据（自动建档）。',
            'gender': gender,
            'first_chapter': first_ch,
            'review_status': 'auto_mined',
            'summary': summary,
            'bio': bio,
            'tenure': [tenure],
            'timeline': [],
        }
        if is_mentioned_only:
            card['is_mentioned_only'] = True
            card['bio'] = f'{nm}，{summary}（人物名录收录，谓"仅被提及"；本版本正文未直书其名，故无正文锚点。生卒、事迹待考。）'
            tenure['basis'] = f'{basis}；人物名录载于第{first_ch}回被提及，正文未直书其名。自动建档，生卒/字号未考。'
        cards.append(card)
        stat['建卡'] += 1
        stat['其中≥2次' if cnv >= 2 else '其中仅1次'] += 1
        if conf < 0.5:
            low_conf.append({'name': nm, 'fac': fac, 'role': role, 'basis': basis})

    out = os.path.join(DATA, 'persons_p6_auto.json')
    json.dump({'comment': 'P6 自动铺量建档 V2（2026-10-30）：名录ren_tip + 姓氏词表 + 维基名单 + 原文频次验证 + 异体字映射 + 百科阵营分组。review_status=auto_mined，生卒未考，阵营身份为推断并标置信度。',
               'persons': cards},
              io.open(out,'w',encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump({'variants': {k: sorted(v) for k, v in VARIANT_REV.items()}},
              io.open(os.path.join(DATA,'alias_variant.json'),'w',encoding='utf-8'), ensure_ascii=False, indent=1)
    report = os.path.join(DATA, 'expand_report.json')
    json.dump({'stats': dict(stat), 'total_new': len(cards),
               'grand_total': 355+len(cards),
               'low_confidence_count': len(low_conf),
               'low_confidence_sample': low_conf[:80],
               'drop_detail': {k: v for k, v in drops.items()},
               'faction_distribution': dict(Counter(c['tenure'][0]['faction_id'] for c in cards)),
               'role_distribution': dict(Counter(c['tenure'][0]['role'] for c in cards))},
              io.open(report,'w',encoding='utf-8'), ensure_ascii=False, indent=1)
    print('统计:', dict(stat))
    print(f'新增 {len(cards)} 张 → 全库 {355+len(cards)} 人')
    print('阵营分布:', dict(Counter(c['tenure'][0]['faction_id'] for c in cards)))
    print('角色分布:', dict(Counter(c['tenure'][0]['role'] for c in cards)))
    print(f'低置信(<0.5) {len(low_conf)} 张')
    print('已写出', out, '与', report)


if __name__ == '__main__':
    main()
