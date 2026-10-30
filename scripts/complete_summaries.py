#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把残缺短片段 summary 补全为通顺的一句话简介。

覆盖三类：
  A. 占位符「《三国演义》人物，见于第N回。」→ 用阵营+身份+官职重写
  B. 短片段「九江太守，为截杀」「从人，杀孙翊」→ 补主语、补被动词
  C. 笼统片段「东吴谋士」「汝阳人」→ 保持，但补首见回目

所有信息都来自卡内已有字段（tenure 的阵营/身份/官职、first_chapter），不新增事实。
"""
import json, glob, re, sys

ROOT = '/workspace/读三国-project'
FAC_CN = {'han': '东汉', 'warlord': '群雄', 'wei': '曹魏', 'wu': '孙吴',
          'shu': '蜀汉', 'jin': '西晋', 'barbarian': '南蛮', 'mystic': '神怪'}
ROLE_CN = {'皇帝': '皇帝', '追谥': '追尊', '君主': '君主', '权臣': '权臣',
           '亲族': '宗室', '文臣': '文臣', '武将': '武将', '女眷': '女眷', '其他': ''}
PLACEHOLDER = re.compile(r'^《三国演义》人物[，,]?\s*见于第\s*\d+\s*回。?$')

# 片段里常见的「为X」「被X」残缺，补成完整被动句
FIX_TAIL = [
    (re.compile(r'为截杀$'), '为截击所杀'),
    (re.compile(r'为斩$'), '为敌所斩'),
    (re.compile(r'为杀$'), '被杀'),
    (re.compile(r'为射死$'), '为箭所射死'),
    (re.compile(r'为擒，?后放回$'), '为擒，后放回'),
    (re.compile(r'为所擒$'), '为所擒'),
]

# 明显残缺、无法成句的尾巴，直接丢弃
DROP_TAIL = re.compile(r'[，,]\s*(字|将|帐下|部曲|等|与|善|从人|门客)$')

# 只有身份词、没有信息量的片段
MEANINGLESS = re.compile(r'^(将|部将|从人|门客|字|蜀将|曹将|魏将|吴将|晋将|袁术将|黄祖将|帐下|部曲)$')
# 「X将，帐下」这类：身份词+方位词，整体无信息量
USELESS_CORE = re.compile(r'^(蜀将|曹将|魏将|吴将|晋将|群雄武将|将|大将)$')


def norm_title(t):
    t = (t or '').strip()
    return '' if ('（原文未载' in t or not t) else t


def build(p):
    name = p['name']
    tns = [t for t in (p.get('tenure') or []) if isinstance(t, dict)]
    last = None
    if tns:
        last = sorted(tns, key=lambda t: (t.get('end_year') or 0, t.get('start_year') or 0))[-1]
    fac = FAC_CN.get(last.get('faction_id'), '') if last else ''
    role = ROLE_CN.get(last.get('role'), '') if last else ''
    title = norm_title(last.get('title')) if last else ''
    fc = p.get('first_chapter')

    old = (p.get('summary') or '').strip()

    # A. 占位符：完全重写
    if PLACEHOLDER.match(old) or not old:
        body = fac + (role if role and role != fac else '')
        s = name + '，' + (body or '《三国演义》人物')
        if title:
            s += '，' + title
        s += '。'
        if isinstance(fc, int):
            s += f'见于第 {fc} 回。'
        return s

    # B/C. 片段：若已有「名，…」结构就规范化
    core = old
    if core.startswith(name):
        core = core[len(name):].lstrip('，,')
    for pat, rep in FIX_TAIL:
        core = pat.sub(rep, core)
    core = DROP_TAIL.sub('', core)
    # 片段以虚词/顿号起头，说明截断错位，切到第一个逗号后的实义部分
    if re.match(r'^[与和及并、，。]', core):
        parts = [x for x in re.split(r'[，,、]', core) if x.strip()]
        core = max(parts, key=len) if parts else ''
    core = core.strip('，。').strip()

    # 逐段清理：去掉「帐下」「部曲」等无信息尾段
    if core:
        segs = [x.strip() for x in re.split(r'[，,]', core) if x.strip()]
        segs = [x for x in segs if x not in ('帐下', '部曲', '麾下', '手下', '等')]
        core = '，'.join(segs)

    # 片段无实义（只剩「将」「门客」等身份词）→ 用结构化信息重写
    if not core or MEANINGLESS.match(core):
        body = fac + (role if role and role != fac else '')
        core = (title or '') if title and len(title) > 1 and not MEANINGLESS.match(title) else body
        if not core:
            core = '《三国演义》人物'

    s = name + '，' + core
    if not re.search(r'[。！？]$', s):
        s += '。'
    # 片段里没有阵营词时，用括注补归属（含标点）
    if fac and fac not in s and role not in s:
        s = s.rstrip('。') + f'（{fac}{role}）。'
    if isinstance(fc, int) and f'第 {fc} 回' not in s and f'第{fc}回' not in s:
        s = s.rstrip('。') + f'见于第 {fc} 回。'
    return s


def main(apply=False):
    changed = []
    for f in sorted(glob.glob(f'{ROOT}/data/persons*.json')):
        d = json.load(open(f, encoding='utf-8'))
        dirty = False
        for p in d.get('persons', []):
            old = (p.get('summary') or '').strip()
            # 只处理占位符与短片段，已写好的不动
            if not (PLACEHOLDER.match(old) or len(old) < 16):
                continue
            new = build(p)
            if new and new != old:
                changed.append((p['name'], old, new))
                if apply:
                    p['summary'] = new
                    dirty = True
        if dirty:
            json.dump(d, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'{"已补全" if apply else "预演"}：{len(changed)} 张')
    for nm, o, n in changed[:20]:
        print(f'  {nm:6s} {o[:26]:28s} → {n[:56]}')


if __name__ == '__main__':
    main('--fix' in sys.argv)
