#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阵营 × 身份 规则收口（用户确认的规则）

  R1 称帝者：未称帝前 → 群雄/君主；称帝后 → 对应阵营/皇帝
  R2 从未称帝但获追谥 → 对应阵营/追谥（已有片保留）
  R3 异族/群雄出身的君主，若曾属其他阵营且非其主公、仅为下属
     → 按对应阵营官职归文臣/武将，官职不明默认武将
  R4 异族禁设「女眷」→ 归武将
  R5 群雄女眷：核实所属时期君主是否称帝；未称帝 → 群雄/女眷；
     称帝后 → 对应势力/女眷

改动清单（共 10 片）：
  刘备   shu/君主 208-221  → warlord/君主    （221 才称帝）
  曹操   wei/君主 196-220  → warlord/君主    （从未称帝，追谥片已在 wei）
  孙策   wu/君主 195-200   → warlord/君主    （从未称帝，追谥片已在 wu）
  孙权   wu/君主 200-229   → warlord/君主    （229 才称帝）
  孟获   shu/君主 225-234  → shu/武将        （降蜀后为洞主，非主公，官职不明→武将）
  貂蝉   warlord/女眷      → han/女眷        （王允府歌伎，其时献帝在位）
  郭女王 warlord/女眷      → wei/女眷 220-235（曹丕皇后，丕 220 称帝）
  张皇后 warlord/女眷      → wei/女眷 243-254（曹芳皇后，张缉之女，见 109 回）
  崔夫人 warlord/女眷      → shu/女眷 255-263（刘谌妻，见 118 回）
  祝融夫人 barbarian/女眷  → barbarian/武将  （R4）
其余 15 位群雄女眷经核实其主君（孙坚/吕布/刘备称帝前/刘表/张绣/袁术等）
均未称帝，按 R5 保留 warlord/女眷。
"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')

# (person_id, start_year) -> 新 faction/role/年份/title/basis
CHANGE = {
    ('liu_bei', 208): {'faction_id': 'warlord', 'role': '君主',
                       'basis': '208-221 为荆州牧、益州牧、汉中王，尚未称帝；221 年称帝后归蜀汉/皇帝。'},
    ('cao_cao', 196): {'faction_id': 'warlord', 'role': '君主',
                       'basis': '196-220 为司空、丞相、魏公、魏王，终身未称帝；死后追尊武皇帝（wei/追谥）。'},
    ('sun_ce', 195): {'faction_id': 'warlord', 'role': '君主',
                      'basis': '195-200 为讨逆将军、吴侯，终身未称帝；后追谥长沙桓王（wu/追谥）。'},
    ('sun_quan', 200): {'faction_id': 'warlord', 'role': '君主',
                        'basis': '200-229 为讨虏将军、吴侯、吴王，尚未称帝；229 年称帝后归孙吴/皇帝。'},
    ('meng_huo', 225): {'faction_id': 'shu', 'role': '武将',
                        'basis': '降蜀后为洞主，非蜀汉主公，官职不明，依规则默认武将。'},
    ('diao_chan', 192): {'faction_id': 'han', 'role': '女眷',
                         'basis': '王允府中歌伎，行连环计于 192 年前后，其时献帝在位、汉祚未终。'},
    # ('guo_nv_wang', ...) 已删除：郭皇后与郭夫人为同一人，已合并至 guo_fu_ren。
    ('guo_fu_ren', 235): {'faction_id': 'wei', 'role': '女眷',
                           'start_year': 220, 'end_year': 235,
                           'basis': '曹丕皇后（郭女王），丕 220 年称帝后归曹魏；卒于 235 年。'},
    ('zhang_huang_hou', 229): {'faction_id': 'wei', 'role': '女眷',
                               'start_year': 243, 'end_year': 254,
                               'basis': '曹芳皇后，张缉之女（第 109 回「缉乃张皇后之父，曹芳之皇丈也」），254 年随芳被废。'},
    ('cui_fu_ren', 229): {'faction_id': 'shu', 'role': '女眷',
                          'start_year': 255, 'end_year': 263,
                          'basis': '北地王刘谌之妻（第 118 回），刘禅子妇，蜀汉既立（221）归蜀汉；263 年殉国。'},
    ('zhu_rong_fu_ren', 225): {'faction_id': 'barbarian', 'role': '武将',
                               'basis': '异族不设女眷；祝融夫人以飞刀作战，孟获妻，归武将。'},
}


def merge_adjacent(tn, pid):
    """合并相邻的同阵营同身份片（如曹操 189-196 + 196-220 → 189-220）"""
    out = []
    for t in sorted(tn, key=lambda x: x.get('start_year') or 0):
        if out:
            a = out[-1]
            if (a.get('faction_id') == t.get('faction_id')
                    and a.get('role') == t.get('role')
                    and a.get('lord_id') == t.get('lord_id')
                    and a.get('end_year') == t.get('start_year')):
                a['end_year'] = t.get('end_year')
                a['title'] = '、'.join(x for x in (a.get('title'), t.get('title')) if x)
                continue
        out.append(t)
    return out


def main():
    apply = '--fix' in sys.argv
    log = []
    for f in sorted(glob.glob(os.path.join(DATA, 'persons*.json'))):
        d = json.load(open(f, encoding='utf-8'))
        dirty = False
        for p in d.get('persons', []):
            tn = p.get('tenure') or []
            hit = False
            for t in tn:
                rule = CHANGE.get((p['id'], t.get('start_year')))
                if not rule:
                    continue
                old = f"{t.get('faction_id')}/{t.get('role')} {t.get('start_year')}-{t.get('end_year')}"
                t['faction_id'] = rule['faction_id']
                t['role'] = rule['role']
                if 'start_year' in rule:
                    t['start_year'] = rule['start_year']
                if 'end_year' in rule:
                    t['end_year'] = rule['end_year']
                t['basis'] = rule['basis']
                new = f"{t['faction_id']}/{t['role']} {t.get('start_year')}-{t.get('end_year')}"
                log.append((p['name'], old, new))
                hit = dirty = True
            if hit:
                p['tenure'] = merge_adjacent(tn, p['id'])
        if dirty and apply:
            json.dump(d, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print(f'改动 {len(log)} 片' + ('' if apply else '（预演，加 --fix 写回）'))
    for nm, o, n in log:
        print(f'  {nm:5s} {o}  →  {n}')


if __name__ == '__main__':
    main()
