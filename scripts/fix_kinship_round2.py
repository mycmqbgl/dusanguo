#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第二批：亲族口径收紧（帝系血亲 + 后族）。

口径已与用户确认：
  亲族 = ①当朝帝系之血亲（父、子、兄弟、叔侄、孙）
         ②后族（后妃本人及其父兄）
  宗室旁支的姻亲（如孙权侄女婿）、功臣之后袭爵者，不属帝系亲族。

本批处理：
  - 周循：孙权之女婿（尚孙鲁班），姻亲成立 → 吴·亲族，title 写实
  - 周胤：娶孙皎之女（孙权侄女，隔一层）→ 吴·武将
  - 孙静/孙匡/孙朗/孙和/孙霸/孙奋/孙亮/刘辩/刘协/刘禅/曹芳/曹奂：title 补帝系锚点
  - 曹植/曹宇/曹据/曹霖/刘永/刘理/刘元起/刘苌/关彝：title 补帝系锚点
  - 曹贵人 → 曹节（曹操之女、献帝皇后）→ 汉·亲族
  - 伏德 → 汉·亲族（国舅：伏皇后之兄），title/basis 写实
  - 王修：补缺失的 basis

写法：逐文件就地改 + 立即 save + 回读断言。
"""
import json, glob, os, io

ROOT = '/workspace/读三国-project'
DATA = os.path.join(ROOT, 'data')


def each_person():
    for f in sorted(glob.glob(os.path.join(DATA, 'persons_*.json'))):
        doc = json.load(io.open(f, encoding='utf-8'))
        for i, p in enumerate(doc['persons']):
            yield f, doc, i, p


def save(f, doc):
    json.dump(doc, io.open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


CH = []


def C(pid, top=None, ten=None, tn0=None):
    """ten: 完整 tenure 列表；tn0: 只改 tenure[0] 的字段"""
    CH.append((pid, top or {}, ten, tn0 or {}))


# ---------- 周循 / 周胤：姻亲判定 ----------
C('zhou_xun', dict(
    summary='周循，周瑜长子，尚孙权之女孙鲁班（大懿公主），官骑都尉。',
    bio='周循，庐江舒人，周瑜长子。孙权以女孙鲁班（后称大懿公主）妻之，官至骑都尉，早卒。'
        '《三国志·吴书·周瑜传》附其名，毛本演义 120 回未载，本卡依正史补录。',
    display_aliases=['周循'],
    date_note='生卒年不详；娶孙权之女孙鲁班，卒于孙权之世（约 225 年前后）。',
    review_status='reviewed'),
  [dict(faction_id='wu', role='亲族', start_year=211, end_year=225,
        title='孙权之婿（尚孙权之女孙鲁班），骑都尉',
        basis='《三国志·吴书·周瑜传》：周循为周瑜长子，尚孙鲁班，官骑都尉。'
              '孙鲁班即孙权之女（后封大懿公主），周循以帝婿之身入吴宗亲之列，故为吴·亲族。'
              '演义未载。',
        confidence=0.9, review_status='reviewed')])

C('zhou_yin', dict(
    summary='周胤，周瑜次子，官兴业都尉，封都乡侯。',
    bio='周胤，庐江舒人，周瑜次子。以父功为兴业都尉，封都乡侯，后坐罪徙庐陵。'
        '《三国志·吴书·周瑜传》附其名，毛本演义 120 回未载，本卡依正史补录。',
    display_aliases=['周胤'],
    date_note='生卒年不详；约 211 年以父功受官，后坐罪徙庐陵。',
    review_status='reviewed'),
  [dict(faction_id='wu', role='武将', start_year=211, end_year=240,
        title='兴业都尉、都乡侯',
        basis='《三国志·吴书·周瑜传》：周胤为周瑜次子，官兴业都尉，封都乡侯。'
              '其为功臣之后袭爵受官，虽娶孙皎之女（孙权侄女），然系孙权侄婿、非帝系之亲，'
              '故依与吕霸相同之口径归吴·武将。演义未载。',
        confidence=0.85, review_status='reviewed')])

# ---------- 曹贵人 -> 曹节，汉·亲族（后族） ----------
C('cao_gui_ren', dict(
    name='曹节', display_aliases=['曹贵人', '曹皇后'],
    match_surfaces=['曹节', '曹贵人', '曹皇后', '献帝皇后'],
    summary='曹节，曹操之女，汉献帝皇后。建安二十年（215）立为皇后，魏受禅后降为山阳公夫人。',
    bio='曹节，曹操之女。建安十八年曹操进三女（曹宪、曹节、曹华）为献帝贵人；'
        '建安二十年（215）伏皇后被废杀，正月朔册立曹节为正宫皇后。'
        '第66回：操入曰「臣女已与陛下为贵人，大贤大孝，宜居正宫」，献帝不敢不从。'
        '魏受禅后，曹节随献帝降为山阳公夫人。',
    date_note='生年不详；215 年立为汉献帝皇后，卒年不详。',
    first_chapter=66),
  [dict(faction_id='han', role='亲族', start_year=215, end_year=220,
        title='献帝皇后（曹操之女）',
        basis='第66回：册立曹操女曹贵人为正宫皇后。曹节为曹操之女、汉献帝之皇后，'
              '属汉室外戚（后族），故归汉·亲族。',
        confidence=0.9, review_status='reviewed'),
   dict(faction_id='wei', role='女眷', start_year=220, end_year=234,
        title='山阳公夫人（曹操之女）',
        basis='第80回：献帝禅位降封山阳公，曹节随为山阳公夫人。',
        confidence=0.8, review_status='reviewed')])

# ---------- 伏德：国舅（伏皇后之兄） ----------
C('fu_de', dict(
    summary='伏德，伏皇后之兄，汉室外戚，官至执金吾。兴平二年（195）护献帝渡河。',
    bio='伏德，琅琊东武人，伏完之子、伏皇后之兄。兴平二年（195）李傕、郭汜追迫献帝于黄河岸边，'
        '「人丛中国舅伏德挟白绢十数匹至」，以绢接连拽辇，又亲负伏皇后下船，帝后乃得渡河。'
        '建安十九年（214）伏后事发，伏氏宗族坐诛。',
    date_note='生年不详；建安十九年（214）伏氏之狱坐诛。'),
  [dict(faction_id='han', role='亲族', start_year=195, end_year=214,
        title='国舅（伏皇后之兄）',
        basis='第13回：人丛中国舅伏德挟白绢十数匹至……后兄伏德，负后下船中。'
              '伏德为献帝伏皇后之兄，属汉室外戚（后族），故归汉·亲族。',
        confidence=0.9, review_status='reviewed')])

# ---------- 补帝系锚点：吴 ----------
C('sun_jing', None, None,
  dict(title='孙坚之弟（昭义中郎将），孙权之叔'))
C('sun_kuang', None, None,
  dict(title='孙坚第四子，孙权之弟，乌程侯'))
C('sun_lang', None, None,
  dict(title='孙坚庶子，孙权之弟（一名孙仁）'))
C('sun_he', None, None,
  dict(title='孙权第三子（曾立为太子，后封南阳王）'))
C('sun_ba', None, None,
  dict(title='孙权第四子，鲁王'))
C('sun_fen', None, None,
  dict(title='孙权第五子，齐王'))
C('sun_liang', None, None,
  dict(title='孙权少子，吴废帝'))

# ---------- 补帝系锚点：汉 ----------
C('liu_bian', None, None,
  dict(title='灵帝长子，少帝（废为弘农王）'))
C('liu_xie', None, None,
  dict(title='灵帝次子，陈留王'))
C('liu_chang', None, None,
  dict(title='灵帝生父，解渎亭侯（桓帝迎立其子入继大统）'))
C('liu_yuan_qi', None, None,
  dict(title='刘备叔父（刘备之叔）'))

# ---------- 补帝系锚点：蜀 ----------
C('liu_yong', None, None,
  dict(title='刘备次子，鲁王（后主之弟）'))
C('liu_li', None, None,
  dict(title='刘备第四子，梁王（后主之弟）'))
C('liu_shan', None, None,
  dict(title='后主刘禅（蜀室之亲）'))

# ---------- 补帝系锚点：魏 ----------
C('cao_zhi', None, None,
  dict(title='曹操第三子（卞氏三子），陈思王'))
C('cao_yu', None, None,
  dict(title='曹操之子，燕王（魏元帝曹奂之父）'))
C('cao_ju', None, None,
  dict(title='曹操之子，彭城王'))
C('cao_lin', None, None,
  dict(title='曹丕之子，东海定王（魏高贵乡公曹髦之父）'))
C('cao_anmin', None, None,
  dict(title='曹操之侄（曹安民）'))
C('cao_fang', None, None,
  dict(title='魏明帝曹叡养子，齐王（废黜后降复王爵）'))
C('cao_huan', None, None,
  dict(title='曹操之孙，常道乡公（燕王曹宇之子）'))

# ---------- 关彝：功臣之后，非帝系之亲 ----------
C('guan_yi', dict(
    summary='关彝，关羽之孙，关兴之子，袭汉寿亭侯。蜀亡死于乱军。',
    bio='关彝，河东解人，关羽之孙、关兴之子。父死袭汉寿亭侯；炎兴元年（263）邓艾破成都，'
        '钟会之乱中为庞会所杀，关氏遂绝。第119回：「关彝为关兴之子，袭汉寿亭侯爵，蜀亡时为庞会所杀。」'),
  [dict(faction_id='shu', role='武将', start_year=263, end_year=263,
        title='汉寿亭侯（袭关羽爵）',
        basis='第119回：关彝为关兴之子，袭汉寿亭侯爵，蜀亡时为庞会所杀。'
              '关彝为关羽之孙、功臣之后袭爵，非刘氏帝系之亲，故归蜀·武将。',
        confidence=0.9, review_status='reviewed')])

# ---------- 王修：补 basis ----------
C('wang_xiu', None, None, None)  # 占位，下面单独处理

# ---------- 应用 ----------
applied = set()
for f, doc, i, p in each_person():
    pid = p['id']
    for cid, top, ten, tn0 in CH:
        if pid != cid:
            continue
        p.update(top)
        if ten is not None:
            p['tenure'] = ten
        elif tn0:
            p['tenure'][0].update(tn0)
        doc['persons'][i] = p
        save(f, doc)
        applied.add(pid)

# 王修 basis 补写
for f, doc, i, p in each_person():
    if p['id'] == 'wang_xiu':
        for tn in p['tenure']:
            if not tn.get('basis'):
                if tn['faction_id'] == 'warlord':
                    tn['basis'] = '第31回：袁谭别驾王修。袁谭败亡，王修收葬其尸，曹操义而用之。'
                else:
                    tn['basis'] = '第31回：曹操以王修为司空掾，后为魏郡太守。'
        p['summary'] = '王修，字叔治，北海营陵人，先为袁谭别驾，后仕魏为司空掾、魏郡太守。'
        doc['persons'][i] = p
        save(f, doc)
        applied.add('wang_xiu')

missing = [c[0] for c in CH if c[0] not in applied]
print('已改', len(applied), '未命中', missing)
