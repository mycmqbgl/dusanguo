#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人物卡 schema 校验器（P0 批产质检）
依据 data/entity-schema.json 的枚举与约束，校验人物卡 JSON。
用法：python scripts/validate_cards.py data/batch_test_5.json [输出报告路径]
"""
import json, io, os, sys, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA = json.load(io.open(os.path.join(ROOT, 'data', 'entity-schema.json'), encoding='utf-8'))

FACTION_SEED = {f['id']: f for f in
                [x for t in SCHEMA['tables'] if t['name'] == 'faction' for x in t['seed']]}
ROLE_IMPERIAL = SCHEMA['enums']['role_imperial']['values']
ROLE_LORD = SCHEMA['enums']['role_lord']['values']
DATE_PREC = SCHEMA['enums']['date_precision']['values']
POSTHUMOUS_FACTIONS = {'wei', 'wu', 'shu', 'jin'}
CONFLICT_TYPES = SCHEMA['enums'].get('history_conflict_type', {}).get('values', [])
REQUIRED = ['id', 'name', 'summary', 'bio', 'date_precision', 'gender', 'first_chapter']

def check_person(p):
    errs, warns = [], []
    pid = p.get('id', '?')
    for f in REQUIRED:
        if p.get(f) in (None, ''):
            errs.append(('REQUIRED', f'缺少必填字段 {f}'))
    if p.get('date_precision') not in DATE_PREC:
        errs.append(('ENUM', f'date_precision 非法：{p.get("date_precision")}'))
    b, d = p.get('birth'), p.get('death')
    if b is not None and d is not None and d < b:
        errs.append(('DATE', f'death({d}) < birth({b})'))
    # 决策 #5：不确定必须 null，禁止推测年份
    # 档位语义（P1-B 修订）：date_precision 描述「已填年份」的精度档，不描述整张卡的完整度。
    #   生年不详而卒年确切是常态（陈寿多不载生年），此时标 exact 合法，但 date_note 必须
    #   注明哪一端不详。若按「最短板」解释，几乎所有人物都要降为 approx，反而丢掉「卒年确切」。
    if p.get('date_precision') == 'exact' and b is None and d is None:
        errs.append(('DATE_PREC', 'birth 与 death 皆空却标 exact（exact 要求至少一端有确切年份）'))
    if p.get('date_precision') == 'unknown' and (b is not None or d is not None):
        errs.append(('DATE_PREC', f'标记 unknown 却填了年份（疑似推测）：birth={b}, death={d}'))
    # 缺端必须写明，否则等于默认「没人知道」，读者无从判断
    note = p.get('date_note') or ''
    if b is None and not any(k in note for k in ('生年', '生卒')):
        warns.append(('DATE_NOTE', '生年为空但 date_note 未说明「生年不详」'))
    if d is None and not any(k in note for k in ('卒年', '生卒')):
        warns.append(('DATE_NOTE', '卒年为空但 date_note 未说明「卒年不详」'))
    # 寿命合理性：抓「把两个人的年份拼到一张卡」这类硬错
    if b is not None and d is not None and not (10 <= d - b <= 105):
        errs.append(('DATE', f'寿命异常 {d - b} 岁（birth={b}, death={d}）'))

    tenures = p.get('tenure') or []
    if not tenures:
        errs.append(('TENURE', '无阵营时间片'))
    seen = {}
    for t in tenures:
        fid, role = t.get('faction_id'), t.get('role')
        s, e = t.get('start_year'), t.get('end_year')
        fac = FACTION_SEED.get(fid)
        if not fac:
            errs.append(('FACTION', f'阵营 {fid} 不存在')); continue
        allowed = ROLE_LORD if fid in ('warlord', 'barbarian') else (['其他'] if fid == 'mystic' else ROLE_IMPERIAL)
        if role not in allowed:
            errs.append(('ROLE', f'{fac["name"]} 下角色「{role}」非法，可用：{"/".join(allowed)}'))
        if role == '追谥' and fid not in POSTHUMOUS_FACTIONS:
            errs.append(('ROLE', f'「追谥」仅限曹魏/孙吴/蜀汉/晋，不能在 {fac["name"]}（N4 定案）'))
        if s is None or e is None or e < s:
            errs.append(('TENURE', f'时间片区间非法：{s}–{e}')); continue
        lower = fac.get('de_facto_start') or fac.get('start_year')
        if fid != 'mystic' and lower and (s < lower or (fac.get('end_year') and e > fac['end_year'])):
            errs.append(('TENURE', f'{fac["name"]} 势力起于 {lower}、国号止于 {fac["end_year"]}，时间片 {s}–{e} 越界'))
        if d is not None and role not in ('追谥', '亲族') and e > d:
            errs.append(('TENURE', f'卒于 {d}，但 {fac["name"]}·{role} 时间片延至 {e}'))
        seen.setdefault(fid, []).append((s, e))
    # 同阵营重叠
    for fid, arr in seen.items():
        arr.sort()
        for i in range(len(arr) - 1):
            if arr[i + 1][0] < arr[i][1]:
                errs.append(('TENURE', f'{FACTION_SEED[fid]["name"]} 内时间片重叠：{arr[i]} 与 {arr[i+1]}'))
    # 跨阵营：须首尾相接，死亡后的空档豁免
    flat = sorted([(t['start_year'], t['end_year'], t['faction_id']) for t in tenures if t.get('start_year') is not None])
    for i in range(len(flat) - 1):
        gap_from, gap_to = flat[i][1], flat[i + 1][0]
        if gap_to < gap_from:
            errs.append(('TENURE', f'{flat[i][2]}({flat[i][0]}–{gap_from}) 与 {flat[i+1][2]}({gap_to}–{flat[i+1][1]}) 跨阵营重叠'))
        elif gap_to - gap_from > 1:
            if d is not None and gap_from >= d:
                continue  # 死后追尊/追谥空档
            warns.append(('TENURE_GAP', f'{flat[i][2]}({gap_from}) 与 {flat[i+1][2]}({gap_to}) 之间有空档'))

    tl = p.get('timeline') or []
    per_year = {}
    for n in tl:
        y = n.get('year')
        if d is not None and y is not None and y > d:
            # 追尊、追谥、改葬、平反都是身后之事，允许晚于卒年；
            # 但必须显式标 posthumous=true，否则视为编年错误。
            if n.get('posthumous'):
                warns.append(('TIMELINE', f'身后事节点 {y}「{n.get("title")}」已标 posthumous，允许晚于卒年'))
            else:
                errs.append(('TIMELINE', f'时间线节点 {y}「{n.get("title")}」晚于卒年 {d}；若为追尊/追谥等身后事，须标 posthumous: true'))
        if len(n.get('title') or '') > 10:
            warns.append(('TIMELINE', f'节点标题超 10 字：{n.get("title")}'))
        per_year[y] = per_year.get(y, 0) + 1
    for y, c in per_year.items():
        if c > 2:
            warns.append(('TIMELINE', f'{y} 年有 {c} 条节点（建议 ≤2）'))

    # P1-1 定案（v1.3）：史实冲突走独立字段，type 与 note 必须同时有值或同时为空
    ct, cnote = p.get('history_conflict_type'), (p.get('history_conflict_note') or '').strip()
    if ct in (None, ''):
        if cnote:
            errs.append(('CONFLICT', 'history_conflict_note 有值但 history_conflict_type 为空（须同时有或同时无）'))
    else:
        if ct not in CONFLICT_TYPES:
            errs.append(('CONFLICT', f'history_conflict_type 非法：{ct}，可用：{"/".join(CONFLICT_TYPES)}'))
        if not cnote:
            errs.append(('CONFLICT', 'history_conflict_type 非空但 history_conflict_note 为空'))
        elif '史' not in cnote:
            warns.append(('CONFLICT', 'history_conflict_note 未见「史」字，疑未按「演义…；史实…」句式写'))
        # 同一差异不得再在 date_note 里重复叙述（防两处表述走样）
        for k in ('演义', '史实', '史载', '史书'):
            if k in (p.get('date_note') or '') and k in cnote:
                warns.append(('CONFLICT', f'date_note 与 history_conflict_note 都出现「{k}」，疑似重复叙述同一差异'))
                break

    bio_len = len(p.get('bio') or '')
    if bio_len < 150:
        warns.append(('BIO', f'bio 仅 {bio_len} 字（次要人物建议 200–300）'))
    if bio_len > 900:
        warns.append(('BIO', f'bio 达 {bio_len} 字（核心人物建议 500–800）'))
    return pid, errs, warns

def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'data', 'batch_test_5.json')
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'build', 'validation.json')
    d = json.load(io.open(src, encoding='utf-8'))
    persons = d.get('persons') if isinstance(d, dict) else d
    rows, total_e, total_w, passed = [], 0, 0, 0
    for p in persons:
        pid, errs, warns = check_person(p)
        total_e += len(errs); total_w += len(warns)
        ok = not errs
        passed += 1 if ok else 0
        rows.append({'id': pid, 'name': p.get('name'), 'pass': ok, 'errors': [{'rule': r, 'msg': m} for r, m in errs],
                     'warnings': [{'rule': r, 'msg': m} for r, m in warns]})
    report = {
        'source': os.path.basename(src),
        'total': len(persons), 'passed': passed, 'failed': len(persons) - passed,
        'error_count': total_e, 'warning_count': total_w,
        'pass_rate': round(passed / max(1, len(persons)) * 100, 1),
        'rows': rows,
    }
    # 护栏（2026-10-27 事故）：校验报告绝不能覆盖输入数据。
    # 曾因「传入单个批次文件 + 未传 out」把报告写回 data/persons_ch002_003.json，
    # 17 张卡被 4KB 报告覆盖。以下三条任一命中即中止，宁可不写也不毁数据。
    if os.path.abspath(out) == os.path.abspath(src):
        raise SystemExit(f'拒绝写入：报告路径与输入文件相同 → {out}')
    if os.path.dirname(os.path.abspath(out)) == os.path.join(ROOT, 'data'):
        raise SystemExit(f'拒绝写入：报告不得落在 data/ 目录 → {out}')
    if os.path.abspath(out).endswith('.json') and os.path.basename(out).startswith('persons_'):
        raise SystemExit(f'拒绝写入：报告不得占用批次文件命名 → {out}')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(report, io.open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'校验 {report["source"]}：{passed}/{len(persons)} 通过（{report["pass_rate"]}%），错误 {total_e}，警告 {total_w}')
    for r in rows:
        mark = '✓' if r['pass'] else '✗'
        print(f'  {mark} {r["name"]}  err={len(r["errors"])} warn={len(r["warnings"])}')
        for e in r['errors']:
            print(f'      [{e["rule"]}] {e["msg"]}')
        for w in r['warnings']:
            print(f'      ~ [{w["rule"]}] {w["msg"]}')
    print(f'报告 → {out}')
    return 0 if report['failed'] == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
