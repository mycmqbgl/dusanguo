#!/usr/bin/env python3
"""重建 summary / bio（第三类灌水式缺陷根治）。

病根：同一段 20 字原文窗口被正则切碎后同时灌进 summary、bio、tenure.title，
产生「蜀将，帐下」「门客，字」「为杀」这类没有主语的残句。

本脚本只处理「确实损坏」的卡，用结构化数据重写：
  summary = 姓名 + 阵营身份 + 官职 + 该人为主语的原文事迹 + 首见回目
  bio     = 姓名 + 身世/身份 + 逐条事迹（带回目）+ 结局
事迹句必须满足「该人为句子主语」——避免把「植谓玄德曰…张梁、张宝在颍川」
这类旁人叙述当成其人功业。
"""
import json, glob, os, re, sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = '--fix' in sys.argv

FACTION_CN = {'han': '东汉', 'wei': '曹魏', 'shu': '蜀汉', 'wu': '孙吴',
              'jin': '西晋', 'warlord': '群雄', 'barbarian': '异族', 'mystic': '方外'}
ROLE_CN = {'皇帝': '皇帝', '追谥': '追尊者', '君主': '君主', '权臣': '权臣',
           '亲族': '宗室', '文臣': '文臣', '武将': '武将', '女眷': '女眷', '其他': '人物'}

BAD_TAIL = re.compile(r'[，,]\s*(字|将|为|与|父|兄|子|女|妻|母|生|降|死|杀|斩|擒|射|刺|反|走|亡|帐下|截杀|守)$')

# 非官职的身份词：用「身份」而非「任」引出
NON_OFFICE = re.compile(r'(之弟|之兄|之子|之女|之妻|之侄|之孙|之母|之父|从人|门客|心腹|亲随|家人|仆人|家奴|'
                        r'隐士|处士|名士|道人|方士|僧人|仙人|猎户|平民|马商|良工|宗族|叛首|黄巾|余党|渠帅|洞主|部长)')
PLACEHOLDER = re.compile(r'^《三国演义》人物[，,]?\s*见于第\s*\d+\s*回。?$')

# 该人为主语的动作句：句首附近出现人名，且后接动词
VERB = (r'(斩|杀|擒|刺|射|战|攻|守|降|奔|投|谏|劝|引兵|率|领|拒|伏诛|族灭|屯|'
        r'袭|破|败|走|追|围|救|护|死|亡|自刎|自杀|说|诈|献|立|废|迁|表|拜|封)')


def clean_title(t):
    if not t:
        return ''
    t = re.sub(r'（[^）]*）', '', t)
    t = re.split(r'[。；]', t)[0]
    t = BAD_TAIL.sub('', t)
    return t.strip('，,、 ')


def load_chapters():
    ch = {}
    for f in sorted(glob.glob(os.path.join(PROJ, 'data/source/ch*.txt'))):
        no = int(re.search(r'ch(\d+)', f).group(1))
        ch[no] = open(f).read()
    return ch


def load_persons():
    pids, out = set(), []
    for f in glob.glob(os.path.join(PROJ, 'data/persons_*.json')):
        d = json.load(open(f))
        if isinstance(d, dict):
            d = d.get('persons', [])
        for p in d:
            if p.get('id') not in pids:
                pids.add(p['id'])
                out.append(p)
    return out


def persona(p):
    ts = p.get('tenure') or []
    if not ts:
        return '（佚）', '人物', '', None
    t = ts[0]
    fac = FACTION_CN.get(t.get('faction_id'), '群雄')
    role = ROLE_CN.get(t.get('role'), t.get('role') or '人物')
    return fac, role, clean_title(t.get('title')), t


def subject_acts(chapters, name, first, limit=2):
    """取该人作主语的句子。人名须出现在句首 0-8 字内。"""
    out = []
    for no in range(max(1, first - 1), min(120, first + 3) + 1):
        txt = chapters.get(no)
        if not txt:
            continue
        for sent in re.split(r'[。！？；]', txt):
            s = sent.strip().replace('\n', '')
            i = s.find(name)
            if i < 0 or i > 8:
                continue
            if not (6 <= len(s) <= 58):
                continue
            tail = s[i + len(name):]
            if not re.search(VERB, tail):
                continue
            out.append((no, s))
            if len(out) >= limit:
                return out
    return out


LEADIN = re.compile(r'^(却说|且说|再说|忽报|正说|话分两头|原来|当日|次日|是夜|却说当日|此时)[，,]?')


def tidy(s):
    s = LEADIN.sub('', s.strip())
    s = re.sub(r'["“”]', '', s)
    # 若句中有逗号且前半段只是状语，取后半主句
    return s.strip('，, ')


def build(p, chapters):
    name = p['name']
    fac, role, title, t = persona(p)
    first = p.get('first_chapter') or 1
    ident = '%s%s' % (fac, role)
    if title:
        ident += ('，身份为%s' if NON_OFFICE.search(title) else '，任%s') % title

    acts = subject_acts(chapters, name, first)
    cs, ce = (t or {}).get('start_year'), (t or {}).get('end_year')

    # summary
    seg = ['%s%s' % (fac, role)]
    if title:
        seg.append(('身份为%s' if NON_OFFICE.search(title) else '任%s') % title)
    tail = ''
    if acts:
        a = tidy(acts[0][1])
        if len(a) > 34:
            a = a[:34] + '…'
        tail = a
    summ = '%s，%s。' % (name, '，'.join(seg))
    if tail:
        summ += '%s。' % tail
    summ += '首见于《三国演义》第 %d 回。' % first

    # bio
    parts = ['%s，%s' % (name, ident)]
    if cs and ce:
        parts[0] += '（%s—%s 年）' % (cs, ce) if cs != ce else '（%s 年）' % cs
    parts[0] += '。'
    if p.get('courtesy'):
        parts.append('字%s。' % p['courtesy'])
    if acts:
        for no, s in acts:
            s = tidy(s)
            if len(s) > 50:
                s = s[:50] + '…'
            parts.append('第 %d 回：%s。' % (no, s))
    else:
        parts.append('第 %d 回见其名，原文未载具体事迹。' % first)
    bio = ''.join(parts)
    return summ, bio, title


def is_bad(p):
    s = (p.get('summary') or '').strip()
    b = (p.get('bio') or '')
    if not s or len(s) < 12:
        return True
    if PLACEHOLDER.match(s):
        return True
    if BAD_TAIL.search(s):
        return True
    if re.search(r'瞎搞|乌桓触', s):
        return True
    if '（据原文及人物名录整理' in b:
        return True
    return False


def main():
    chapters = load_chapters()
    persons = load_persons()
    todo = [p for p in persons if is_bad(p)]
    print('待重建 %d / %d' % (len(todo), len(persons)))
    out = {p['id']: build(p, chapters) for p in todo}
    show = list(out)[:10]
    for pid in show:
        s, b, t = out[pid]
        print('---', pid)
        print('  S:', s)
        print('  B:', b[:120])
    if not FIX:
        return
    for f in glob.glob(os.path.join(PROJ, 'data/persons_*.json')):
        raw = json.load(open(f))
        isd = isinstance(raw, dict)
        lst = raw.get('persons', []) if isd else raw
        dirty = False
        for p in lst:
            if p['id'] in out:
                s, b, t = out[p['id']]
                p['summary'] = s
                p['bio'] = b
                if t:
                    for tt in (p.get('tenure') or []):
                        tt['title'] = t
                dirty = True
        if dirty:
            json.dump(raw, open(f, 'w'), ensure_ascii=False, indent=1)
    print('已写回', len(out))


if __name__ == '__main__':
    main()
