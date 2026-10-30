#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把自动建档卡的任期结束年收回到「末见回目」对应的年份。

## 问题

`expand_persons.py` 的 `clamp_tenure()` 是这样定任期的：

    lo, hi = FAC_BOUND[fac]        # 势力年份上下界
    y      = CH_YEAR[first_ch]     # 首见回目 → 年
    s      = max(lo, min(y, hi))
    e      = hi if hi >= s else s  # ← 结束年 = 势力上限，与本人无关

于是「结束年」从来不是这个人何时退场，而是他所属势力撑到哪一年。左丰只在
第 1 回（184 年）索贿卢植、全书出现 2 次，却因为阵营被判成 barbarian（上限
280）而在人物页 184—280 的每一年都在任——点开任何年份都能看见他。

全书 368 片任期吃满势力上限且末见年更早，其中 310 片属自动建档。

## 修法

以「该人物在正文里最后一次被锚点命中的回目」换算年份，作为任期结束年。
这比势力上限可靠得多：孙登末见第 108 回 = 241 年，正是他的史实卒年。

### 两条必须遵守的排除

1. **只动 `review_status == 'auto'` 的片**。人工核过的（reviewed / verified）
   不动——他们多半有史实卒年依据，不是 clamp 出来的。
2. **跳过「追谥」**。曹嵩 wei/追谥 220—266，末见第 11 回（194 年阵亡），
   但 220 年曹丕称帝后追尊他为太皇帝——这个区间是对的，套末见年会毁掉它。

### 偏差方向

末见年以**低估**为主（顾雍末见 229 / 史实卒 243，薛综末见 208 / 史实卒 243），
因为「演义里戏份结束」早于「史实寿命」。这对「在任时间片」这个语义是正确
甚至更好的估计；反过来高估只发生在身后被人追述的情况（如陆逊末见第 119 回
= 264，史实卒 245），那是安全方向。

用法：
    python3 scripts/fix_tenure_span.py          # 预演，只打印
    python3 scripts/fix_tenure_span.py --fix    # 写入 data/persons*.json
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
BUILD = os.path.join(ROOT, 'build')

sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from chron_const import CH_YEAR  # noqa: E402

# 追谥是身后追尊，任期天然晚于末见年，不能按末见年收
EXEMPT_ROLE = {'追谥'}

# ── B 类的真正病因：阵营判错 ────────────────────────────────────────────────
# 有 7 片的起始年就被势力下限抬到了末见年之后（如区星 wu 195 起、末见却在
# 第 2 回=184）。光把任期拉回末见年会越出新阵营的年份区间——这说明**阵营
# 一开始就判错了**，它们本不该归属那个势力。逐条按正文原文改判，证据如下。
# 元组 = (阵营, 角色, 阵营中文词, 角色中文词, 正文依据)
# 阵营中文词须与 audit_persons.py 的 FAC_WORD 对齐，否则简介会与任期打架。
REFACE = {
    # 第 2 回：「长沙贼区星作乱」——贼寇，非吴
    'qu_xing':   ('barbarian', '武将', '异族', '武将',
                  '第 2 回原文「长沙贼区星作乱」，系贼寇，非孙氏部属。'),
    # 第 2 回：「黄巾余党三人：赵弘、韩忠、孙仲」
    'sun_zhong': ('barbarian', '武将', '异族', '武将',
                  '第 2 回原文「黄巾余党三人：赵弘、韩忠、孙仲」，黄巾余党，非吴。'),
    # 第 2 回：许昌之子，「坚…斩许昌并其子许韶」
    'xu_shao_2': ('barbarian', '武将', '异族', '武将',
                  '第 2 回原文「斩许昌并其子许韶」，会稽妖贼许昌之子，非吴。'),
    # 第 37 回：孔明密友，「此四人务于精纯」——荆襄名士，从未仕蜀。
    #   与边让、蔡邕同例归东汉，不归「神怪」（那是左慈、紫虚上人一路）。
    'zhou_ping': ('han', '其他', '东汉', '人物',
                  '第 37 回原文「孔明与博陵崔州平…此四人务于精纯」，荆襄名士，未仕蜀汉。'),
    # 第 37 回：「乃家兄岳父黄承彦也」——沔南名士
    'cheng_yan': ('han', '其他', '东汉', '人物',
                  '第 37 回原文「此非卧龙家兄，乃家兄岳父黄承彦也」，沔南名士，未仕蜀汉。'),
    # 第 23 回：董承侍妾；董承为汉献帝国舅，属汉廷
    'yun_ying':  ('han', '女眷', '东汉', '女眷',
                  '第 23 回原文「家奴秦庆童同侍妾云英在暗处私语」，董承府侍妾，属汉廷。'),
    # ── 2026-10 补：职任段自相矛盾者 ─────────────────────────────────────
    # 上表 6 条是靠「任期越出阵营边界」暴露的；下面 5 条的任期本身合法，
    # 但简介的职任段与阵营标签打架（如「曹魏文臣，吴大司马」），病因相同：
    # 阵营来自抓取源注记，而注记本身写错了，`infer_from_note` 照抄。
    # 第 1 回：「左丰挟恨，回奏朝廷」——黄门，十常侍同党，汉廷宦官
    'zuo_feng':  ('han', '文臣', '东汉', '文臣',
                  '第 1 回原文「左丰挟恨，回奏朝廷，说我高垒不战」，职任黄门，'
                  '与十常侍同党，属汉廷宦官，非异族。'),
    # 第 108 回：「太傅诸葛恪、大司马吕岱至榻前，嘱以后事」——吴大司马
    'lv_dai':    ('wu', '武将', '孙吴', '武将',
                  '第 108 回原文「太傅诸葛恪、大司马吕岱至榻前，嘱以后事」，'
                  '吴大司马，非曹魏。原判魏系裸词「司马」误配官职名。'),
    # 第 108 回：「魏光禄大夫张缉」；第 109 回：「缉乃张皇后之父，曹芳之皇丈」
    'zhang_ji_3': ('wei', '文臣', '曹魏', '文臣',
                   '第 108 回原文「魏光禄大夫张缉」，第 109 回「缉乃张皇后之父，'
                   '曹芳之皇丈也」，魏臣，非孙吴。'),
    # 第 109 回：「扬州刺史文钦」；第 110 回：「钦乃曹爽门下客」——起兵时为魏臣
    'wen_qin':   ('wei', '武将', '曹魏', '武将',
                  '第 109 回原文「扬州刺史文钦，以废主为名，起兵前来」，第 110 回'
                  '「钦乃曹爽门下客」，起兵时为魏臣（后降吴，见第 111 回）。'),
    # 第 116 回：「监军卫瓘，护军胡烈」——钟会伐蜀时的魏军护军
    'hu_lie':    ('wei', '武将', '曹魏', '武将',
                  '第 116 回原文「时有监军卫瓘，护军胡烈，大将田续、庞会…」，'
                  '钟会伐蜀时的魏军护军，非蜀将。'),
    # ── 2026-10 补：按「职任段首字」扫出的阵营错判 ───────────────────────
    # 判据：简介职任段以「吴/魏/蜀/汉/晋」开头（形如「魏司徒」「吴大司马」），
    # 该政权却不在本人的 tenure.faction_id 里。这批任期本身合法，错的只是归属。
    # 第 105 回：「司徒董寻上表切谏」——魏明帝曹睿的司徒
    'dong_xun':  ('wei', '文臣', '曹魏', '文臣',
                  '第 105 回原文「司徒董寻上表切谏曰…睿览表怒曰」，魏明帝曹睿的司徒，'
                  '非汉廷（汉已亡于 220 年）。'),
    # 第 113 回：「艾视之，乃襄阳党均也」——邓艾军中使者
    'dang_jun':  ('wei', '文臣', '曹魏', '文臣',
                  '第 113 回原文「一人应声曰：某愿往。艾视之，乃襄阳党均也。艾大喜，'
                  '即令党均赍金珠宝物，径到成都结连黄皓」，邓艾部属，非异族。'),
    # 第 107 回：「令司徒高柔，假以节钺行大将军事」
    'gao_rou':   ('wei', '文臣', '曹魏', '文臣',
                  '第 107 回原文「令司徒高柔，假以节钺行大将军事，先据曹爽营」，'
                  '司马懿政变时的魏司徒，非汉廷。'),
    # 第 120 回：「吴主皓大慌，急召丞相张悌、司徒何植、司空滕循」
    'he_zhi':    ('wu', '文臣', '孙吴', '文臣',
                  '第 120 回原文「吴主皓大慌，急召丞相张悌、司徒何植、司空滕循，'
                  '计议退兵之策」，东吴司徒，非汉廷。'),
    # 第 96 回：「贾逵引前将军满宠、东莞太守胡质，径取阳城」
    'hu_zhi':    ('wei', '武将', '曹魏', '武将',
                  '第 96 回原文「贾逵引前将军满宠、东莞太守胡质，径取阳城」，'
                  '魏军一路主将，非蜀将。'),
    # 第 120 回：「中书令胡冲、光禄勋薛莹奏曰：陛下何不效安乐公刘禅乎」
    'hu_chong':  ('wu', '文臣', '孙吴', '文臣',
                  '第 120 回原文「中书令胡冲、光禄勋薛莹奏曰」，晋军入石头城时的'
                  '东吴中书令，非群雄。'),
    # 第 116 回：「惟有相国参军刘寔，微笑不语」——司马昭相国府参军
    'liu_shi_2': ('wei', '文臣', '曹魏', '文臣',
                  '第 116 回原文「惟有相国参军刘寔，微笑不语。太尉王祥见寔冷笑」，'
                  '魏相国（司马昭）府参军，非蜀汉。'),
    # 第 92 回：「天水太守马遵，安定太守崔谅」
    'ma_zun':    ('wei', '武将', '曹魏', '武将',
                  '第 92 回原文「天水太守马遵，安定太守崔谅」，诸葛亮北伐时的'
                  '魏天水太守，非蜀汉。'),
    # 第 80 回：「令博士许慈、谏议郎孟光掌礼」；第 91 回：「孟光、来敏为祭酒」
    'meng_guang': ('shu', '文臣', '蜀汉', '文臣',
                   '第 80 回原文「令博士许慈、谏议郎孟光掌礼，筑坛于成都武担之南」，'
                   '蜀汉谏议郎，非异族。'),
    # 第 107 回：「又令太仆王观行中领军事，据曹羲营」
    'wang_guan': ('wei', '文臣', '曹魏', '文臣',
                  '第 107 回原文「又令太仆王观行中领军事，据曹羲营」，'
                  '司马懿政变时的魏太仆，非孙吴。'),
    # 第 116 回：「太尉王祥见寔冷笑」；第 119 回：「太尉王祥、司空荀顗谏曰」
    'wang_xiang': ('wei', '文臣', '曹魏', '文臣',
                   '第 116 回原文「太尉王祥见寔冷笑，就马上握其手而问曰」，'
                   '魏太尉（后入晋），非汉廷。'),
    # 第 111 回：「令长史吴纲，送子诸葛靓入吴为质求援」——诸葛诞的长史
    'wu_gang':   ('wei', '文臣', '曹魏', '文臣',
                  '第 111 回原文「又令长史吴纲，送子诸葛靓入吴为质求援」，'
                  '魏将诸葛诞的长史，入吴是求援而非吴臣。'),
    # 第 115 回：「时右将军阎宇，身无寸功，只因阿附黄皓，遂得重爵」
    'yan_yu_2':  ('shu', '武将', '蜀汉', '武将',
                  '第 115 回原文「时右将军阎宇，身无寸功，只因阿附黄皓，遂得重爵」，'
                  '蜀汉右将军，非群雄。'),
}

# 职任段（简介里第二个逗号之后、第一个句号之前）需要一并订正的，否则会出现
# 「曹魏武将，魏将」这类同义重复，或残留「之父」这种提取时丢字的残句。
DUTY_FIX = {
    'hu_lie': '护军',
    'wen_qin': '魏扬州刺史，曹爽门下客，后降吴',
    'zhang_ji_3': '魏光禄大夫，张皇后之父，曹芳之皇丈',
}

# 简介/生平开头的阵营词（须与 audit_persons.py 的 FAC_WORD 一致）
FAC_WORD = ('曹魏', '孙吴', '蜀汉', '东汉', '西晋', '群雄', '南蛮', '异族', '神怪')
ROLE_WORD = ('君主', '追谥', '权臣', '亲族', '文臣', '武将', '女眷', '人物', '其他')
HEAD_TAG = re.compile(r'^([\u4e00-\u9fa5]{1,8}[，,]\s*)(' + '|'.join(FAC_WORD) + r')('
                      + '|'.join(ROLE_WORD) + r')')

# ★ 幂等：basis 是「追加式」拼装的，同一段说明重复追加两次会变成
#   「…非本人退场之年。；★任期按末见回目收敛：…非本人退场之年。」
#   落盘前先剥掉旧的那段，保证脚本跑多少遍结果都一样。
TEN_NOTE_RE = re.compile(r'；?\s*★任期按末见回目收敛：[^；]*?非本人退场之年。')
REFACE_NOTE_RE = re.compile(r'；?\s*★阵营改判：[^；]*')

# 简介职任段：第二个逗号之后到第一个句号之前（「名，阵营身份，职任。」）
DUTY_RE = re.compile(r'^([^，]+，[^，]+，)([^。]*)(。)')


def clean_ten(b):
    """只剥掉「任职收敛」那段说明。"""
    return TEN_NOTE_RE.sub('', b or '').rstrip('；')


def clean_basis(b):
    """剥掉本脚本追加过的两段说明，回到「原始依据」状态。"""
    return REFACE_NOTE_RE.sub('', clean_ten(b)).rstrip('；')


def last_seen_map():
    """pid -> 末见回目（正文锚点里最后一次出现的章）"""
    last = {}
    for f in sorted(glob.glob(os.path.join(BUILD, 'chapters', '*.json'))):
        no = int(re.search(r'ch(\d+)', os.path.basename(f)).group(1))
        d = json.load(open(f, encoding='utf-8'))
        for m in (d.get('mentions') or []):
            if m.get('entity_type') != 'person':
                continue
            pid = m.get('entity_id')
            if pid and no > last.get(pid, 0):
                last[pid] = no
    return last


def main(apply):
    last = last_seen_map()
    files = {}
    for f in sorted(glob.glob(os.path.join(DATA, 'persons*.json'))):
        files[f] = json.load(open(f, encoding='utf-8'))

    changed, skipped, reface = [], [], []
    for f, d in files.items():
        lst = d if isinstance(d, list) else (d.get('persons') or d.get('items') or [])
        for p in lst:
            if not isinstance(p, dict) or not p.get('id'):
                continue
            lc = last.get(p['id'])
            ly = CH_YEAR.get(lc) if lc else None
            if ly is None:
                continue                      # 正文无锚点，无从判断
            for t in (p.get('tenure') or []):
                s, e = t.get('start_year'), t.get('end_year')
                if s is None or e is None:
                    continue
                # 先改判阵营（B 类的病根），再按末见年收任期
                rf = REFACE.get(p['id'])
                if rf:
                    if t.get('faction_id') != rf[0]:
                        t['basis'] = clean_basis(t.get('basis')) + '；★阵营改判：' + rf[4]
                        t['faction_id'], t['role'] = rf[0], rf[1]
                        reface.append((p['name'], rf[0], rf[1], rf[2] + rf[3]))
                    # 简介/生平开头的「阵营+身份」标签是生成时写死的，不同步就会与
                    # 任期打架。幂等：无论阵营本轮是否变化都对齐一次。
                    duty = DUTY_FIX.get(p['id'])
                    for key in ('summary', 'bio'):
                        v = p.get(key) or ''
                        m = HEAD_TAG.match(v)
                        if m and (m.group(2), m.group(3)) != (rf[2], rf[3]):
                            v = v[:m.start(2)] + rf[2] + rf[3] + v[m.end(3):]
                        if duty:
                            # 职任段一并订正：否则会出现「曹魏武将，魏将」这种
                            # 同义重复，或残留提取时丢字的「之父」残句。
                            dm = DUTY_RE.match(v)
                            if dm and dm.group(2) != duty:
                                v = dm.group(1) + duty + dm.group(3) + v[dm.end():]
                        p[key] = v
                if t.get('review_status') != 'auto':
                    skipped.append((p['name'], '非 auto（人工已核）'))
                    continue
                if t.get('role') in EXEMPT_ROLE:
                    skipped.append((p['name'], '追谥（身后追尊）'))
                    continue
                if e <= ly:
                    continue                  # 已在末见年内，无需改
                # A 类：起点正常，只收终点
                # B 类：整段都在末见年之后（起点被势力下限 clamp 抬高了），连起点一起拉回
                ns = s if s <= ly else ly
                ne = max(ns, ly)
                note = ('★任期按末见回目收敛：全书最后一次提及在第 %d 回（%d 年），'
                        '原 %d—%d 系取势力年份上限，非本人退场之年。' % (lc, ly, s, e))
                t['basis'] = clean_ten(t.get('basis')) + '；' + note
                changed.append((p['name'], t.get('faction_id'), t.get('role'),
                                s, e, ns, ne, lc, ly, 'B' if s > ly else 'A'))
                t['start_year'], t['end_year'] = ns, ne

    if reface:
        print('%s：%d 片阵营改判' % ('已改' if apply else '预演', len(reface)))
        for nm, fac, role, tag in reface:
            print('    %-6s → %s/%s  简介改「%s」' % (nm, fac, role, tag))
        print()
    print('%s：%d 片任期收敛到末见年' % ('已改' if apply else '预演', len(changed)))
    kinds = {}
    for c in changed:
        kinds[c[9]] = kinds.get(c[9], 0) + 1
    print('  A 类（只收终点）%d 片 / B 类（连起点一起拉回）%d 片' % (kinds.get('A', 0), kinds.get('B', 0)))
    print()
    print('  超出最多的 20 片：')
    for c in sorted(changed, key=lambda c: -(c[4] - c[8]))[:20]:
        print('    %-6s %-9s %-3s %4d—%4d → %4d—%4d  末见第%-4d回=%d年' %
              (c[0], c[1], c[2], c[3], c[4], c[5], c[6], c[7], c[8]))
    if not apply:
        print()
        print('（预演模式，未写入。加 --fix 落盘）')
        return

    for f, d in files.items():
        json.dump(d, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print()
    print('已写入 data/persons*.json，需重跑 scripts/build.py 重建 build/persons/')


if __name__ == '__main__':
    main('--fix' in sys.argv)
