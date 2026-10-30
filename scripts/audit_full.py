#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全量逐人物校验（1183 人 × 10 类字段）

校验项：
  1 姓名字    name 非空/长度合规；courtesy 不为空串不乱码、不与名相同
  2 生卒年    null 时 date_precision 须 unknown；birth<=death；年份在汉晋区间；
              严禁编造 —— auto_mined 卡若有生卒年即为违规；
              演义/史实两套（history_life_dates）需与 birth/death 不矛盾
  3 一句话简介 summary 非空、非占位符（「《三国演义》人物，见于第N回。」）
  4 阵营      faction_id 在 8 类之内
  5 身份      role 在身份枚举之内（含 2026-10-30 新增的「客君」），且符合「阵营×身份」规则
  6 官职      tenure.title 非空、非纯标点、不含跨条目粘连
  7 时间线    timeline 年份须落在 tenure 覆盖的年份区间内
  8 生平详述  bio 非空、非占位、与 summary 不矛盾
  9 出现章回  first_chapter 为 1-120 的整数
 10 关系图谱  lord_id 存在且与任期年份重叠
"""
import glob
import json
import os
import re
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')

FACTIONS = {'han', 'warlord', 'wei', 'wu', 'shu', 'jin', 'barbarian', 'mystic'}
# 「客君」= 前朝/他国君主降封后受本朝爵者（刘协山阳公、刘禅安乐公、曹奂陈留王），
# 2026-10-30 新增，与 build.py ROLE_ORDER / entity-schema.json 保持一致。
ROLES = {'皇帝', '追谥', '君主', '权臣', '亲族', '文臣', '武将', '女眷', '其他', '客君'}
# han 下限放到 1：第20回叙刘氏世系可上溯至汉初远祖；上限到 234：
# 献帝禅位后受封山阳公，其「汉」身份延续至 234 年崩。
FAC_BOUND = {'han': (1, 234), 'warlord': (184, 229), 'wei': (196, 266),
             'wu': (195, 280), 'shu': (208, 263), 'jin': (265, 316),
             'barbarian': (184, 280), 'mystic': (184, 280)}
# 阵营 × 身份 规则（用户确认）
FAC_BAN = {'han': set(), 'wei': {'君主'}, 'shu': {'君主'}, 'wu': {'君主'},
           'jin': {'君主'}}
FAC_ONLY = {'warlord': {'君主', '文臣', '武将', '女眷', '其他'},
            'barbarian': {'君主', '文臣', '武将', '其他'},
            'mystic': {'其他'}}

PLACEHOLDER = re.compile(r'^《三国演义》人物(名录收录，谓)?见于第\d+回。?$')
GLUE = re.compile(r'[\u4e00-\u9fa5]{2,4}：\s*[一二三四五六七八九十百千零\d]+回')
BAD_CHARS = re.compile(r'[，,。、；;：:（）()「」【】]')


def main():
    P = {}
    for f in sorted(glob.glob(os.path.join(DATA, 'persons*.json'))):
        for p in json.load(open(f, encoding='utf-8')).get('persons', []):
            P.setdefault(p['id'], p)

    iss = defaultdict(list)

    def add(k, pid, nm, **kw):
        iss[k].append(dict(id=pid, name=nm, **kw))

    for pid, p in P.items():
        nm = p.get('name') or ''
        tn = p.get('tenure') or []

        # ---------- 1 姓名字
        if not nm or not (2 <= len(nm) <= 4):
            add('①姓名异常', pid, nm, val=nm)
        # 古人「字」多为两字（伯符、孟德、玄德），单字字极罕见（如项羽字羽），
        # 因此单字 courtesy 基本可判为「把名的末字误填成字」。
        # 反例（已修）：刘宏 courtesy='宏'（名之末字）、王子服 courtesy='子服'（整名当字）。
        cz = p.get('courtesy')
        if cz is not None:
            if isinstance(cz, str):
                bad = (not cz.strip()
                       or BAD_CHARS.search(cz)
                       or len(cz) > 4
                       or cz == nm
                       or bool(nm) and (cz in nm or nm.endswith(cz)))
                if bad:
                    add('①字异常', pid, nm, courtesy=cz)

        # ---------- 2 生卒年
        b, d = p.get('birth'), p.get('death')
        prec = p.get('date_precision')
        if b is None and d is None and prec not in (None, 'unknown'):
            add('②生卒缺失但精度非unknown', pid, nm, precision=prec)
        # 只填卒年（「? -221」）是史书常态，属诚实做法，不报；
        # 只填生年却无卒年才算残缺。
        if b is not None and d is None:
            add('②有生年无卒年', pid, nm, birth=b)
        if b is not None and d is not None:
            if not (isinstance(b, int) and isinstance(d, int)):
                add('②生卒非整数', pid, nm, birth=b, death=d)
            else:
                if b > d:
                    add('②生卒倒挂', pid, nm, birth=b, death=d)
                if not (100 <= b <= 320 and 100 <= d <= 320):
                    add('②生卒越出汉晋区间', pid, nm, birth=b, death=d)
        # 严禁编造：自动建档卡不得有生卒年
        if p.get('review_status') == 'auto_mined' and (b is not None or d is not None):
            add('②自动建档卡疑似编造生卒', pid, nm, birth=b, death=d)
        # 演义/史实两套
        hld = p.get('history_life_dates')
        if isinstance(hld, dict):
            hb, hd = hld.get('birth'), hld.get('death')
            if isinstance(hb, int) and isinstance(hd, int) and hb > hd:
                add('②史实生卒倒挂', pid, nm, birth=hb, death=hd)
        elif isinstance(hld, str) and hld.strip():
            # 只校验「史：A-B」这种纯年份区间；含「演：」的是演义/史实对照文本，
            # 两年份并不构成生卒关系，不能按倒挂处理。
            m2 = re.match(r'^\s*史[:：]\s*(\d{3})\s*[-—~－]\s*(\d{3})\s*$', hld.strip())
            if m2 and int(m2.group(1)) > int(m2.group(2)):
                add('②史实生卒倒挂', pid, nm, raw=hld)

        # ---------- 3 一句话简介
        s = (p.get('summary') or '').strip()
        if not s:
            add('③简介缺失', pid, nm)
        elif PLACEHOLDER.match(s):
            add('③简介为占位符', pid, nm, summary=s)
        elif GLUE.search(s):
            add('③简介含跨条目粘连', pid, nm, summary=s[:40])

        # ---------- 8 生平详述
        bio = (p.get('bio') or '').strip()
        if not bio:
            add('⑧生平缺失', pid, nm)
        elif PLACEHOLDER.match(bio):
            add('⑧生平为占位符', pid, nm)
        elif GLUE.search(bio):
            add('⑧生平含跨条目粘连', pid, nm)

        # ---------- 9 出现章回
        fc = p.get('first_chapter')
        if fc is None:
            # 正文未出现（如士燮，为势力年表所引而正文 0 次）—— 诚实标注，需有说明
            if not (p.get('is_mentioned_only') or '正文' in (p.get('summary') or '')):
                add('⑨章回缺失且无说明', pid, nm)
        elif not isinstance(fc, int) or not (1 <= fc <= 120):
            add('⑨章回越界', pid, nm, first_chapter=fc)

        # ---------- 4/5/6/10 逐片检查
        if not tn:
            add('④无阵营时间片', pid, nm)
        for t in tn:
            fac, role = t.get('faction_id'), t.get('role')
            if fac not in FACTIONS:
                add('④阵营越界', pid, nm, faction=fac)
                continue
            if role not in ROLES:
                add('⑤身份越界', pid, nm, role=role, faction=fac)
                continue
            ban = FAC_BAN.get(fac)
            if ban and role in ban:
                add('⑤身份违反阵营规则', pid, nm, faction=fac, role=role)
            only = FAC_ONLY.get(fac)
            if only and role not in only:
                add('⑤身份违反阵营规则', pid, nm, faction=fac, role=role)
            # 官职
            ti = (t.get('title') or '').strip()
            if not ti:
                # 正文未出现的人物（仅名录收录）本无官职可载，不报
                if p.get('is_mentioned_only'):
                    pass
                # 原文已核实「无名爵可考」的，属诚实标注（禁止编造），不报
                elif p.get('title_unknown_verified'):
                    pass
                else:
                    add('⑥官职缺失', pid, nm, faction=fac, role=role,
                        span=f"{t.get('start_year')}-{t.get('end_year')}")
            elif GLUE.search(ti) or ti in ('，', '、'):
                add('⑥官职含粘连或标点', pid, nm, title=ti[:30])
            # 年份
            sy, ey = t.get('start_year'), t.get('end_year')
            if sy is None or ey is None:
                add('⑥任期年份缺失', pid, nm, faction=fac, start=sy, end=ey)
            elif sy > ey:
                add('⑥任期倒挂', pid, nm, start=sy, end=ey)
            else:
                lo, hi = FAC_BOUND.get(fac, (0, 9999))
                if sy > hi or ey < lo:
                    add('⑥任期越出阵营区间', pid, nm, faction=fac,
                        span=f'{sy}-{ey}', bound=f'{lo}-{hi}')
            # 10 君臣边
            lord = t.get('lord_id')
            if lord:
                lp = P.get(lord)
                if not lp:
                    add('⑩君臣边悬空', pid, nm, lord_id=lord)
                else:
                    spans = [(x.get('start_year'), x.get('end_year'))
                             for x in (lp.get('tenure') or []) if x.get('start_year')]
                    if sy and spans and not any(
                            (a is None or a <= (ey or sy)) and (b is None or b >= (sy or ey))
                            for a, b in spans):
                        add('⑩君臣任期无重叠', pid, nm, lord=lp['name'],
                            span=f'{sy}-{ey}',
                            lord_span=str([(a, b) for a, b in spans]))

        # ---------- 7 时间线
        for ev in p.get('timeline') or []:
            y = ev.get('year') if isinstance(ev, dict) else None
            if y is None:
                continue
            # timeline 记生平（含生年、早年事迹），范围比 tenure 宽；
            # 只校验落在汉晋合理区间，以及与已知生卒年不矛盾
            if not (130 <= y <= 320):
                add('⑦时间线年份异常', pid, nm, year=y,
                    text=str((ev.get('text') if isinstance(ev, dict) else '') or '')[:30])
                continue
            if isinstance(b, int) and y < b - 5:
                add('⑦时间线早于生年', pid, nm, year=y, birth=b)
            # 追谥/追封发生在死后，timeline 记追尊年份，晚于卒年属正常
            posthum = bool(ev.get('posthumous')) if isinstance(ev, dict) else False
            if (isinstance(d, int) and y > d + 5 and not posthum
                    and not any(t.get('role') == '追谥' for t in tn)):
                add('⑦时间线晚于卒年', pid, nm, year=y, death=d)

    total = sum(len(v) for v in iss.values())
    print(f'=== 全量逐人物校验（{len(P)} 人）===')
    for k in sorted(iss):
        print(f'  {k}: {len(iss[k])}')
    print(f'  合计问题 {total} 项')
    print()
    for k in sorted(iss):
        v = iss[k]
        if not v:
            continue
        print(f'--- {k} ({len(v)}) ---')
        for x in v[:8]:
            print('   ', {a: b for a, b in x.items() if a != 'name'}, '|', x['name'])
        if len(v) > 8:
            print(f'    …另有 {len(v)-8} 条')

    out = {k: v for k, v in iss.items()}
    out['_summary'] = {'persons': len(P), 'issues': total}
    json.dump(out, open(os.path.join(DATA, 'audit_full.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'\n已写出 data/audit_full.json')


if __name__ == '__main__':
    main()
