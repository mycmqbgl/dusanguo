#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
读三国 · 回归自检与截图（一条命令跑完）

用法
  python scripts/verify.py              # 只做自检 + 截图（用当前 build/ 与 app/）
  python scripts/verify.py --build      # 先重新构建，再全跑
  python scripts/verify.py --only data  # 只跑静态数据自检（不启浏览器，秒级）
  python scripts/verify.py --only map   # 只跑地图页场景
  python scripts/verify.py --no-shots   # 只自检，不截图

检查项
  A 数据自检      锚点指向的实体是否存在、战役节点坐标、州界闭合/自交、大势年份覆盖
  C 代码同源      两份页面内联的地图内核必须逐字节相同；模板里不得再出现第二份底图实现
  P 页面自检      无控制台报错、深链到达预期 DOM、关键注释/注记确实渲染出来
  S 截图          固定视口截图，检测空白页（非白像素占比过低即失败）

产物
  build/verify/*.png     截图
  build/verify/report.json 机器可读结果
  退出码 0 全过 / 1 有失败项
"""
import argparse
import glob
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, 'build')
APP = os.path.join(ROOT, 'app')
OUT = os.path.join(BUILD, 'verify')

sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from chron_const import CH_YEAR, FAC_BOUND  # noqa: E402  —— 回目→年份、势力年份上下界，与 expand_persons 同一份

EDGE_CANDIDATES = [
    '/usr/bin/chromium',
    '/usr/bin/google-chrome',
    '/usr/bin/chromium-browser',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
]

RESULTS = []


def add(kind, name, ok, detail=''):
    RESULTS.append({'kind': kind, 'name': name, 'ok': bool(ok), 'detail': detail})
    print('  %s %-46s %s' % ('PASS' if ok else 'FAIL', name, detail))


def load(path):
    with io.open(path, encoding='utf-8') as f:
        return json.load(f)


def find_browser():
    for p in EDGE_CANDIDATES:
        if os.path.exists(p):
            return p
    return None


# ---------------------------------------------------------------- A 数据自检
def check_data():
    print('\n[A] 数据自检')

    def need(rel, label):
        p = os.path.join(ROOT, rel)
        add('data', '产物存在 ' + label, os.path.exists(p), '' if os.path.exists(p) else '缺少 ' + rel)
        return p if os.path.exists(p) else None

    need('build/book.json', 'build/book.json')
    need('build/places.json', 'build/places.json')
    need('build/power.json', 'build/power.json')
    need('data/geo-real.json', 'data/geo-real.json')

    book = load(os.path.join(BUILD, 'book.json'))
    ch_no = sorted(c['no'] for c in book['chapters'])
    add('data', '回目连续（%d 回）' % len(ch_no), ch_no == list(range(1, len(ch_no) + 1)),
        ('首 %d 末 %d' % (ch_no[0], ch_no[-1])) if ch_no else '空')

    pids = set()
    pdir = os.path.join(BUILD, 'persons')
    if os.path.isdir(pdir):
        for f in os.listdir(pdir):
            if not f.endswith('.json') or f == 'index.json':
                continue
            pids.add(load(os.path.join(pdir, f))['id'])
    add('data', '人物卡（%d 张）' % len(pids), len(pids) > 0)

    places = {p['id']: p for p in load(os.path.join(BUILD, 'places.json'))}
    ev_ids = set()
    edir = os.path.join(BUILD, 'events')
    if os.path.isdir(edir):
        for f in os.listdir(edir):
            if not f.endswith('.json') or f == 'index.json':
                continue
            ev_ids.add(load(os.path.join(edir, f))['id'])
    add('data', '事件（%d 个）' % len(ev_ids), len(ev_ids) > 0)

    # 锚点 → 实体（顺带记下每人末见回目，供任期跨度检查用）
    bad, total, badspan = [], 0, 0
    last_seen = {}
    cdir = os.path.join(BUILD, 'chapters')
    for f in sorted(os.listdir(cdir)):
        if not f.endswith('.json'):
            continue
        ch = load(os.path.join(cdir, f))
        _c = ch.get('chapter')
        no = (_c.get('no') if isinstance(_c, dict) else _c) or int(re.sub(r'\D', '', f) or 0)
        for m in ch.get('mentions', []):
            total += 1
            if m['entity_type'] == 'place' and m['entity_id'] not in places:
                bad.append(('place', m['entity_id'], f))
            if m['entity_type'] == 'person' and pids and m['entity_id'] not in pids:
                bad.append(('person', m['entity_id'], f))
            if m['end'] <= m['start']:
                badspan += 1
            if m['entity_type'] == 'person' and no > last_seen.get(m['entity_id'], 0):
                last_seen[m['entity_id']] = no
    add('data', '锚点实体可解析（%d 条）' % total, not bad, ('示例 ' + str(bad[:3])) if bad else '')
    add('data', '锚点区间合法', badspan == 0, ('%d 条 end<=start' % badspan) if badspan else '')

    # ★ 2026-10：自动建档的任期结束年曾被一律设成「所属势力的年份上限」（见
    #   expand_persons.clamp_tenure 的 e = hi）。左丰只在第 1 回索贿卢植、全书
    #   出现 2 次，却因阵营判为 barbarian（上限 280）而在人物页 184–280 每一年
    #   都在任。全书 310 片如此。判据：auto 片的结束年晚于本人末见回目对应年份。
    #   追谥除外——曹嵩 wei/追谥 220–266 是曹丕称帝后追尊，本就晚于其阵亡之年。
    span_bad = []
    if os.path.isdir(pdir):
        for f in os.listdir(pdir):
            if not f.endswith('.json') or f == 'index.json':
                continue
            p = load(os.path.join(pdir, f))
            ly = CH_YEAR.get(last_seen.get(p.get('id')))
            if ly is None:
                continue
            for t in (p.get('tenure') or []):
                if t.get('review_status') != 'auto' or t.get('role') == '追谥':
                    continue
                e = t.get('end_year')
                if e is not None and e > ly:
                    span_bad.append((p['name'], t.get('start_year'), e, ly))
    add('data', '自动建档任期不晚于末见回目（%d 片超限）' % len(span_bad),
        not span_bad, str(span_bad[:3]) if span_bad else '')

    # ★ 2026-10：阵营归属的另一类错——简介的职任段写着「魏司徒」「吴大司马」，
    #   faction_id 却是另一个政权。根因同上：阵营是从抓取源的注记推断的，而注记
    #   本身可能写错（「吕岱，曹魏文臣，吴大司马」自相矛盾），推断照抄就跟着错。
    #   判据取职任段前两字「阵营字 + 官职字」：
    #     · 限「官职字」是因为「魏延追赶不上」里的「魏」是人名，不是政权；
    #     · 只在「该政权存续期与本人任期完全不相交」时放行——霍弋 264 年出场，
    #       蜀汉 263 年已亡，他此时已是魏臣，判 wei 不误。
    #       （注意不能用「重叠 ≥2 年」：单人单年任期本身长度就是 0，会漏掉吕岱。）
    WARD = {'吴': 'wu', '魏': 'wei', '蜀': 'shu', '汉': 'han', '晋': 'jin'}
    OFFICE = set('司太中大刺将相侍光长参领征镇都护建谏官尚御廷卫车骠黄')
    DUTY_RE = re.compile(r'^[^，]+，[^，]+，([^。]{1,40})。')
    # 已知合理例外：
    #   du_xi    — 215–219 为汉侍中，220 年后仕魏，判 wei 指后段；
    #   yang_mi  — 两个同名者（第 13 回李傕部将 / 第 108 回）被并成一张卡，待拆；
    #   yong_kai — 南中大姓，蜀汉任其为建宁太守后反，faction 归南中势力（barbarian）、
    #              职任段写反叛前的「蜀建宁太守」，两者并存不矛盾。
    FAC_OK = {'du_xi', 'yang_mi', 'yong_kai'}
    fac_bad = []
    if os.path.isdir(pdir):
        for f in os.listdir(pdir):
            if not f.endswith('.json') or f == 'index.json':
                continue
            p = load(os.path.join(pdir, f))
            tns = [t for t in (p.get('tenure') or []) if t.get('review_status') == 'auto']
            if not tns or p.get('id') in FAC_OK:
                continue
            facs = {t.get('faction_id') for t in tns}
            lo = min(t['start_year'] for t in tns)
            hi = max(t['end_year'] for t in tns)
            for key in ('summary', 'bio'):
                m = DUTY_RE.match(p.get(key) or '')
                if not m:
                    continue
                duty = m.group(1)
                if len(duty) < 2 or duty[0] not in WARD or duty[1] not in OFFICE:
                    continue
                # 职任段可能横跨两朝（贾逵「汉谏议大夫，魏建威将军」），
                # 只要其中任一政权与本人的片相符就算一致
                chars = {WARD[c] for c in duty if c in WARD}
                if facs & chars:
                    continue
                wlo, whi = FAC_BOUND.get(WARD[duty[0]], (184, 280))
                if min(hi, whi) < max(lo, wlo):
                    continue          # 任期与该政权存续期完全不相交，讲的是另一时期
                fac_bad.append((p['name'], duty[:14], sorted(facs)))
    add('data', '简介职任段阵营与本片归属一致（%d 条不符）' % len(fac_bad),
        not fac_bad, str(fac_bad[:3]) if fac_bad else '')

    nopix = [p['id'] for p in places.values() if p.get('pixel_x') is None]
    add('data', '地名均有像素坐标（%d 个）' % len(places), not nopix, str(nopix[:4]) if nopix else '')

    # 战役节点
    battles, badb = [], []
    bdir = os.path.join(BUILD, 'battles')
    if os.path.isdir(bdir):
        for f in sorted(os.listdir(bdir)):
            if f.endswith('.json'):
                battles.append(load(os.path.join(bdir, f)))
    for b in battles:
        if len(b.get('front_line') or []) < 2:
            badb.append((b['id'], '节点不足'))
        for n in b.get('front_line') or []:
            if n.get('pixel_x') is None or n.get('pixel_y') is None:
                badb.append((b['id'], n.get('label')))
    add('data', '战役节点坐标完整（%d 场 / %d 节点）'
        % (len(battles), sum(len(b.get('front_line') or []) for b in battles)), not badb, str(badb[:3]) if badb else '')
    orph = [b['id'] for b in battles if b.get('event_id') not in ev_ids]
    add('data', '战役父事件存在', not orph, str(orph[:3]) if orph else '')

    # 大势（郡级版）
    power = load(os.path.join(BUILD, 'power.json'))
    years = power.get('years') or []
    by = power.get('byYear') or {}
    snaps = power.get('snapshots') or {}
    fids = {f['id'] for f in power.get('factions') or []}
    miss = [y for y in years if str(y) not in by]
    add('data', '大势年份逐年展开（%d 年）' % len(years), not miss, str(miss[:4]) if miss else '')
    add('data', '大势覆盖 184–280（%d 快照）' % len(snaps),
        years and years[0] == 184 and years[-1] == 280 and len(snaps) == 28,
        '%d..%d' % (years[0] if years else -1, years[-1] if years else -1))
    add('data', '大势势力数 = 42', len(fids) == 42, '实际 %d' % len(fids))
    badh = []
    for y, s in snaps.items():
        seen = {}
        for fid, jl in (s.get('hold') or {}).items():
            if fids and fid not in fids:
                badh.append((y, fid))
            for j in jl:
                if j in seen:
                    badh.append((y, j, '重复'))
                seen[j] = fid
        if len(seen) != 123:
            badh.append((y, '覆盖 %d/123 郡' % len(seen)))
    add('data', '每快照 123 郡恰一主', not badh, str(badh[:3]) if badh else '')
    zl = power.get('zhou_labels') or {}
    add('data', '十三州注记锚点', len(zl) == 13, '实际 %d' % len(zl))
    badlbl = [y for y, s in snaps.items() if len(s.get('labels') or {}) != len(s.get('hold') or {})]
    add('data', '势力注记锚点与归属一一对应', not badlbl, str(badlbl[:4]))

    # ★ 2026-10：以上全是查磁盘上的 build/power.json，查不出「构建时大势静默失败、
    #   前端拿到 null」这条链——build.py 里 build_power 抛异常只打印一行、power=None，
    #   reader.html 内联 DATA.power=null，大势页整页空白，而上面每一条都照旧 PASS。
    #   所以这里必须回读**已构建的 reader.html**，断言内联数据里确实有 power。
    rpath = os.path.join(ROOT, 'app', 'reader.html')
    if os.path.exists(rpath):
        html = io.open(rpath, encoding='utf-8').read()
        m = re.search(r'const DATA\s*=\s*(\{.*?\});\s*\n', html, re.S)
        inline_pw = None
        if m:
            try:
                inline_pw = json.loads(m.group(1)).get('power')
            except ValueError:
                inline_pw = 'PARSE_FAIL'
        ok_pw = isinstance(inline_pw, dict) and len(inline_pw.get('snapshots') or {}) == len(snaps)
        add('build', 'reader.html 内联大势数据（非 null）', ok_pw,
            '构建时大势生成失败？看 build.py 的「大势数据生成失败」一行'
            if not ok_pw else '%d 快照 / %d 势力'
            % (len(inline_pw.get('snapshots') or {}), len(inline_pw.get('factions') or [])))
        # 降级提示文本本身就是模板里 `if (!POWER)` 分支的源码，静态搜文本必然命中，
        # 所以改由下方的页面场景断言（reader_power* 的「!大势数据未生成」）兜底，
        # 这里只查内联数据是否为空——空即等于用户看到那句话。

    # 州界几何 + 汉县
    geo = load(os.path.join(ROOT, 'data', 'geo-real.json'))
    zp = geo.get('zhoupoly') or []
    closed = [z.get('name') for z in zp if z['pts'][0] != z['pts'][-1]]
    add('data', '州界闭合（%d 州）' % len(zp), not closed, str(closed[:4]) if closed else '')
    holes = []
    try:
        from shapely.geometry import Polygon
        for z in zp:
            if not Polygon(z['pts']).is_simple:
                holes.append(z.get('name'))
        add('data', '州界无自交', not holes, str(holes) if holes else '')
    except ImportError:
        print('    （未装 shapely，跳过自交检查）')
    cf = os.path.join(ROOT, 'data', 'counties-han.json')
    if os.path.exists(cf):
        cs = load(cf)['counties']
        tiers = {}
        for c in cs:
            tiers[c['t']] = tiers.get(c['t'], 0) + 1
        add('data', '汉县点位（%d 个）' % len(cs), len(cs) > 250,
            '治所 %d / 县 %d' % (tiers.get('都', 0), tiers.get('县', 0)))


# ---------------------------------------------------------------- C 代码同源
CORE_HEAD = '读三国 · 地图内核 MapCore'
CORE_TAIL = 'window.MapCore = (function'


def core_slice(html):
    i = html.find(CORE_TAIL)
    if i < 0:
        return None
    j = html.find('})();', i)
    return html[i:j + 5] if j > 0 else None


def check_same_source():
    print('\n[C] 代码同源（防地图双轨复发）')
    core_path = os.path.join(APP, 'map_core.js')
    add('code', '内核文件存在 app/map_core.js', os.path.exists(core_path))
    if not os.path.exists(core_path):
        return
    core = io.open(core_path, encoding='utf-8').read()
    add('code', '内核头部说明完整', CORE_HEAD in core)

    pages = ['map_test.html', 'reader.html']
    slices = []
    for pg in pages:
        p = os.path.join(APP, pg)
        if not os.path.exists(p):
            add('code', '页面存在 ' + pg, False)
            continue
        html = io.open(p, encoding='utf-8').read()
        cs = core_slice(html)
        slices.append((pg, cs))
        # 逐字节内联：构建脚本注入的就是 app/map_core.js 原文
        add('code', '%s 内联内核' % pg, core.strip() in html,
            '长度 %s' % (len(cs) if cs else 0))
        # 内核以外不得再有第二份底图实现（把内核本身剔掉再查）
        rest = html.replace(core.strip(), '')
        dup = [fn for fn in ['function drawBase', 'function decorScale', 'function _pz',
                             'function lockZoom', 'function viewBox'] if fn in rest]
        add('code', '%s 无重复底图实现' % pg, not dup, str(dup) if dup else '')

    if len(slices) == 2 and all(s for _, s in slices):
        h = [hashlib.sha1(s.encode('utf-8')).hexdigest()[:12] for _, s in slices]
        add('code', '两页内核逐字节相同', h[0] == h[1], ' / '.join(h))


# ---------------------------------------------------------------- 浏览器
def run_browser(browser, url, extra, timeout=120):
    # 每次调用独立 profile：避免进程单例把两次调用并进同一实例造成串页/竞态
    prof = os.path.join(BUILD, 'tmp', 'edgeprof_%d' % (int(time.time() * 1000) % 100000000))
    cmd = [browser, '--headless=new', '--disable-gpu', '--hide-scrollbars',
           '--no-first-run', '--no-sandbox', '--user-data-dir=' + prof] + extra + [url]
    t0 = time.time()
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, ['TIMEOUT'], time.time() - t0
    out = p.stdout.decode('utf-8', 'ignore')
    err = p.stderr.decode('utf-8', 'ignore')
    logs = []
    for line in err.splitlines():
        low = line.lower()
        if 'uncaught' in low or ('console' in low and ('error' in low or 'severe' in low)):
            logs.append(line.strip()[:400])
    return out, logs, time.time() - t0


def file_url(rel):
    return 'file:///' + os.path.abspath(os.path.join(APP, rel)).replace('\\', '/')


def check_page(browser, name, rel, frag, expect, wait=5000):
    """打开页面 → 抓 DOM + 控制台。
    expect 里以 ! 开头的串表示「不应出现」。匹配前先剥掉内联 <script>——
    本项目数据与模板全部内联，不剥的话源代码里的字符串会造成假阳性。"""
    url = file_url(rel) + (frag or '')
    html, logs, dt = run_browser(browser, url, ['--virtual-time-budget=%d' % wait, '--dump-dom'])
    if html is None or logs:      # 冷启动偶发超时，重试一次
        html, logs, dt = run_browser(browser, url, ['--virtual-time-budget=%d' % (wait * 2), '--dump-dom'])
    ok = html is not None and not logs
    detail = '%.1fs' % dt
    if logs:
        detail = logs[0][:160]
    add('page', name, ok, detail)
    if html:
        dom = re.sub(r'<script\b.*?</script>', '', html, flags=re.S)
        neg = [k[1:] for k in expect if k.startswith('!')]
        need = [k for k in expect if not k.startswith('!') and k not in dom]
        miss = [k for k in neg if k in dom]
        add('page', name + ' · 关键内容', not need and not miss,
            (('缺 ' + str(need)) if need else '') + (('不该有 ' + str(miss)) if miss else ''))
    return html


def check_shot(browser, name, rel, frag, w=1500, h=950, wait=6000):
    path = os.path.join(OUT, name + '.png')
    # 截图加 shot=1：页面禁用过渡/动画（合成器动画不受 virtual-time 控制，
    # 否则弹窗开场动画会被截到中间帧，基线逐次漂移）
    if (frag or '').startswith('?'):
        url = file_url(rel) + frag + '&shot=1'
    else:
        url = file_url(rel) + '?shot=1' + (frag or '')
    _, logs, dt = run_browser(browser, url, ['--window-size=%d,%d' % (w, h),
                                             '--virtual-time-budget=%d' % wait,
                                             '--screenshot=' + path])
    if not os.path.exists(path):
        add('shot', name, False, '未生成文件')
        return
    # 空白页检测：非纸色像素占比
    ink = 0.0
    size = os.path.getsize(path)
    try:
        from PIL import Image
        im = Image.open(path).convert('L').resize((160, 100))
        px = list(im.getdata())
        ink = sum(1 for v in px if v < 225) / float(len(px))
    except Exception:
        ink = 1.0 if size > 20000 else 0.0
    ok = ink > 0.02 and not logs
    add('shot', name, ok, 'ink %.1f%% · %dKB · %.1fs' % (ink * 100, size // 1024, dt))
    if ARGS.shots and ok:
        check_baseline(name, path)


# ---------------------------------------------------------------- 像素基线
# 「能截到图」≠「没改坏」：截图只判空页的话，地图挪位、配色破坏、卡片塌了都拦不住。
# baseline/ 下的图是人工确认过的快照；超过容差就输出并排对比图供人裁决。
BASELINE_DIR = os.path.join(OUT, 'baseline')
DIFF_DIR = os.path.join(OUT, 'diff')
PIXEL_TOL = 8          # 每通道差 ≤8 视为同一颜色（无头渲染的亚像素抖动）
DIFF_LIMIT = 0.003     # 差异像素占比 >0.3% 判超阈（待办定值）


def check_baseline(name, shot_path):
    base = os.path.join(BASELINE_DIR, name + '.png')
    if ARGS.update_baseline:
        os.makedirs(BASELINE_DIR, exist_ok=True)
        shutil.copy2(shot_path, base)
        add('baseline', name, True, '基线已更新')
        return
    if not os.path.exists(base):
        # 首见场景：本张自动入基线，但要让人知道这是「未审快照」，不是「验证通过」
        os.makedirs(BASELINE_DIR, exist_ok=True)
        shutil.copy2(shot_path, base)
        add('baseline', name, True, '首见，已入基线（未经人工确认）')
        return
    try:
        from PIL import Image, ImageChops
        a = Image.open(base).convert('RGB')
        b = Image.open(shot_path).convert('RGB')
    except Exception as e:
        add('baseline', name, False, '图像读取失败: %s' % e)
        return
    if a.size != b.size:
        add('baseline', name, False, '尺寸不同 基线%s vs 当前%s' % (a.size, b.size))
        return
    diff = ImageChops.difference(a, b)
    # 每通道都 ≤ PIXEL_TOL 的像素视为相同；用 point 向量化，比逐像素循环快一个量级
    thr = diff.point(lambda v: 0 if v <= PIXEL_TOL else 255).convert('L')
    hist = thr.histogram()
    ndiff = hist[255]
    ratio = ndiff / float(a.size[0] * a.size[1])
    if ratio <= DIFF_LIMIT:
        add('baseline', name, True, 'diff %.3f%%' % (ratio * 100))
        return
    # 超阈：输出并排对比图（左基线右当前，中间红线），落 diff/ 供人裁决
    os.makedirs(DIFF_DIR, exist_ok=True)
    w, h = a.size
    canvas = Image.new('RGB', (w * 2 + 4, h), (200, 30, 30))
    canvas.paste(a, (0, 0))
    canvas.paste(b, (w + 4, 0))
    out = os.path.join(DIFF_DIR, name + '.png')
    canvas.save(out)
    add('baseline', name, False,
        'diff %.2f%%（>%.1f%%）→ %s' % (ratio * 100, DIFF_LIMIT * 100, os.path.relpath(out, ROOT)))


# ---------------------------------------------------------------- 场景
# expect 中 '!' 前缀 = 不应出现；匹配前会剥掉内联 <script>，只查渲染结果
# 基础场景 = 与铺量无关的 UI 骨架；铺量相关（末回、战役）由 auto_scenes() 生成，
# 上限 SCENE_LIMIT，超限丢最老的战役桶——新铺的内容更需要回归。
MAP_SCENES = [
    ('map_full', 'map_test.html', '?z=1.4', ['冀州', '交州', '1.40×']),
    # snap=1：深链瞬时落位（回归专用），无头环境 rAF 不稳定也能截到最终状态
    ('map_place', 'map_test.html', '?snap=1#place=luo_yang', ['class="detail" id="detail"', '!1.00×']),
    ('map_county', 'map_test.html', '?snap=1#county=%E9%9B%92%E9%98%B3', ['class="detail" id="detail"', '5.50×']),
]
READER_SCENES = [
    ('reader_persons', 'reader.html', '#persons', ['全部阵营']),
    ('reader_places', 'reader.html', '#places', ['个点位']),
    # ★ '!大势数据未生成' 是必需品：build.py 里大势生成失败只留一行日志、
    #   内联 DATA.power=null、大势页整页空白，而「190<small>」这类断言断的是侧栏，
    #   侧栏照常渲染 → 所有检查都 PASS。2026-10 的空白页就是这么漏过去的。
    ('reader_power190', 'reader.html', '#power=190',
     ['190<small>', '势力边界', '!大势数据未生成']),
    ('reader_power200', 'reader.html', '#power=200', ['200<small>', '!大势数据未生成']),
    ('reader_power184', 'reader.html', '#power=184',
     ['184<small>', '不属/史载不明', '!大势数据未生成']),
    ('reader_power280', 'reader.html', '#power=280', ['280<small>', '!大势数据未生成']),
    ('reader_events', 'reader.html', '#events', ['挂载战役']),
    ('reader_placecard', 'reader.html', '#placecard=luo_yang', ['比例由地名类型预设']),
    # P1-1 定案（2026-10-28 修订）：改名「史异注」，不折叠，固定渲染在卡片底部；
    # 无冲突者不得出现「史异注」字样（反向断言）
    ('reader_conflict', 'reader.html', '#person=hua_xiong', ['史异注', '功劳归属', '!<details']),
    ('reader_no_conflict', 'reader.html', '#person=cao_cao', ['!史异注']),
    # 生卒年双标：吉平卡片须在演义生卒下标出史书生卒
    ('reader_life_dates', 'reader.html', '#person=ji_ping',
     ['史书生卒', '建安二十三年', '!<details']),
    # 关系图谱：时点条（君臣/敌对开关）与画布须渲染出节点
    ('reader_graph', 'reader.html', '#graph', ['君臣', '敌对', 'gnode']),
    # D-7：弱链接（is_weak_link）须与回指推定（anaphora）分样式，且点击不弹全卡。
    # 第 1 回「嵩曰」是 is_weak_link，曹嵩与皇甫嵩同姓同字面，正是证据不足的典型。
    ('reader_weak', 'reader.html', '#chapter=1',
     ['ent p wl', 'data-wl="1"', '点击不展开人物卡', '!class="ent p weak" data-t="person" data-id="cao_song"']),
]

SCENE_LIMIT = 30


def auto_scenes():
    """随铺量自动扩展的场景：末回正文 + 每 10 回桶里 front_line 最长的战役。

    战役断言语义化：断言面板里出现该战役首节点 label（如「分兵把关」），
    而不是只断言有面板——「有面板」拦不住「挂错战役」这类错误。
    战役 → 章节 的映射借事件数据：event.passage_ids 推章，event.battle_ids 推战役。
    """
    scenes = []
    cdir = os.path.join(BUILD, 'chapters')
    bdir = os.path.join(BUILD, 'battles')
    edir = os.path.join(BUILD, 'events')
    nos = sorted(int(f[2:5]) for f in os.listdir(cdir) if f.startswith('ch') and f.endswith('.json'))
    if not nos:
        return scenes
    # 末回正文（原 reader_ch30 硬编码的替代，铺到 40 回自动跟到 40）
    scenes.append(('reader_last', 'reader.html', '#chapter=%d' % nos[-1], ['第 %d 回' % nos[-1]]))
    if not (os.path.isdir(bdir) and os.path.isdir(edir)):
        return scenes
    ev_ch = {}
    for f in glob.glob(os.path.join(edir, '*.json')):
        try:
            ev = json.load(io.open(f, encoding='utf-8'))
        except Exception:
            continue
        pids = ev.get('passage_ids') or []
        if not pids:
            continue
        ch0 = min(p // 1000 for p in pids)
        for bid in ev.get('battle_ids') or []:
            ev_ch.setdefault(bid, ch0)
    buckets = {}
    for f in glob.glob(os.path.join(bdir, '*.json')):
        try:
            b = json.load(io.open(f, encoding='utf-8'))
        except Exception:
            continue
        ch = ev_ch.get(b['id'])
        fl = b.get('front_line') or []
        if not ch or not fl or not fl[0].get('label'):
            continue
        buckets.setdefault((ch - 1) // 10, []).append((ch, b))
    # 新桶优先保留（上限不够时丢最老的桶，成对丢弃保持 map/reader 对称）
    pairs = []
    for bucket in sorted(buckets, reverse=True):
        ch, b = max(buckets[bucket], key=lambda t: (len(t[1]['front_line']), t[0]))
        label = b['front_line'][0]['label']
        pairs.append([
            ('map_battle_ch%d' % ch, 'map_test.html', '?snap=1#battle=%s' % b['id'],
             ['class="detail" id="detail"', label]),
            ('reader_battle_ch%d' % ch, 'reader.html', '?snap=1#battle=%s' % b['id'], [label]),
        ])
    fixed = len(MAP_SCENES) + len(READER_SCENES) + 1        # +1 = 末回
    for pair in reversed(pairs):                            # 恢复老→新
        if fixed + len(pair) > SCENE_LIMIT:
            continue
        scenes.extend(pair)
        fixed += len(pair)
    return scenes


def check_browser(browser, only):
    print('\n[P] 页面自检 + [S] 截图（%s）' % os.path.basename(browser))
    auto = auto_scenes()
    n_auto = len(auto) - 1        # 末回之外的自动战役场景数
    print('  自动场景：末回 1 + 战役 %d（桶按 front_line 最长，上限 %d）' % (n_auto, SCENE_LIMIT))
    scenes = []
    if only in (None, 'map'):
        scenes += MAP_SCENES + [s for s in auto if s[1] == 'map_test.html']
    if only in (None, 'reader'):
        scenes += [s for s in auto if s[1] == 'reader.html'] + READER_SCENES
    for name, rel, frag, expect in scenes:
        if only != 'shots':
            check_page(browser, name, rel, frag, expect)
        if ARGS.shots:
            check_shot(browser, name, rel, frag)


def main():
    global ARGS
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true', help='先跑 scripts/build.py')
    ap.add_argument('--only', choices=['data', 'code', 'map', 'reader'], help='只跑一部分')
    ap.add_argument('--no-shots', dest='shots', action='store_false', help='不截图')
    ap.add_argument('--update-baseline', action='store_true',
                    help='把本次截图全部刷新为基线（先人工过图再用，否则把 bug 固化）')
    ARGS = ap.parse_args()
    ARGS.shots = getattr(ARGS, 'shots', True)

    if not os.path.isdir(OUT):
        os.makedirs(OUT)

    if ARGS.build:
        print('构建中…')
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'scripts', 'build.py')],
                           cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        tail = r.stdout.decode('utf-8', 'ignore').strip().splitlines()[-1:]
        add('build', 'build.py 成功', r.returncode == 0, ' '.join(tail))
        if r.returncode != 0:
            print(r.stdout.decode('utf-8', 'ignore')[-3000:])

    if ARGS.only in (None, 'data'):
        check_data()
    if ARGS.only in (None, 'code'):
        check_same_source()

    if ARGS.only in (None, 'map', 'reader'):
        b = find_browser()
        if not b:
            add('page', '找到无头浏览器', False, 'Edge/Chrome 均未找到')
        else:
            check_browser(b, ARGS.only)

    fails = [r for r in RESULTS if not r['ok']]
    with io.open(os.path.join(OUT, 'report.json'), 'w', encoding='utf-8') as f:
        json.dump({'time': time.strftime('%Y-%m-%d %H:%M:%S'), 'total': len(RESULTS),
                   'failed': len(fails), 'items': RESULTS}, f, ensure_ascii=False, indent=1)
    print('\n合计 %d 项，失败 %d 项 → %s' % (len(RESULTS), len(fails),
                                        os.path.relpath(os.path.join(OUT, 'report.json'), ROOT)))
    for r in fails:
        print('  × [%s] %s %s' % (r['kind'], r['name'], r['detail']))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
