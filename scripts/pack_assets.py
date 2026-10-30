# -*- coding: utf-8 -*-
"""打包「项目资产」上传集。

原则：只收**人工维护的源文件**，一切可由脚本重建的产物都不入资产，
避免资产里出现第二份真相（历史上地图双轨代码就是这么来的）。

    python scripts/pack_assets.py            # 生成 dist/读三国-项目资产/ 与 zip
    python scripts/pack_assets.py --no-zip   # 只出目录
    python scripts/pack_assets.py --list     # 只打印清单，不写盘

排除项及重建方式写在包内 MANIFEST.md 里，脚本每次运行重新生成该文件。
"""
import argparse
import datetime
import io
import json
import os
import shutil
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'dist', '读三国-项目资产')
NAME = '读三国-项目资产'

# (相对路径, 类型)  type: file | glob
INCLUDE = [
    ('README.md', 'file'),
    ('docs', 'mdhtml'),          # 文档：*.md + *.html + 报告配图
    ('app', 'appsrc'),           # 前端源：内核 + 两个模板 + 地形底图
    ('scripts', 'py'),           # 构建与校验脚本
    ('data', 'data'),            # 数据源：实体卡、事件、地理、原文
]

# 扫描脚本的中间输出（discover_entities.py 可重跑），不入资产
SKIP_FILES = ('data/discovered.json', 'data/discovered2.json')

# 生成物：随源更新，可打开即读，但**不得手改**
BUILT = ['app/reader.html', 'app/map_test.html']

# 不入资产的东西：路径前缀 → 重建方式
EXCLUDE_NOTE = [
    ('build/', '全部构建产物（book/places/persons/chapters/events/battles/power/verify/shots/tmp）',
     '`python scripts/build.py` 一条命令重建，约 2 分钟'),
    ('data/ne/', 'Natural Earth 10m 海岸线/河流/湖泊 + DEM 网格缓存（145 MB 外部数据）',
     '从 naturalearthdata.com 下 10m 矢量包放入 `data/ne/`，DEM 由 `scripts/build_terrain.py` 自动缓存'),
    ('app/assets/terrain.png', '地形图 PNG 母版（21 MB）',
     '`python scripts/build_terrain.py` 从 `data/ne/` 重新渲染'),
    ('.workbuddy/', '会话与记忆目录（本机私有）', '—'),
]


def size_of(p):
    if os.path.isfile(p):
        return os.path.getsize(p)
    n = 0
    for base, _, files in os.walk(p):
        for f in files:
            n += os.path.getsize(os.path.join(base, f))
    return n


def human(n):
    for u in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or u == 'GB':
            return ('%.1f %s' % (n, u)) if u != 'B' else ('%d B' % n)
        n /= 1024.0


def collect():
    """返回 [(源绝对路径, 包内相对路径)]"""
    items = []
    for rel, kind in INCLUDE:
        src = os.path.join(ROOT, rel)
        if kind == 'file':
            if os.path.isfile(src):
                items.append((src, rel))
            continue
        if not os.path.isdir(src):
            continue
        for base, dirs, files in os.walk(src):
            dirs[:] = sorted(d for d in dirs if d != '__pycache__')
            for f in sorted(files):
                p = os.path.join(base, f)
                sub = os.path.relpath(p, ROOT).replace('\\', '/')
                ext = os.path.splitext(f)[1].lower()
                if kind == 'mdhtml' and ext not in ('.md', '.html', '.png'):
                    continue
                if kind == 'appsrc' and ext not in ('.js', '.html', '.jpg'):
                    continue
                if kind == 'py' and ext != '.py':
                    continue
                if kind == 'data':
                    if sub in SKIP_FILES:
                        continue
                    if sub.startswith('data/ne/'):
                        continue
                    if ext not in ('.json', '.txt', '.csv'):
                        continue
                items.append((p, sub))
    return items


def stats():
    """包内 MANIFEST 用的现状数字，取自 build/（跑过 build.py 才有）

    缺哪个数就少打哪一行，不编造；但要喊出来——MANIFEST 里数字静默消失
    比报错更难查。
    """
    d = {}
    missing = []

    def warn(what, e):
        missing.append('%s（%s）' % (what, e.__class__.__name__))

    try:
        b = json.load(io.open(os.path.join(ROOT, 'build', 'book.json'), encoding='utf-8'))
        d['chapters'] = len(b['chapters'])
        st = b['stats']
        d['chars'] = st.get('char_count')
        d['passages'] = st.get('passage_count')
    except Exception as e:
        warn('章数/字数/段落数', e)
    for key, path in (('persons', 'build/persons'), ('events', 'build/events'), ('battles', 'build/battles')):
        p = os.path.join(ROOT, path)
        if os.path.isdir(p):
            d[key] = len([f for f in os.listdir(p) if f.endswith('.json') and f != 'index.json'])
    try:
        pl = json.load(io.open(os.path.join(ROOT, 'build', 'places.json'), encoding='utf-8'))
        d['places'] = len(pl)
    except Exception as e:
        warn('点位数', e)
    try:
        n = 0
        cdir = os.path.join(ROOT, 'build', 'chapters')
        for f in os.listdir(cdir):
            if f.endswith('.json'):
                n += len(json.load(io.open(os.path.join(cdir, f), encoding='utf-8')).get('mentions', []))
        d['mentions'] = n
    except Exception as e:
        warn('提及数', e)
    if missing:
        sys.stderr.write('  ! MANIFEST 缺数字：%s —— 先跑 scripts/build.py\n' % '、'.join(missing))
    return d


def manifest(items, d):
    total = sum(size_of(s) for s, _ in items)
    by_dir = {}
    for s, rel in items:
        k = rel.split('/')[0] if '/' in rel else '(根目录)'
        by_dir[k] = by_dir.get(k, 0) + size_of(s)
    today = datetime.date.today().isoformat()

    L = []
    A = L.append
    A('# 读三国 · 项目资产清单')
    A('')
    A('> 生成于 %s，由 `scripts/pack_assets.py` 自动产出。**本目录即项目真相**：' % today)
    A('> 本地工作区只是工作副本，任何改动先落在这里，再同步回本地构建。')
    A('')
    A('## 一、这份资产里有什么')
    A('')
    A('| 目录 | 内容 | 体积 |')
    A('|---|---|---|')
    duty = {
        '(根目录)': '`README.md` 项目入口 + `MANIFEST.md` 本清单',
        'docs': '需求文档 / 设计文档 / 规则手册 / 待确认问题 / 待办清单 / 各期报告',
        'app': '前端源：`map_core.js` 地图内核、两个 `*_template.html`、`assets/terrain.jpg`',
        'scripts': '构建、抓取、地理、校验脚本（`build.py` / `prepare_geo.py` / `verify.py` …）',
        'data': '数据源：人物卡、事件战役、地名、大势、词表规则、原文 `source/chNNN.txt`',
    }
    for k, v in by_dir.items():
        A('| `%s` | %s | %s |' % (k, duty.get(k, ''), human(v)))
    A('')
    A('文件合计 **%d 个 / %s**。' % (len(items), human(total)))
    A('')
    A('## 二、其中的生成物（可打开即读，勿手改）')
    A('')
    A('| 文件 | 体积 | 说明 |')
    A('|---|---|---|')
    for rel in BUILT:
        p = os.path.join(ROOT, rel)
        if os.path.isfile(p):
            A('| `%s` | %s | 数据与内核已内联的单文件成品页，双击即读 |'
              % (rel, human(os.path.getsize(p))))
    A('')
    A('这两份是 `build.py` 把 `data/` 与 `app/map_core.js` 内联进模板后的产物。')
    A('放进来是为了让资产**脱离 Python 环境也能直接打开**；但它们是只读快照——')
    A('要改内容改 `app/*_template.html` 或 `data/`，再重建，**不要直接编辑这两个文件**，')
    A('否则下次构建会被覆盖，且会重新制造「两份实现」的老问题。')
    A('')
    A('## 三、没有放进来什么（以及怎么重建）')
    A('')
    A('| 排除项 | 是什么 | 重建方式 |')
    A('|---|---|---|')
    for p, what, how in EXCLUDE_NOTE:
        A('| `%s` | %s | %s |' % (p, what, how))
    A('')
    A('合计排除约 1.15 GB。这些全部可以再生成，放进资产只会引出「改了模板忘了重建 /')
    A('拿旧产物当真相」的老问题。')
    A('')
    A('## 四、现状数字')
    A('')
    if d:
        A('| 项 | 值 |')
        A('|---|---|')
        if 'chapters' in d:
            A('| 已入库回目 | 第 1–%d 回 |' % d['chapters'])
        if d.get('chars'):
            A('| 正文字数 | {:,} |'.format(d['chars']))
        if d.get('passages'):
            A('| 段落数 | {:,} |'.format(d['passages']))
        if 'mentions' in d:
            A('| 正文锚点 | {:,} 条 |'.format(d['mentions']))
        if 'persons' in d:
            A('| 人物卡 | %d 张 |' % d['persons'])
        if 'places' in d:
            A('| 地名 | %d 个 |' % d['places'])
        if 'events' in d:
            A('| 事件 | %d 个 |' % d['events'])
        if 'battles' in d:
            A('| 战役 | %d 场 |' % d['battles'])
    else:
        A('（本地未跑过 `build.py`，数字缺省）')
    A('')
    A("## 五、从这份资产重建整站")
    A('')
    A('```bash')
    A('# 1) 取回资产到本地工作目录，装依赖')
    A('pip install shapely pillow numpy')
    A('# 2) 补外部地理数据到 data/ne/（见第三节「没有放进来什么」）')
    A('# 3) 重建')
    A('python scripts/build.py        # 生成 build/ 与 app/reader.html、app/map_test.html')
    # 回归项数从最近一次 build/verify/report.json 读，避免手册里的数字随场景增加腐坏
    n_suite = None
    try:
        n_suite = json.load(io.open(os.path.join(ROOT, 'build', 'verify', 'report.json'),
                                   encoding='utf-8')).get('total')
    except Exception:
        pass
    A('python scripts/verify.py       # %s 项回归，退出码 0 即可交付'
      % ('%d' % n_suite if n_suite else 'N'))
    A('```')
    A('')
    A("## 六、维护约定")
    A('')
    A('1. **资产为准**：文档、数据、脚本、前端源的修改先落资产，本地副本随后对齐。')
    A('2. **构建产物不入资产**：`build/` 与两个成品页只在本地存在，需要时重建。')
    A('3. **改动必过回归**：`python scripts/verify.py` 退出码 0 才能算完；数据类改动还会跑 `validate_cards.py`。')
    A('4. **文档与待办同步**：改了口径先改 `docs/规则手册.md` 与 `docs/需求文档.md`，待办镜像 `docs/待办清单.md` 跟着走。')
    A('')
    return '\n'.join(L) + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-zip', action='store_true')
    ap.add_argument('--list', action='store_true')
    a = ap.parse_args()

    items = collect()
    if not items:
        print('没有可打包的文件，检查 INCLUDE 配置', file=sys.stderr)
        return 1
    d = stats()

    total = sum(size_of(s) for s, _ in items)
    if a.list:
        for s, rel in items:
            print('%9s  %s' % (human(size_of(s)), rel))
        print('-' * 40)
        print('%9s  %d 个文件' % (human(total), len(items)))
        return 0

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    for s, rel in items:
        dst = os.path.join(OUT, rel.replace('/', os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(s, dst)

    man = manifest(items, d)
    io.open(os.path.join(OUT, 'MANIFEST.md'), 'w', encoding='utf-8').write(man)

    print('资产包：%s' % OUT)
    print('  %d 个文件 / %s（另 MANIFEST.md）' % (len(items), human(total)))
    for k in ('docs', 'app', 'scripts', 'data'):
        n = len([1 for _, rel in items if rel.startswith(k + '/')])
        if n:
            sz = sum(size_of(s) for s, rel in items if rel.startswith(k + '/'))
            print('  %-8s %3d 个  %s' % (k, n, human(sz)))

    if not a.no_zip:
        today = datetime.date.today().strftime('%Y%m%d')
        zpath = os.path.join(ROOT, 'dist', '%s-%s.zip' % (NAME, today))
        with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for base, _, files in os.walk(OUT):
                for f in files:
                    p = os.path.join(base, f)
                    z.write(p, os.path.join(NAME, os.path.relpath(p, OUT)))
        print('  压缩包：%s（%s）' % (zpath, human(os.path.getsize(zpath))))
    return 0


if __name__ == '__main__':
    sys.exit(main())
