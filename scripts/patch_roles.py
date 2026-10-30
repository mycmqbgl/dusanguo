#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
身份 / 时间片校正（任务④）

依据「谁有多个部下认其为主」的客观证据 + 史事，校正五类问题：

  role 升级：吕布（徐州牧，20 人认其为主）→ 君主
            曹丕（8 人，后称帝）  → 追加魏帝段
            诸葛亮（5 人，蜀丞相摄政）→ 追加蜀汉权臣段
            韩馥（冀州牧，4 人）  → 君主
            司马懿（晚岁专魏政）  → 追加权臣段

  时间片缺失：这些人物原本只有「汉末群雄」时期的一段，缺建国后的归属段，
             导致大势地图、人物页阵营都停在 warlord。按 FAC_BOUND 追加合法区间。

  九宫格归位：祝融夫人虽使飞刀上阵，按 identity_priority 应列女眷。
"""
import json, io, os, glob, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')

PATCH = {
    'lv_bu':        {'set_role': {('warlord', 189): '君主'}},
    'han_fu':       {'set_role': {('warlord', 189): '君主'}},
    'cao_pi':       {'append': [{'faction_id':'wei','role':'皇帝','start_year':220,'end_year':226,
                                 'title':'魏文帝','basis':'建安二十五年（220）受禅即皇帝位，改元黄初，国号魏。据《三国志·魏书·文帝纪》。',
                                 'confidence':1.0,'review_status':'reviewed'}]},
    'zhuge_liang':  {'append': [{'faction_id':'shu','role':'权臣','start_year':221,'end_year':234,
                                 'title':'丞相、武乡侯、益州牧','basis':'章武元年（221）刘备称帝，亮为丞相；建兴十二年（234）卒于五丈原。据《三国志·蜀书·诸葛亮传》。',
                                 'confidence':1.0,'review_status':'reviewed'}]},
    'sim_yi':       {'append': [{'faction_id':'wei','role':'权臣','start_year':239,'end_year':251,
                                 'title':'太傅、丞相（追），专魏政','basis':'正始十年（249）高平陵之变后专魏政；嘉平三年（251）卒。据《晋书·宣帝纪》。',
                                 'confidence':0.95,'review_status':'reviewed'}]},
    'zhu_rong_fu_ren': {'set_role_role': '女眷'},
}


def main(apply=False):
    hits = 0
    for f in sorted(glob.glob(os.path.join(DATA, 'persons_*.json'))):
        doc = json.load(io.open(f, encoding='utf-8'))
        changed = 0
        for p in doc['persons']:
            cfg = PATCH.get(p['id'])
            if not cfg:
                continue
            if 'set_role' in cfg:
                for tn in (p.get('tenure') or []):
                    key = (tn.get('faction_id'), tn.get('start_year'))
                    if key in cfg['set_role']:
                        tn['role'] = cfg['set_role'][key]
                        tn.setdefault('_role_patched', '由「下属数」证据升级')
                        changed += 1
            if 'set_role_role' in cfg:
                for tn in (p.get('tenure') or []):
                    tn['role'] = cfg['set_role_role']; changed += 1
            for seg in cfg.get('append', []):
                exists = any(t.get('faction_id') == seg['faction_id'] and
                             t.get('role') == seg['role'] for t in (p.get('tenure') or []))
                if not exists:
                    p.setdefault('tenure', []).append(dict(seg))
                    changed += 1
            print(f'  {p["name"]}({p["id"]}) 改 {changed} 处 @ {os.path.basename(f)}')
        if changed:
            hits += changed
            if apply:
                json.dump(doc, io.open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'合计 {hits} 处' + ('（已写回）' if apply else '（dry-run，加 --apply 落盘）'))


if __name__ == '__main__':
    main(apply='--apply' in sys.argv)
