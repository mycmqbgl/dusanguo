#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""皇帝身份归位 · 第二轮（针对「皇帝只有 5 位」的核查）

查出的问题：
  A 八位真皇帝被归「君主」（曹叡/曹芳/曹髦/曹奂/刘禅/孙亮/孙休/孙皓）——
    他们的 title 里明写着「皇帝」，却没进「皇帝」分类。
  B 汉灵帝有两张重复卡（liu_hong_2「刘宏」surfaces 为空 + han_ling_di「汉灵帝」），
    且都标 warlord/武将。
  C 司马炎只有「wei/武将 258-266」一片 —— 西晋开国皇帝的身份整个缺失。
  D 司马懿/司马师/司马昭缺「追谥」片（晋追尊宣帝/景帝/文帝）。
  E 宗室皇子（孙和/孙匡/曹植/刘永…）被归「君主」，应为「亲族」或有实职者按实职。
  F 张悌/伍延/张象 三位吴将（title 写「吴丞相」「吴车骑将军」「吴前将军」）
    被归到 jin 阵营 280-316，应回 wu。
  G 司马防/司马朗 是汉臣（京兆尹/汉主簿），被标 wei/文臣 208-266。
"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')

# A+C+D+G：整段 tenure 重写（按 start_year 排序后写入）
REWRITE = {
    'cao_rui': [{'faction_id': 'wei', 'role': '皇帝', 'start_year': 226, 'end_year': 239,
                 'title': '魏明帝（太和、青龙、景初）',
                 'basis': '文帝太子，226 年即位，曹魏第二代皇帝。', 'confidence': 0.95}],
    'cao_fang': [{'faction_id': 'wei', 'role': '皇帝', 'start_year': 239, 'end_year': 254,
                  'title': '魏齐王（正始、嘉平）',
                  'basis': '明帝养子，八岁即位，254 年为司马师所废。', 'confidence': 0.95}],
    'cao_mao': [{'faction_id': 'wei', 'role': '皇帝', 'start_year': 254, 'end_year': 260,
                 'title': '魏高贵乡公（正元、甘露）',
                 'basis': '文帝之孙，254 年立，260 年讨司马昭被杀。', 'confidence': 0.95}],
    # 曹奂：258 封常道乡公（宗室），260 年即帝位
    'cao_huan': [
        {'faction_id': 'wei', 'role': '亲族', 'start_year': 258, 'end_year': 260,
         'title': '常道乡公（曹宇子，原名璜）',
         'basis': '258 年受封常道乡公，此时尚为宗室。', 'confidence': 0.85},
        {'faction_id': 'wei', 'role': '皇帝', 'start_year': 260, 'end_year': 266,
         'title': '魏元帝（景元、咸熙）',
         'basis': '260 年曹髦被杀后即位，265 年禅位司马炎，魏亡。', 'confidence': 0.95}],
    'liu_shan': [
        {'faction_id': 'shu', 'role': '皇帝', 'start_year': 223, 'end_year': 263,
         'title': '蜀汉后主（建兴、延熙、景耀）',
         'basis': '223 年即位，263 年降魏。', 'confidence': 0.95},
        {'faction_id': 'wei', 'role': '其他', 'start_year': 263, 'end_year': 266,
         'title': '安乐公', 'lord_id': 'cao_huan',
         'basis': '263 年降魏受封安乐公，非君主。', 'confidence': 0.9}],
    'sun_liang': [{'faction_id': 'wu', 'role': '皇帝', 'start_year': 252, 'end_year': 258,
                   'title': '吴废帝（建兴、五凤、太平）',
                   'basis': '孙权少子，252 年立，258 年为孙綝所废。', 'confidence': 0.95}],
    'sun_xiu': [{'faction_id': 'wu', 'role': '皇帝', 'start_year': 258, 'end_year': 264,
                 'title': '吴景帝（永安）',
                 'basis': '孙权第六子，孙綝所立，264 年崩。', 'confidence': 0.95}],
    'sun_hao': [{'faction_id': 'wu', 'role': '皇帝', 'start_year': 264, 'end_year': 280,
                 'title': '吴末帝（元兴、甘露至天纪）',
                 'basis': '264 年立，280 年降晋，吴亡。', 'confidence': 0.95}],
    # C 司马炎：世子 → 相国晋王 → 西晋开国皇帝
    'si_ma_yan': [
        {'faction_id': 'wei', 'role': '亲族', 'start_year': 258, 'end_year': 265,
         'title': '晋王世子（司马昭长子）', 'lord_id': 'sim_zhao',
         'basis': '司马昭长子，265 年前为晋王世子。', 'confidence': 0.85},
        {'faction_id': 'jin', 'role': '皇帝', 'start_year': 265, 'end_year': 290,
         'title': '西晋武帝（泰始、咸宁、太康、太熙）',
         'basis': '265 年代魏称帝，280 年灭吴一统，290 年崩。', 'confidence': 0.95}],
    # G 汉臣
    'si_ma_fang': [{'faction_id': 'han', 'role': '文臣', 'start_year': 190, 'end_year': 219,
                    'title': '汉京兆尹',
                    'basis': '司马懿之父，汉京兆尹，卒于汉末（约 219）。', 'confidence': 0.8}],
    'si_ma_lang': [{'faction_id': 'han', 'role': '文臣', 'start_year': 196, 'end_year': 217,
                    'title': '汉主簿、兖州刺史',
                    'basis': '司马懿之兄，汉臣，217 年从征濡须时染疫卒。', 'confidence': 0.8}],
    # F 吴将归吴
    'zhang_ti': [{'faction_id': 'wu', 'role': '文臣', 'start_year': 275, 'end_year': 280,
                  'title': '吴丞相', 'lord_id': 'sun_hao',
                  'basis': 'title 明载「吴丞相」，280 年抗晋战死，非晋臣。', 'confidence': 0.85}],
    'wu_yan': [{'faction_id': 'wu', 'role': '武将', 'start_year': 275, 'end_year': 280,
                'title': '吴车骑将军', 'lord_id': 'sun_hao',
                'basis': 'title 明载「吴车骑将军」，属孙吴。', 'confidence': 0.85}],
    'zhang_xiang': [{'faction_id': 'wu', 'role': '武将', 'start_year': 278, 'end_year': 280,
                     'title': '吴前将军（后降晋）', 'lord_id': 'sun_hao',
                     'basis': 'title 明载「吴前将军」，280 年降晋，出身孙吴。', 'confidence': 0.85}],
    # B 汉灵帝
    'han_ling_di': [{'faction_id': 'han', 'role': '皇帝', 'start_year': 168, 'end_year': 189,
                     'title': '汉灵帝（建宁、熹平、光和、中平）',
                     'basis': '名刘宏，168 年即位，189 年崩，东汉末期的在位皇帝。',
                     'confidence': 0.95}],
}

# D 追加「追谥」片（不覆盖既有）
APPEND = {
    'sim_yi': [{'faction_id': 'jin', 'role': '追谥', 'start_year': 266, 'end_year': 316,
                'title': '晋宣帝（司马炎追尊）',
                'basis': '266 年司马炎称帝后追尊为宣皇帝。', 'confidence': 0.9}],
    'sim_shi': [{'faction_id': 'jin', 'role': '追谥', 'start_year': 266, 'end_year': 316,
                 'title': '晋景帝（追尊）',
                 'basis': '司马炎追尊为景皇帝。', 'confidence': 0.9}],
    'sim_zhao': [{'faction_id': 'jin', 'role': '追谥', 'start_year': 266, 'end_year': 316,
                  'title': '晋文帝（追尊）',
                  'basis': '司马炎追尊为文皇帝。', 'confidence': 0.9}],
}

# E 宗室：无实职的皇子/王 → 亲族；有实职的按实职
KINSMAN = {
    'sun_he': '亲族', 'sun_kuang': '亲族', 'sun_lang': '亲族',
    'cao_lin': '亲族', 'cao_yu': '亲族', 'cao_ju': '亲族', 'cao_zhi': '亲族',
    'liu_yong': '亲族', 'liu_li': '亲族', 'liu_chen': '亲族',
    'si_ma_you': '亲族',
    'sun_ben': '武将', 'sun_yi_2': '武将', 'si_ma_wang': '武将',
}

DROP_IDS = {'liu_hong_2'}   # 与 han_ling_di 重复，且 surfaces 为空


def main():
    apply = '--fix' in sys.argv
    log = []
    for f in sorted(glob.glob(os.path.join(DATA, 'persons*.json'))):
        d = json.load(open(f, encoding='utf-8'))
        before = [p['id'] for p in d.get('persons', [])]
        d['persons'] = [p for p in d.get('persons', []) if p['id'] not in DROP_IDS]
        dropped = DROP_IDS.intersection(before)
        if dropped:
            log.append(('删重复卡', ','.join(sorted(dropped)), '与 han_ling_di 重复'))
        dirty = bool(dropped)
        for p in d['persons']:
            pid = p['id']
            if pid in REWRITE:
                old = [(t.get('faction_id'), t.get('role'), t.get('start_year'))
                       for t in (p.get('tenure') or [])]
                p['tenure'] = [dict(x) for x in REWRITE[pid]]
                log.append(('重写', p['name'], f'{old} -> {len(p["tenure"])} 片'))
                dirty = True
            for spec in APPEND.get(pid, []):
                tn = p.setdefault('tenure', [])
                if any(t.get('role') == spec['role'] and t.get('faction_id') == spec['faction_id']
                       for t in tn):
                    continue
                tn.append(dict(spec))
                tn.sort(key=lambda x: x.get('start_year') or 0)
                log.append(('追加', p['name'], f'{spec["faction_id"]}/{spec["role"]} {spec["start_year"]}'))
                dirty = True
            if pid in KINSMAN:
                for t in p.get('tenure', []) or []:
                    if t.get('role') == '君主':
                        log.append(('归位', p['name'], f'君主 -> {KINSMAN[pid]}'))
                        t['role'] = KINSMAN[pid]
                        dirty = True
        if dirty and apply:
            json.dump(d, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print(f'改动 {len(log)} 处' + ('' if apply else '（预演，加 --fix 写回）'))
    for a, b, c in log:
        print(f'  [{a}] {b}: {c}')


if __name__ == '__main__':
    main()
