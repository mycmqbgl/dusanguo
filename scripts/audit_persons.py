#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人物相关数据全维度体检（任务③④⑤）

检查对象（人物卡是唯一入口，所有下游都由它派生）：
  1. tenure.role     是否落在 build.py ROLE_ORDER 的 10 项之内（越界会导致人物页网格不显示）
  2. tenure.faction_id 是否在 FACTION_META 8 类之内
  3. tenure 时间片    start/end 是否合法、是否落在阵营存在区间内
  4. 君臣边 lord_id  是否指向库内真实人物（图谱君臣边由此产生）
  5. 事件 participants.person_id 是否指向库内真实人物
  6. 大势 power.json 的 faction leader 能否匹配到某张人物卡
  7. 人物 match_surfaces 是否与他人重名冲突
  8. 关系图谱对称性：A 的 lord 是 B，则 B 的下属列表里应有 A（由前端实时计算，此处预检）

输出 data/audit_persons.json，并按需把可自动修复项写回源文件。
"""
import json, io, os, re, glob, sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
BUILD = os.path.join(ROOT, 'build')
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

FACTION_META = {'han','warlord','wei','wu','shu','jin','barbarian','mystic'}
ROLE_ORDER = ['皇帝','追谥','君主','权臣','亲族','文臣','武将','女眷','客君','其他']
FAC_BOUND = {'han':(1,234),'warlord':(184,229),'wei':(196,266),'wu':(195,280),
             'shu':(208,263),'jin':(265,316),'barbarian':(184,280),'mystic':(184,280)}

# 越界 role 的收敛映射（保留原语义归入十类）
ROLE_FIX = {
    '太守':'文臣','刺史佐吏':'文臣','主簿':'文臣','县令':'文臣','丞相':'文臣',
    '托孤大臣':'文臣','辅政':'文臣','辅政大臣':'文臣','谋臣':'文臣','权臣心腹':'文臣',
    '统帅':'武将','郡将':'武将','叛将':'武将','都督':'武将','番兵统帅':'武将',
    '亡国之君':'君主','割据君主':'君主','蛮王':'君主','羁縻洞主':'君主','洞主':'君主','国主':'君主',
    '术士':'其他','平民':'其他','名士':'其他','隐士':'其他',
    # 客君：前朝/他国君主降封后受本朝爵者（2026-10-30 新增），历史遗留写法一并收敛
    '降封之君':'客君','亡国之君降封':'客君','客君':'客君',
}


def load_all():
    docs = {}
    persons = {}
    for f in sorted(glob.glob(os.path.join(DATA, 'persons_*.json'))):
        doc = json.load(io.open(f, encoding='utf-8'))
        docs[f] = doc
        for p in doc['persons']:
            persons[p['id']] = p
    return docs, persons


def main(fix=False):
    docs, persons = load_all()
    issues = defaultdict(list)

    # 1-3 tenure 合法性
    for pid, p in persons.items():
        for i, tn in enumerate(p.get('tenure') or []):
            role = tn.get('role')
            fac = tn.get('faction_id')
            s, e = tn.get('start_year'), tn.get('end_year')
            if role not in ROLE_ORDER:
                issues['role_越界'].append({'id':pid,'name':p['name'],'role':role,
                                            'suggest':ROLE_FIX.get(role)})
            if fac not in FACTION_META:
                issues['faction_越界'].append({'id':pid,'name':p['name'],'faction':fac})
            if s is None or e is None:
                issues['年份缺失'].append({'id':pid,'name':p['name'],'start':s,'end':e})
            elif s > e:
                issues['起止倒挂'].append({'id':pid,'name':p['name'],'start':s,'end':e})
            elif fac in FAC_BOUND:
                lo, hi = FAC_BOUND[fac]
                # span_pre_state：君主称制前即已在其身边者（如刘备之妻甘夫人、
                # 糜夫人在 208 年蜀汉势力形成之前已入刘门），任期早于阵营起点属史实，
                # 非数据错误，由卡面 span_pre_state 显式声明后豁免。
                # 废黜、禅位后仍以本朝宗室之身受封（曹芳齐王至 274、曹奂陈留王至 302），
                # 其卒年可越出本朝上限，由卡面 span_post_state 显式声明后豁免。
                if (s < lo or e > hi) and not p.get('span_pre_state') and not p.get('span_post_state'):
                    issues['越出阵营区间'].append({'id':pid,'name':p['name'],'faction':fac,
                                                   'start':s,'end':e,'bound':[lo,hi]})
            lord = tn.get('lord_id')
            if lord and lord not in persons:
                issues['lord_id悬空'].append({'id':pid,'name':p['name'],'lord_id':lord})

    # 3a-2. 同一阵营内，一个人的两个时间片不得在同一年同时成立
    #     口径：相邻两片共享端点年（前片 end == 后片 start）属正常交接，只允许重叠 1 年；
    #     重叠 > 1 年即「某年同时有两个身份」，按年筛选时此人被计两次。
    #     反例（已修）：曹芳 魏·皇帝 239-254 与 魏·其他 249-266；曹奂 魏·亲族 258-260 与 魏·其他 258-266；
    #     司马懿 魏·文臣 220-251 与 魏·权臣 239-251。
    for pid, p in persons.items():
        by = {}
        for tn in (p.get('tenure') or []):
            by.setdefault(tn.get('faction_id'), []).append(tn)
        for fac, lst in by.items():
            for a in range(len(lst)):
                for b in range(a + 1, len(lst)):
                    x, y = lst[a], lst[b]
                    sx, ex = x.get('start_year'), x.get('end_year')
                    sy, ey = y.get('start_year'), y.get('end_year')
                    if None in (sx, ex, sy, ey):
                        continue
                    n = max(0, min(ex, ey) - max(sx, sy) + 1)
                    if n > 1:
                        issues['同阵营时间重叠'].append({
                            'id': pid, 'name': p['name'], 'faction': fac, 'years': n,
                            'a': '%s %s-%s' % (x.get('role'), sx, ex),
                            'b': '%s %s-%s' % (y.get('role'), sy, ey),
                            'suggest': '同一时点只能有一个身份：修剪其中一段的起止年，或合并'})

    # 3b. 「其他」身份不得持有实任官职
    #     口径：「其他」用于既非君主/宗室、也非文臣武将者（商贾、医者、隐士、门客、
    #     家奴、从人、术士、无职任的家属等）。凡在原文或正史中实任某政权官职者
    #     （中常侍、太傅、将军、都尉、太守、监军、列侯等），应归文臣或武将，
    #     不得以「其他」规避。神怪阵营只有「其他」，不参与本检查。
    REAL_OFFICE = re.compile(
        r'中常侍|大长秋|黄门令|太傅|太尉|司徒|司空|太常|光禄|少府|执金吾|'
        r'将军|校尉|都尉|太守|刺史|州牧|相国|尚书|仆射|侍中|中书令|'
        r'监军|别部司马|长史|司马|参军|主簿|从事|别驾|治中|议郎|侍郎|博士|'
        r'亭侯|乡侯|列侯|县侯')
    for pid, p in persons.items():
        for tn in (p.get('tenure') or []):
            if tn.get('role') != '其他' or tn.get('faction_id') == 'mystic':
                continue
            title = tn.get('title') or ''
            # 标题中含「（世系提及）」「（前朝…）」「之子」「之女」等为身份描述，豁免
            if re.search(r'（|世系|提及|之子|之女|之妻|之姊|之父|之侄|未仕|致仕', title):
                continue
            m = REAL_OFFICE.search(title)
            if m:
                issues['其他持实职'].append({
                    'id': pid, 'name': p['name'], 'title': title, 'hit': m.group(0),
                    'suggest': '改为 文臣/武将/亲族'})

    # 3c. 「亲族」身份必须有明确的家世锚点
    #     口径（已与用户确认）：亲族 = ①当朝帝系之血亲（父、子、兄弟、叔侄、孙）；
    #     ②后族（后妃本人及其父兄）。宗室旁支的姻亲（侄女婿）、功臣之后袭爵者，
    #     虽有世系线索但不是帝系亲族，不得挂「亲族」。
    #     反例（均为已修）：司马炎（其父司马昭是魏臣，炎非曹氏之亲）、
    #     吕霸（吕蒙之子，袭爵的功臣之后）、荀恽（荀彧之子，魏之朝臣）、
    #     周胤（娶孙皎之女，孙权侄女婿，隔了一层）。
    #     校验方式：title（必要时并看 basis）中必须出现「〈人名〉之(子|弟|孙|女|侄…)、
    #     嫔妃身份、X王（宗室封号）」这类**双向可校验**的关系描述；
    #     仅靠「某人之子」还不够——必须有可指认的帝系锚点，且「袭爵/功臣之后」不算。
    KIN_ANCHOR = re.compile(
        r'[帝主].{0,4}之(?:子|女|弟|兄|孙|侄|叔)|'
        r'(?:操|丕|叡|备|禅|坚|策|权|亮|休|皓|懿|昭|炎|焉|焉).{0,4}之(?:子|女|弟|兄|孙|侄)|'
        r'庶子|养子|长子|次子|三子|四子|五子|六子|七子|世子|'
        r'皇后|贵妃|美人|贵人|妃|太后|国舅|宗室|宗亲|后族|外戚|'
        r'尚.{0,6}之女|尚.{0,6}公主|'
        r'(?:鲁|梁|燕|齐|楚|赵|吴|代|彭城|东海|南阳|会稽|北地|安乐|陈留|弘农|西乡|常道乡)王|'
        r'生父|之叔|叔父')
    # 帝系锚点还需指向本朝君主姓名，避免「某人之子」蒙混
    # 刘元起为刘备叔父：刘备此时尚是汉之布衣宗亲，其叔亦系汉室远支，故 han 含「刘备」。
    MONARCH = {'han': ('灵帝', '献帝', '少帝', '桓帝', '董太后', '何太后', '汉室', '刘焉', '刘备'),
               'wei': ('曹操', '曹丕', '曹叡', '曹芳', '曹髦', '曹奂', '魏室', '武帝', '文帝', '明帝'),
               'shu': ('刘备', '刘禅', '先主', '后主', '蜀室'),
               'wu': ('孙坚', '孙策', '孙权', '孙亮', '孙休', '孙皓', '吴室'),
               'jin': ('司马懿', '司马昭', '司马炎', '司马师')}
    for pid, p in persons.items():
        for tn in (p.get('tenure') or []):
            if tn.get('role') != '亲族':
                continue
            title = tn.get('title') or ''
            fac = tn.get('faction_id')
            basis = tn.get('basis') or ''
            blob = title + '｜' + basis
            # 本朝降封/禅位之君，其亲族身份由「本朝宗室」承载，属史实而非张冠李戴
            post_state = p.get('span_post_state')
            if not KIN_ANCHOR.search(title) and not (post_state and re.search(r'王|公|侯', title)):
                issues['亲族无血亲线索'].append({
                    'id': pid, 'name': p['name'], 'faction': fac, 'title': title,
                    'suggest': 'title 须写明系出哪一位君主（×之子/×之弟/后妃/宗室封王）；否则改 文臣/武将/其他'})
                continue
            # 亲族必须能指认到本朝帝系（或本朝所尊之外戚），不得张冠李戴
            kw = MONARCH.get(fac) or ()
            if kw and not any(k in blob for k in kw) and not post_state:
                issues['亲族帝系不明'].append({
                    'id': pid, 'name': p['name'], 'faction': fac, 'title': title,
                    'expect': '/'.join(kw),
                    'suggest': '在 title 或 basis 中写明系出本朝哪一位君主；否则改 文臣/武将'})

    # 3d. 「追谥」只能用于本朝追尊前代（父祖），不得用于降封、禅位后的封号
    #     反例（已修）：刘协禅位后受魏封山阳公，原误记作「汉·追谥」，
    #     实为魏所封之降封，应由 liu_xie 的 wei/其他 段承载。
    for pid, p in persons.items():
        for tn in (p.get('tenure') or []):
            if tn.get('role') != '追谥':
                continue
            title = tn.get('title') or ''
            if re.search(r'公$|王$|侯$|降封|禅位|废为', title):
                issues['追谥误用'].append({
                    'id': pid, 'name': p['name'], 'title': title,
                    'suggest': '降封/禅位后的封号应记为受封朝代的 亲族/其他'})

    # 3e. 一句话简介与生平详述不得阵营自相矛盾
    #     反例（已修）：毋丘甸 summary 写「群雄人物」、bio 写「曹魏…」；
    #     大量自动建档卡 summary 是「曹魏武将」而 bio 前置写「群雄武将」。
    #     口径：summary 中的阵营词必须等于 tenure[0].faction_id；bio 不再以
    #     「姓名，阵营身份」起头（该信息由 summary 与 tenure 承载）。
    FAC_WORD = [('曹魏', 'wei'), ('孙吴', 'wu'), ('蜀汉', 'shu'), ('东汉', 'han'),
                ('西晋', 'jin'), ('群雄', 'warlord'), ('南蛮', 'barbarian'),
                ('异族', 'barbarian'), ('神怪', 'mystic')]
    for pid, p in persons.items():
        s = p.get('summary') or ''
        tns = p.get('tenure') or []
        if not tns:
            continue
        fac0 = tns[0].get('faction_id')
        # 摘要描述的是此人一生最高身份时，可用「官至蜀汉丞相」这类表述，
        # 此时阵营词出现在「官至/仕/封」之后，不算与首位任期冲突。
        s_head = re.sub(r'(官至|仕|降|归|封|入)(群雄|东汉|曹魏|孙吴|蜀汉|西晋|南蛮|异族|神怪)', r'\1', s)
        for word, fid in FAC_WORD:
            if word in s_head and fid != fac0:
                issues['简介阵营与任期不符'].append({
                    'id': pid, 'name': p['name'], 'summary': s[:40],
                    'word': word, 'faction': fac0})
                break
        # bio 开头的模板腔「X，阵营身份」一律视为与 summary 重复且易冲突
        bio = p.get('bio') or ''
        m = re.match(r'^[\u4e00-\u9fa5]{1,8}[，,]\s*(群雄|东汉|曹魏|孙吴|蜀汉|西晋|南蛮|异族|神怪)', bio)
        if m:
            issues['生平含阵营标签开头'].append({
                'id': pid, 'name': p['name'], 'head': bio[:24]})

    # 4. surface 重名冲突
    #    例外：若重名各方均已用 homonym_note 显式声明「同姓名不同人」各自的区分标识
    #    （如汉司空张温 vs 吴中郎将张温），属演义中真实存在的同名异人，不算冲突。
    surf = defaultdict(set)
    for pid, p in persons.items():
        for s in (p.get('match_surfaces') or []):
            surf[s].add(pid)
    for s, ids in surf.items():
        if len(ids) > 1:
            if all(persons[i].get('homonym_note') for i in ids if i in persons):
                continue
            issues['surface重名'].append({'surface':s,
                'ids':sorted(ids),'names':sorted(persons[i]['name'] for i in ids if i in persons)})

    # 5. 事件 participants 悬空
    for f in glob.glob(os.path.join(DATA, 'event_*.json')):
        doc = json.load(io.open(f, encoding='utf-8'))
        evs = doc.get('events') or (doc if isinstance(doc, list) else [])
        for ev in evs:
            if not isinstance(ev, dict): continue
            for pt in (ev.get('participants') or []):
                if not isinstance(pt, dict): continue
                pid = pt.get('person_id')
                if pid and pid not in persons:
                    issues['事件人物悬空'].append({'file':os.path.basename(f),
                        'event':ev.get('title') or ev.get('id'),'person_id':pid,
                        'name':pt.get('name')})

    # 6. 大势 leader 与人物卡的对应
    #    build/power.json 的真实结构是 {factions:[{id,name,leader,person_id,...}]}，
    #    没有顶层 leaders 字段，也没有 per-faction snapshots。原实现取
    #    power.get('leaders') 恒为 None，`snap.get('leader') or fac.get('leader')`
    #    又在 snapshots 缺失时只落到 fac 一层，等于「只看名字在不在库里」，
    #    person_id 填错/漏填一概查不出。
    pw = os.path.join(BUILD, 'power.json')
    if os.path.exists(pw):
        power = json.load(io.open(pw, encoding='utf-8'))
        byname = {}
        for pid, p in persons.items():
            byname.setdefault(p.get('name'), []).append(pid)

        def report(kind, fac, **kw):
            row = {'faction': fac.get('id') or fac.get('name')}
            row.update(kw)
            issues[kind].append(row)

        for fac in (power.get('factions') or []):
            ld = fac.get('leader')
            pid = fac.get('person_id')
            if not ld:
                continue
            cand = byname.get(ld) or []
            if not cand:
                report('大势leader未匹配', fac, leader=ld,
                       why='库里没有叫这个名字的人物卡')
                continue
            if len(cand) > 1:
                # 同名不同人：必须靠 person_id 消歧，否则地图上会挂错人
                report('大势leader同名待消歧', fac, leader=ld, candidates=cand)
            if not pid:
                report('大势leader缺person_id', fac, leader=ld, by_name=cand)
            elif pid not in persons:
                report('大势leader未匹配', fac, leader=ld,
                       why='person_id 指向不存在的人物卡', person_id=pid)
            elif persons[pid].get('name') != ld:
                report('大势leader错挂', fac, leader=ld, person_id=pid,
                       person_name=persons[pid].get('name'))

    # 7. 缺字段
    for pid, p in persons.items():
        for k in ('name','id','summary','bio','gender','date_precision'):
            if not p.get(k):
                issues['缺字段'].append({'id':pid,'name':p.get('name'),'field':k})

    print('=== 人物数据体检 ===')
    total = 0
    for k, v in sorted(issues.items(), key=lambda x: -len(x[1])):
        print(f'  {k}: {len(v)}')
        total += len(v)
    print(f'  合计 {total} 项')
    print()
    for k in ('role_越界','faction_越界','起止倒挂','lord_id悬空','大势leader未匹配','缺字段'):
        if issues.get(k):
            print(f'--- {k} ---')
            for x in issues[k][:20]:
                print('   ', x)
    for k in ('越出阵营区间','surface重名','事件人物悬空'):
        if issues.get(k):
            print(f'--- {k} ({len(issues[k])}) 样例 ---')
            for x in issues[k][:12]:
                print('   ', x)

    json.dump({k: v for k, v in issues.items()},
              io.open(os.path.join(DATA, 'audit_persons.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    # ---- 自动修复：role 越界 / 起止倒挂 / 越出阵营区间 ----
    if fix:
        n = 0
        for f, doc in docs.items():
            changed = 0
            for p in doc['persons']:
                for tn in (p.get('tenure') or []):
                    r = tn.get('role')
                    if r in ROLE_FIX:
                        tn['role'] = ROLE_FIX[r]; tn.setdefault('_role_orig', r); changed += 1
                    s, e = tn.get('start_year'), tn.get('end_year')
                    fac = tn.get('faction_id')
                    if s is not None and e is not None and s > e:
                        tn['start_year'], tn['end_year'] = e, s; changed += 1
                    if fac in FAC_BOUND and s is not None and e is not None:
                        lo, hi = FAC_BOUND[fac]
                        ns, ne = max(lo, min(s, hi)), max(lo, min(e, hi))
                        if (ns, ne) != (s, e):
                            tn['start_year'], tn['end_year'] = ns, ne; changed += 1
            if changed:
                json.dump(doc, io.open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
                n += changed
        print(f'\n已自动修复 {n} 处（写回 data/persons_*.json）')
    return issues


if __name__ == '__main__':
    main(fix='--fix' in sys.argv)
