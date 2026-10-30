#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
覆盖率评估：估算「原文中应链的人名，实际链上了多少」

思路：演义里人物最稳定的信号是「单称/名 + 曰」，即 X曰、X怒、X大喜。
对每个这样的位置检查是否已被 mention 覆盖；未被覆盖的按频次排序，
人工判为真名的计入「漏网」，其余记为「噪声」。

用法：python scripts/eval_coverage.py [--show 30]
"""
import json, io, os, re, argparse, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, 'build')

# 只取「X 曰」这一种最干净的信号：X 直接接「曰」，不夹动词，
# 否则「大呼曰」会被切成人名「大呼」、「允怒曰」被切成「允怒」。
# 末字若是动词性字，说明切错了——「允怒」剥成「允」重判（--no-merge 恢复旧丢弃行为）。
# 2026-10-27 实测补「叹泣哭告」：操叹曰/泣曰/哭曰/告曰 与 曰 同频，缺了会把
# 「操叹」整词当候选、把「允哭」这类可剥位置直接丢掉。
BAD_TAIL = set('呼怒惊喜叱笑问答谓进出来去走马兵刀枪弓箭杀斩击攻守拜谢命叹泣哭告喝奏对叫忖思按之大之')

# 明显不是人名的词（虚词、副词、连词、跨词切分产物）
NOT_NAME = set('''
方今 何必 何言 何反 何私 任我 余战 贺毕 曾拜 刘名 尹放 马只 马便 马直 马径 马来
侯各 侯并 夏张 史韩 董太 于吾 于帝 雷大 王寻 丞相 太师 主公 将军 使者 众将 二人
此人 何人 有人 吾等 汝等 我等 彼等 一时 于是 因此 然后 今闻 若此 如此 何故 何以
大 乃 再 名 号 妻 吏 老人 其人 其略 书略 众皆 厉声 大叫 再拜 忽人报 仰天 厉声问
县令 壮士 左右 太后 督邮 其文 其歌 诗 我 且 而公 乃大 共议 宣谕 对众 回报 庄主 众官皆 卓按剑 忽报 匡大
常 或 侍妾 自 责 乃厉声 布对卓 自忖 良久 貂蝉大惊 歌 众官 诸将 士卒 军士 百姓 将校
'''.split())

PAT = '(?:^|[，。！？"」』；：、\\s（(])([\\u4e00-\\u9fa5]{1,3})曰'
RE = re.compile(PAT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--show', type=int, default=25)
    ap.add_argument('--no-merge', dest='merge_tail', action='store_false',
                    help='关闭末字动词后向合并（恢复旧行为：BAD_TAIL 位置直接丢弃）')
    args = ap.parse_args()

    chapter_files = sorted(f for f in os.listdir(os.path.join(BUILD, 'chapters')) if f.endswith('.json'))

    # 已链接的人名位置：{(ch, passage_id): [(start, end), ...]}
    covered = collections.defaultdict(list)
    for f in chapter_files:
        d = json.load(io.open(os.path.join(BUILD, 'chapters', f), encoding='utf-8'))
        no = d['chapter']['no']
        for m in d['mentions']:
            if m['entity_type'] == 'person':
                covered[(no, m['passage_id'])].append((m['start'], m['end']))

    # 注意：build/index.json 是 P0 单回时代的遗留文件，跨回汇总已改由 book.json 承载。
    # 读错文件会让「人物锚点」永远停在 199，与真实值差一个数量级。
    book = json.load(io.open(os.path.join(BUILD, 'book.json'), encoding='utf-8'))
    DATA = os.path.join(ROOT, 'data')
    cards = sum(len(json.load(io.open(os.path.join(DATA, f), encoding='utf-8'))['persons'])
                for f in os.listdir(DATA) if f.startswith('persons_') and f.endswith('.json'))
    merge_tail = args.merge_tail

    hit_total = 0
    miss = collections.Counter()
    miss_ctx = {}
    tail_merge = 0          # 后向合并统计：末字动词被剥掉重判的位置数
    tail_dropped = 0        # 剥完为空/全是动词字 → 非人名位置，正确忽略
    for f in chapter_files:
        d = json.load(io.open(os.path.join(BUILD, 'chapters', f), encoding='utf-8'))
        no = d['chapter']['no']
        for p in d['passages']:
            t = p['text']
            spans = covered.get((no, p['id']), [])
            for mt in RE.finditer(t):
                cand = mt.group(1)
                # 末字动词性字的两种处理（--no-merge 恢复旧行为=直接丢弃）：
                #   「允怒曰」——首字「允」是人名，剥掉「怒」重判，位置计入分母；
                #   「责之曰」「谓曰」——全是动词/代词，剥完为空，位置忽略。
                # 旧的硬丢弃把两类混在一起：前者被漏计（低估分母），后者丢得对。
                if cand[-1] in BAD_TAIL:
                    if not merge_tail:
                        continue
                    core = cand
                    while core and core[-1] in BAD_TAIL:
                        core = core[:-1]
                    if not core or core[-1] in BAD_TAIL:
                        tail_dropped += 1
                        continue
                    tail_merge += 1
                    cand = core
                s = mt.start(1)
                e = s + len(cand)
                if any(not (e <= a or b <= s) for a, b in spans):
                    hit_total += 1
                else:
                    miss[cand] += 1
                    if cand not in miss_ctx:
                        miss_ctx[cand] = '第%d回 …%s…' % (no, t[max(0, s - 8):e + 4])

    noise = {k: v for k, v in miss.items() if k in NOT_NAME}
    cand = {k: v for k, v in miss.items() if k not in NOT_NAME}
    noise_n = sum(noise.values())
    cand_n = sum(cand.values())
    total = hit_total + cand_n
    rate = hit_total / total * 100 if total else 0.0

    print('人物卡 %d 张 | 已链人物锚点 %d 处（%d 回 / %d 字）'
          % (cards, book['stats'].get('person_mentions', 0),
             len(book['chapters']), book['stats'].get('char_count', 0)))
    print('"X+曰/怒"类人名位置：已链 %d 处' % hit_total)
    if merge_tail:
        print('末字动词后向合并：重判 %d 处、忽略 %d 处（纯动词短语，本非人名位置）'
              % (tail_merge, tail_dropped))
    print('未链：疑似人名 %d 处 / %d 个，明显噪声 %d 处 / %d 个' % (cand_n, len(cand), noise_n, len(noise)))
    print('→ 估算覆盖率 %.1f%%（已链 / (已链+疑似漏网)）' % rate)
    print()
    print('漏网候选 Top %d（次数 | 词 | 首见上下文）：' % args.show)
    for k, v in sorted(cand.items(), key=lambda x: -x[1])[:args.show]:
        print('  %3d  %-6s %s' % (v, k, miss_ctx[k]))


if __name__ == '__main__':
    main()
