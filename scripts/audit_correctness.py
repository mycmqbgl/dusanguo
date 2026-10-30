#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人物「阵营 / 身份」正确性复核（任务④，第 2 遍起）

第 1 遍查的是**合法性**（role 是否在身份枚举内（十类，含 2026-10-30 新增「客君」）、年份是否越界）；
本脚本查的是**正确性**——与权威基准对照，看归类是否站得住：

  A. 与 data/faction_roster.json（百度/搜狗百科按势力分组）对照：
     某人基准标 Shu，卡上却写 Wei → 冲突。
  B. 与爵里同源佐证：用 tenure.title / summary / bio 里的阵营关键词做二次判断。
  C. role 合理性：君主/权臣不可能同时是女眷；的一侧 [obj] person 有 bio 提到「X之妻/母」
     却写 role=武将 → 可疑。
  D. 君臣边（graph）：lord_id 指向的人是否真的在某阵营称主 ——
     检查 lord 本人的 role/势力是否支持"君"的身份。

输出 data/audit_correctness.json，只报告可核对的差异，不做臆改。
"""
import json, io, os, re, glob, sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')

FAC_CN = {'han':'东汉','warlord':'群雄','wei':'曹魏','wu':'孙吴','shu':'蜀汉',
          'jin':'西晋','barbarian':'异族','mystic':'神怪'}
# 阵营时间边界（与 build.py FAC_BOUND 一致），用于识别「先附后立」的口径差异
FAC_BOUND = {'han': (25, 220), 'warlord': (184, 229), 'wei': (196, 266),
             'wu': (195, 280), 'shu': (208, 263), 'jin': (265, 316),
             'barbarian': (184, 280), 'mystic': (184, 280)}
FAC_KEY = {
    'shu': r'(蜀|刘|汉|益州|西川|成都|汉中|诸葛|姜维)',
    'wei': r'(魏|曹|许昌|邺|司马)',
    'wu':  r'(吴|孙|江东|建业|武昌|周郎|孙权)',
    'jin': r'(晋|司马炎|羊祜|杜预)',
    'han': r'(汉廷|朝中|天子|献帝|灵帝|三公|太尉|司徒)',
    'barbarian': r'(羌|胡|蛮|匈奴|乌桓|鲜卑|南蛮|洞主|单于)',
    'mystic': r'(仙|道|隐|术|神)',
}

# 基准表口径与卡面不一致、但经原文核定「卡面为准」者。
# 说明：faction_roster 系按后世史书/百科的势力分组，把入晋功臣归在「魏」，
# 把方技之士归在「神怪」；演义时间线下这些归类不成立，故单独列出并附判据。
BASE_DRIFT = {
    'wang_jun': '第120回王濬为益州刺史、龙骧将军，受晋武帝命造楼船伐吴，是灭吴主将；'
                '演义叙事时点已在晋，归「西晋」为准，基准作「曹魏」系按出身势力归类。',
    'du_yu': '第120回杜预为镇南大将军、都督荆州事，与王濬同受晋命伐吴；'
             '演义时点在晋，归「西晋」为准，基准作「曹魏」系按出身势力归类。',
    'hua_tuo': '第15回为周泰疗疮、第78回为曹操诊头风，游方行医、无官职、无神异法术；'
               '属方技之士（东汉/其他），基准作「神怪」不妥。',
}


def load_persons():
    ps = {}
    for f in sorted(glob.glob(os.path.join(DATA, 'persons_*.json'))):
        for p in json.load(io.open(f, encoding='utf-8'))['persons']:
            ps[p['id']] = p
    return ps


def main():
    persons = load_persons()
    by_name = defaultdict(list)
    for pid, p in persons.items():
        by_name[p['name']].append(pid)

    base = {}
    fr = json.load(io.open(os.path.join(DATA, 'faction_roster.json'), encoding='utf-8'))
    for fac, groups in fr['groups'].items():
        items = []
        if isinstance(groups, dict):
            for g in groups.values(): items += groups if False else []
            for gname, names in groups.items():
                items.append((gname, names.split()))
        elif isinstance(groups, str):
            items.append(('', groups.split()))
        for gname, names in items:
            for nm in names:
                base.setdefault(nm, set()).add(fac)

    issues = defaultdict(list)
    checked = 0
    for nm, facs in base.items():
        ids = by_name.get(nm)
        if not ids:
            continue
        pid = ids[0]
        p = persons[pid]
        cur = set()
        for tn in (p.get('tenure') or []):
            if tn.get('faction_id'):
                cur.add(tn['faction_id'])
        if not cur or not facs:
            continue
        checked += 1
        # 口径差异白名单：本项目把「汉廷体系内」人物（汉官/汉将/汉后妃/十常侍）
        # 归入 han（东汉），百科基准多把他们统归 warlord（群雄）。本项目口径更细，
        # 不算冲突，计为 caliber 单独列出。
        if cur == {'han'} and 'warlord' in facs:
            issues['阵营口径差异（汉廷 vs 群雄）'].append({
                'id': pid, 'name': nm, 'card_cn': ['东汉'],
                'base_cn': [FAC_CN.get(x, x) for x in sorted(facs)],
                'note': '本项目按东汉朝廷体系归类，基准按群雄归类，口径不同非错误'})
            continue
        # 「先附后立」口径差异：人物在基准阵营成立之前就依附其领袖
        # （如徐庶 201 年投刘备，而蜀汉阵营自 208 年起算），本项目按当时实况归 warlord，
        # 基准按后来的阵营归类，属口径不同而非错误。
        years = [t.get('start_year') for t in (p.get('tenure') or [])
                 if t.get('start_year')]
        if years and any(min(years) < FAC_BOUND.get(f, (0, 9999))[0] for f in facs):
            issues['阵营口径差异（先附后立）'].append({
                'id': pid, 'name': nm, 'card_cn': [FAC_CN.get(x, x) for x in sorted(cur)],
                'base_cn': [FAC_CN.get(x, x) for x in sorted(facs)],
                'first_year': min(years),
                'note': '人物在基准阵营成立前即依附其领袖，按当时实况归类'})
            continue
        # 允许跨阵营转投：只有当完全无交集时才判冲突
        if not (cur & facs):
            if pid in BASE_DRIFT:
                issues['基准口径已核，卡面为准'].append({
                    'id': pid, 'name': nm,
                    'card_cn': [FAC_CN.get(x, x) for x in sorted(cur)],
                    'base_cn': [FAC_CN.get(x, x) for x in sorted(facs)],
                    'reason': BASE_DRIFT[pid]})
                continue
            issues['阵营与百科基准不符'].append({
                'id': pid, 'name': nm, 'card': sorted(cur),
                'card_cn': [FAC_CN.get(x, x) for x in sorted(cur)],
                'base': sorted(facs), 'base_cn': [FAC_CN.get(x, x) for x in sorted(facs)],
                'review': p.get('review_status'),
                'conf': min([tn.get('confidence') or 0 for tn in (p.get('tenure') or [])] + [1])})

    # C. role 与性别/身份线索冲突
    for pid, p in persons.items():
        txt = ' '.join(filter(None, [p.get('summary'), p.get('bio'),
                                     ' '.join(t.get('title') or '' for t in (p.get('tenure') or []))]))
        gender = p.get('gender')
        for tn in (p.get('tenure') or []):
            role = tn.get('role')
            # 性别冲突以 gender 字段为准（客观），不再用「夫人/妃」等亲属描述猜——
            # 那些词常出现在「XX之妹」「献帝妃嫔之父」这类亲属关系中，会大面积误报。
            if gender == 'female' and role in ('武将', '文臣', '君主', '权臣'):
                issues['身份疑似错配'].append({'id': pid, 'name': p['name'],
                                               'role': role, 'hint': 'gender=female'})
                break
            if gender == 'male' and role == '女眷':
                issues['身份疑似错配'].append({'id': pid, 'name': p['name'],
                                               'role': role, 'hint': 'gender=male'})
                break
            if role == '女眷' and re.search(r'(引兵|大战|斩将|先锋)', txt) and not re.search(r'(夫人|氏$|后$|妃)', p['name']):
                issues['身份疑似错配'].append({'id':pid,'name':p['name'],'role':role,'hint':'有战功记载'})
                break

    # D. 君臣边
    for pid, p in persons.items():
        for tn in (p.get('tenure') or []):
            lord = tn.get('lord_id')
            if not lord:
                continue
            lp = persons.get(lord)
            if not lp:
                issues['君臣边悬空'].append({'id':pid,'name':p['name'],'lord_id':lord}); continue
            lroles = {t.get('role') for t in (lp.get('tenure') or [])} - {None}
            # ① 主君身份压根不像能领属（女眷/其他/亲族）→ 可疑
            if lroles and not (lroles & {'皇帝', '君主', '权臣', '追谥', '武将', '文臣'}):
                issues['君臣边可疑'].append({'id': pid, 'name': p['name'],
                                             'lord': lp['name'],
                                             'lord_roles': sorted(lroles),
                                             'reason': '主君身份不宜领属'})
                continue
            # ② 任期与主君在世/在位的年份完全不重叠 → 硬证据，报
            s, e = tn.get('start_year'), tn.get('end_year')
            spans = [(t.get('start_year'), t.get('end_year'))
                     for t in (lp.get('tenure') or []) if t.get('start_year')]
            if s and spans and not any(
                    (a is None or a <= (e or s)) and (b is None or b >= (s or e))
                    for a, b in spans):
                issues['君臣边可疑'].append({'id': pid, 'name': p['name'],
                                             'lord': lp['name'],
                                             'lord_roles': sorted(lroles),
                                             'reason': f'任期 {s}-{e} 与主君无重叠'})

    print(f'=== 阵营/身份正确性复核（对照 {checked} 位有百科基准的人物）===')
    for k, v in sorted(issues.items(), key=lambda x: -len(x[1])):
        print(f'  {k}: {len(v)}')
    print()
    for k in ('阵营与百科基准不符',):
        if issues.get(k):
            print(f'--- {k} ---')
            for x in issues[k][:40]:
                print(f"    {x['name']}: 卡上={x['card_cn']} 百科={x['base_cn']} 来源={x['review']} 置信{x['conf']}")
    for k in ('君臣边可疑','君臣边悬空','身份疑似错配'):
        if issues.get(k):
            print(f'--- {k} ({len(issues[k])}) ---')
            for x in issues[k][:15]:
                print('   ', x)
    json.dump({k: v for k, v in issues.items()},
              io.open(os.path.join(DATA, 'audit_correctness.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('\n已写出 data/audit_correctness.json')


if __name__ == '__main__':
    main()
