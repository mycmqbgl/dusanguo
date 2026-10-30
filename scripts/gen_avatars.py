#!/usr/bin/env python3
"""水墨头像批量流水线：从 build/persons/*.json 生成头像 manifest 与 Prompt。

用法:
  python3 scripts/gen_avatars.py            # 生成 build/avatars_manifest.json + prompts/*.txt
  python3 scripts/gen_avatars.py --list     # 仅统计

产物:
  build/avatars_manifest.json   每人一条: {id, name, tier, faction, mentions, prompt, out}
  build/avatar_prompts/{tier}/{id}.txt   逐人 prompt 文件（供图像生成环境/人工批量执行）

说明:
  - 生成图像本身需要 ImageGen 工具（本沙箱网络受限不可达），需在有该工具的环境执行；
    按 manifest 逐条调用，输出写入 app/assets/avatars/{id}.png（512x512，方图）。
  - 分级 tier: hero(提及>=100) / major(>=20) / minor(<20)，hero 用完整特征 prompt，
    major 用通用模板+身份，minor 用极简通用模板。
  - 前端已集成: .ava 内 <img src="assets/avatars/{id}.png" onerror="this.remove()">，
    缺图自动回落姓氏首字，无需一次性完成。
"""
import json, os, glob, argparse, textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDIR = os.path.join(ROOT, 'build', 'persons')
OUT_MANIFEST = os.path.join(ROOT, 'build', 'avatars_manifest.json')
PROMPT_DIR = os.path.join(ROOT, 'build', 'avatar_prompts')

# 主干人物服饰/特征关键词（提及数最高的一批，按演义描述手写）
HERO_TRAITS = {
    'cao_cao':        '一位威严的中年枭雄，细目长髯，头戴进贤冠，身着暗红锦袍，腰悬长剑',
    'liu_be':         '一位仁厚的长者，双手过膝，双耳垂肩，面如冠玉，头戴纶巾，身着素色广袖长袍',
    'sun_quan':       '一位碧眼紫髯的英主，方颐大口，头戴冕冠，身着紫金朝服',
    'zhugeliang':     '一位羽扇纶巾的青年谋士，身披鹤氅，面如冠玉，眉宇清朗，手持白羽扇',
    'guan_yu':        '一位身长九尺的美髯公，面如重枣，丹凤眼卧蚕眉，绿锦战袍，手提青龙偃月刀',
    'zhang_fei':      '一位豹头环眼的黑面猛将，燕颔虎须，声若巨雷，身着皂色战袍，手持丈八蛇矛',
    'zhao_yun':       '一位白马银枪的俊朗少年将军，白袍银甲，姿颜雄伟，怀有凛然之气',
    'zhou_yu':        '一位风流倜傥的江东儒将，姿质风流，头戴纶巾，身着青衫，腰佩长剑',
    'sim_yi':         '一位深沉多谋的老者，鹰视狼顾，须发花白，身着黑紫官袍',
    'lv_bu':          '一位顶束金冠的盖世猛将，面白无须，身着兽面吞头连环铠，手持方天画戟，身姿雄伟',
    'diao_chan':      '一位倾国倾城的舞姬，眉黛春山，云鬓花颜，身着红罗宫装，身姿婀娜',
    'sun_ce':         '一位英气勃发的少年霸主，面如冠玉，浓眉朗目，身着赤色战袍，手持长枪',
    'ma_chao':        '一位面如冠玉的白袍猛将，狮盔兽带，银甲白袍，目似朗星，手持长枪',
    'huang_zhong':    '一位须发皆白的老将，宝刀未老，挽强弓着铁甲，精神矍铄',
    'dian_wei':       '一位古之恶来般的魁伟壮士，虎背熊腰，浓眉阔面，手提双铁戟',
    'xu_chu':         '一位虎痴般的赤膊壮汉，身长八尺，腰大十围，袒胸露腹，状貌雄毅',
    'jiang_wei':      '一位英姿飒爽的青年将军，面如重枣，浓眉凤目，身着绿甲持枪',
    'lu_su':          '一位忠厚的江东谋臣，体貌魁奇，头戴帻巾，身着深青长袍',
    'dong_zhuo':      '一位臃肿暴戾的权相，面阔体胖，绀揆虬髯，身着华丽锦袍，神情骄横',
    'liu_xie':        '一位清瘦忧思的少年天子，头戴冕旒，身着玄色衮服，神情恭谨含悲',
}

BASE = ('中国传统水墨画风格全身立像，单人，宣纸底色，淡墨晕染，'
        '笔意疏朗留白，三国时期{identity}，{traits}。'
        '全身像构图居中，人物完整入画，背景纯宣纸白，无文字无边框。')
MINOR = ('中国传统水墨画风格全身立像，单人，宣纸底色，淡墨晕染，'
         '三国时期{identity}，貌不出众，衣饰从简。全身居中，背景纯白，无文字。')

ROLE_WORD = {'武将': '武将', '谋士': '谋士', '文官': '文官', '君主': '诸侯君主',
             '皇帝': '帝王', '后妃': '女子', '宗室': '宗室贵族'}


def tier_of(m):
    return 'hero' if m >= 100 else ('major' if m >= 20 else 'minor')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--list', action='store_true')
    args = ap.parse_args()

    persons = []
    for f in sorted(glob.glob(os.path.join(PDIR, '*.json'))):
        p = json.load(open(f))
        role = ''
        if p.get('tenure'):
            role = p['tenure'][0].get('role', '')
        mentions = p.get('mention_count', 0)
        persons.append({'id': p['id'], 'name': p['name'], 'gender': p.get('gender'),
                        'role': role, 'mentions': mentions, 'tier': tier_of(mentions),
                        'summary': p.get('summary') or ''})
    persons.sort(key=lambda x: -x['mentions'])

    os.makedirs(PROMPT_DIR, exist_ok=True)
    manifest = []
    for p in persons:
        ident = ROLE_WORD.get(p['role'], '人物')
        if p['gender'] == 'female':
            ident = '女子'
        if p['tier'] == 'hero':
            traits = HERO_TRAITS.get(p['id'], f'气度不凡的{ident}，{p["summary"][:30]}')
            prompt = BASE.format(identity=ident, traits=traits)
        else:
            prompt = MINOR.format(identity=ident)
        manifest.append({'id': p['id'], 'name': p['name'], 'tier': p['tier'],
                         'mentions': p['mentions'], 'prompt': prompt,
                         'out': f'app/assets/avatars/{p["id"]}.png'})
        fp = os.path.join(PROMPT_DIR, p['tier'], f'{p["id"]}.txt')
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        with open(fp, 'w') as fh:
            fh.write(prompt + '\n')

    json.dump(manifest, open(OUT_MANIFEST, 'w'), ensure_ascii=False, indent=1)
    from collections import Counter
    c = Counter(p['tier'] for p in manifest)
    if args.list or True:
        print(f'共 {len(manifest)} 人: hero={c["hero"]} major={c["major"]} minor={c["minor"]}')
        print(f'manifest -> {OUT_MANIFEST}')
        print(f'prompts  -> {PROMPT_DIR}/{{hero,major,minor}}/{{id}}.txt')


if __name__ == '__main__':
    main()
