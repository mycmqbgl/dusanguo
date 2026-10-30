#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成全量人物水墨全身像的出图清单（build/avatars_manifest.json）

按人物卡的实际字段拼写出图提示词，不用虚构的相貌描写：
  阵营 → 服色基调     身份 → 服饰形制     性别 → 男女装
  再接一小段取自 summary/称号的身份说明，最后统一加风格锚（全身入画、纯纸底）。

分层 tier 决定出图预算与优先级：
  hero   正文提及 >=150 次，或有 "verified" 身份 —— 约 60 人，值得优先出、反复重 roll
  major  提及 >=15 次
  minor  其余（多为自动建档的小人物）

产出同时给出各层的数量与 dashscope 报价估算。
"""
import json, io, os, re, glob, sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
BUILD = os.path.join(ROOT, 'build')
OUT = os.path.join(BUILD, 'avatars_manifest.json')

FAC_CN = {'han':'东汉','warlord':'汉末群雄','wei':'曹魏','wu':'孙吴','shu':'蜀汉',
          'jin':'西晋','barbarian':'南中异族','mystic':'方外'}
# 阵营服色基调：参考 build.py 的 FACTION_META 配色
FAC_TONE = {'han':'赭黄','warlord':'苍灰','wei':'靛青','wu':'黛绿','shu':'朱赤',
            'jin':'紫绛','barbarian':'赭褐','mystic':'墨灰'}
ROBE = {'武将':'身披札甲、腰束革带','文臣':'宽袍大袖、手持笏板','君主':'衮冕华服',
        '皇帝':'十二旒冕服','权臣':'锦袍玉带','亲族':'素锦常服','女眷':'长裙曳地、云鬟高髻',
        '其他':'布衣芒鞋','追谥':'礼服端严','文士':'青衿儒衫'}
GENDER = {'male':'男子','female':'女子'}

STYLE = ('，中国传统水墨画全身立像，单人站立，宣纸底色，淡墨晕染，'
         '笔意疏朗留白；构图居中，人物自头顶至双足完整入画；'
         '背景纯白无纹，无文字无边框无印章')


def build_prompt(p, mentions):
    fac, role, title, tn = 'warlord', '其他', '', {}
    for t in (p.get('tenure') or []):
        # 取最靠前且置信度最高的一段作为主形制
        if not tn or (t.get('confidence') or 0) > (tn.get('confidence') or 0):
            tn = t
    fac = tn.get('faction_id') or 'warlord'
    role = tn.get('role') or '其他'
    title = tn.get('title') or ''
    gender = p.get('gender') or 'male'
    female = gender in ('female', '女', 'F', 'f')

    parts = []
    if female:
        parts.append('青年女子')
        robe = ROBE.get('女眷')
    else:
        parts.append('男子')
        robe = ROBE.get(role, ROBE['其他'])
    tone = FAC_TONE.get(fac, '苍灰')
    desc = f'{FAC_CN.get(fac,"汉末")}{role}，{tone}主调，{robe}'
    if title:
        desc += f'，身份为{title[:12]}'
    # 生平线索：优先 summary，其次 bio 首句，截到 24 字内且回退到最近标点，避免半截词
    s = (p.get('summary') or '').strip()
    if not s or s.startswith('《三国演义》人物'):
        s = re.split(r'[。（]', (p.get('bio') or ''))[0][:24]
    s = re.sub(r'[（(].*?[)）]', '', s)
    if len(s) > 24:
        cut = max(s.rfind(c, 0, 25) for c in '，,；;、')
        s = s[:cut] if cut > 8 else s[:24]
    s = s.strip('，,。；;、')
    if s and not s.startswith(p['name']):
        desc += f'；{s}'
    return desc + STYLE


def main():
    persons = []
    for f in sorted(glob.glob(os.path.join(DATA, 'persons_*.json'))):
        for p in json.load(io.open(f, encoding='utf-8'))['persons']:
            persons.append(p)
    ids = Counter()
    # 提及次数（决定主次）
    for f in sorted(glob.glob(os.path.join(BUILD, 'chapters', 'ch*.json'))):
        d = json.load(io.open(f, encoding='utf-8'))
        for m in d['mentions']:
            if m['entity_type'] == 'person':
                ids[m['entity_id']] += 1

    items = []
    for p in persons:
        pid = p['id']
        cnt = ids.get(pid, 0)
        if cnt >= 150 or (p.get('review_status') == 'verified' and cnt >= 30):
            tier = 'hero'
        elif cnt >= 15:
            tier = 'major'
        else:
            tier = 'minor'
        items.append({'id': pid, 'name': p['name'], 'tier': tier, 'mentions': cnt,
                      'prompt': build_prompt(p, cnt),
                      'out': f'app/assets/avatars/{pid}.png'})
    items.sort(key=lambda x: (-x['mentions'], x['name']))
    json.dump(items, io.open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    c = Counter(x['tier'] for x in items)
    print(f'已写出 {OUT}：{len(items)} 人')
    for k in ('hero', 'major', 'minor'):
        print(f'   {k}: {c[k]} 人')
    print(f'\n按 dashscope wanx2.1-t2i-turbo 0.14 元/张估算：')
    print(f'   仅 hero      {c["hero"]} 张   ≈ {c["hero"]*0.14:.1f} 元')
    print(f'   hero+major  {c["hero"]+c["major"]} 张   ≈ {(c["hero"]+c["major"])*0.14:.1f} 元')
    print(f'   全部 {len(items)} 张   ≈ {len(items)*0.14:.1f} 元（含 1.3 倍重 roll 约 {len(items)*0.14*1.3:.0f} 元）')
    print('\n示例提示词：')
    for x in items[:2] + items[len(items)//2:len(items)//2+1]:
        print(f'   [{x["tier"]}] {x["name"]}: {x["prompt"][:90]}…')


if __name__ == '__main__':
    main()
