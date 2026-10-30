#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""水墨全身像 · AI 批量出图脚本（多通道，本地运行版）

为全库 1183 位三国人物生成水墨风全身立像，输出 app/assets/avatars/<id>.png。
人物提示词全部来自 build/avatars_manifest.json（scripts/build_avatar_manifest.py 依据人物卡阵营/身份/性别自动生成，重跑即可随数据更新）。

支持三个通道（--provider 选一）：

  1. pollinations   免密钥免费通道（默认）。限流 1 张/45 秒，偶发 503/402，
                    脚本自动退避重试。适合小批量/蹲守，1183 张约需 15 小时。
  2. dashscope      阿里通义万相（wanx2.1-t2i-turbo），出图质量与水墨契合度最好。
                    需 DASHSCOPE_API_KEY。约 0.14 元/张，全量 1183 张约 166 元（hero 37 张仅 5 元）。
  3. openai         任意 OpenAI 兼容图像接口（/v1/images/generations），
                    需 OPENAI_BASE_URL + OPENAI_API_KEY（+可选 OPENAI_MODEL）。

用法（在本项目根目录下）：
  python3 scripts/gen_ink_ai.py --all                 # 全部 1183 人（断点续跑）
  python3 scripts/gen_ink_ai.py --tier hero           # 37 位主角（提及>=150 或 verified）
  python3 scripts/gen_ink_ai.py --tier major          # +250 位要角（提及>=15）
  python3 scripts/gen_ink_ai.py --tier hero --tier major   # 两层
  python3 scripts/gen_ink_ai.py cao_cao guan_yu       # 指定 id
  python3 scripts/gen_ink_ai.py --all --provider dashscope
  python3 scripts/gen_ink_ai.py --all --limit 20      # 只补前 20 张缺的

脚本断点续跑：已存在的 png 自动跳过（--force 覆盖）。
失败不落地，反复重跑即可补缺。

跑完后无需改前端：build.py 会自动扫描 avatars 目录并注入白名单，
重新 python3 scripts/build.py 即生效。
"""
import argparse
import base64
import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, 'build', 'avatars_manifest.json')
OUT = os.path.join(ROOT, 'app', 'assets', 'avatars')

# 统一风格锚：强调「全身、头顶到脚完整入画、纯纸底」
STYLE_SUFFIX = ('。全身像构图居中，人物完整入画，头顶到双脚都在画面内，'
                '背景纯宣纸白，无文字无边框无印章，淡墨晕染，笔意疏朗留白')


# ---------------------------------------------------------------- pollinations
def gen_pollinations(prompt, out_path, tries=8):
    prompt = prompt + STYLE_SUFFIX
    url = ('https://image.pollinations.ai/prompt/' + urllib.parse.quote(prompt) +
           '?width=832&height=1216&nologo=true&model=flux&enhance=false&seed='
           + str(abs(hash(prompt)) % 9999))
    delay = 20
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=150) as r:
                data = r.read()
            if len(data) > 20000:
                Image.open(io.BytesIO(data)).convert('RGB').save(out_path)
                return True
            print(f'    返回体过小 {len(data)}B')
        except Exception as e:
            print(f'    try{k+1} {type(e).__name__}: {str(e)[:70]}')
        time.sleep(delay)
        delay = min(delay + 20, 120)
    return False


# ------------------------------------------------------------------- dashscope
def gen_dashscope(prompt, out_path, tries=4):
    key = os.environ['DASHSCOPE_API_KEY']
    body = json.dumps({
        'model': 'wanx2.1-t2i-turbo',
        'input': {'prompt': prompt + STYLE_SUFFIX, 'size': '768*1152', 'n': 1},
        'parameters': {'seed': abs(hash(prompt)) % 99999},
    }).encode()
    for k in range(tries):
        try:
            req = urllib.request.Request(
                'https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis',
                data=body, method='POST',
                headers={'Authorization': 'Bearer ' + key,
                         'Content-Type': 'application/json',
                         'X-DashScope-Async': 'enable'})
            with urllib.request.urlopen(req, timeout=60) as r:
                task = json.load(r)['output']['task_id']
            # 轮询异步任务
            for _ in range(40):
                time.sleep(3)
                q = urllib.request.Request(
                    'https://dashscope.aliyuncs.com/api/v1/tasks/' + task,
                    headers={'Authorization': 'Bearer ' + key})
                with urllib.request.urlopen(q, timeout=30) as r:
                    st = json.load(r)['output']
                if st['task_status'] == 'SUCCEEDED':
                    img_url = st['results'][0]['url']
                    with urllib.request.urlopen(img_url, timeout=60) as r:
                        Image.open(io.BytesIO(r.read())).convert('RGB').save(out_path)
                    return True
                if st['task_status'] == 'FAILED':
                    raise RuntimeError(st.get('message', 'task failed'))
            raise RuntimeError('poll timeout')
        except KeyError:
            raise          # 配置错误直接抛，不重试
        except Exception as e:
            print(f'    try{k+1} {type(e).__name__}: {str(e)[:70]}')
            time.sleep(10)
    return False


# ---------------------------------------------------------------------- openai
def gen_openai(prompt, out_path, tries=4):
    base = os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1').rstrip('/')
    key = os.environ['OPENAI_API_KEY']
    model = os.environ.get('OPENAI_MODEL', 'gpt-image-1')
    body = json.dumps({'model': model, 'prompt': prompt + STYLE_SUFFIX,
                       'size': '1024x1536', 'n': 1}).encode()
    for k in range(tries):
        try:
            req = urllib.request.Request(
                base + '/images/generations', data=body, method='POST',
                headers={'Authorization': 'Bearer ' + key,
                         'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=180) as r:
                resp = json.load(r)
            d = resp['data'][0]
            if d.get('b64_json'):
                raw = base64.b64decode(d['b64_json'])
            else:
                with urllib.request.urlopen(d['url'], timeout=60) as r:
                    raw = r.read()
            Image.open(io.BytesIO(raw)).convert('RGB').save(out_path)
            return True
        except KeyError:
            raise
        except Exception as e:
            print(f'    try{k+1} {type(e).__name__}: {str(e)[:70]}')
            time.sleep(15)
    return False


GENS = {'pollinations': gen_pollinations,
        'dashscope': gen_dashscope,
        'openai': gen_openai}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ids', nargs='*')
    ap.add_argument('--all', action='store_true', help='全部 1183 人')
    ap.add_argument('--tier', action='append', default=[],
                    help='按 tier 过滤: hero / major / minor，可重复指定')
    ap.add_argument('--limit', type=int, help='最多处理 N 张（按清单顺序取缺的）')
    ap.add_argument('--provider', default='pollinations', choices=list(GENS))
    ap.add_argument('--dry-run', action='store_true', help='只列出将要生成的条目，不出图')
    ap.add_argument('--force', action='store_true', help='覆盖已存在文件')
    ap.add_argument('--interval', type=float, default=0,
                    help='每张之间的额外间隔秒数（免费通道建议 48）')
    a = ap.parse_args()

    man = json.load(open(MANIFEST, encoding='utf-8'))
    by_id = {m['id']: m for m in man}
    if a.all:
        sel = man
    elif a.tier:
        sel = [m for m in man if m['tier'] in a.tier]
    elif a.ids:
        sel = [by_id[i] for i in a.ids if i in by_id] or sys.exit('id 不在清单中')
    else:
        sys.exit('用法: --all / --tier hero / 直接给 id')

    todo = []
    for m in sel:
        p = os.path.join(OUT, m['id'] + '.png')
        if a.force or not os.path.exists(p):
            todo.append(m)
    if a.limit:
        todo = todo[:a.limit]
    print(f'通道 {a.provider} · 待生成 {len(todo)}/{len(sel)} 张'
          + (f' · 已存在 {len(sel)-len(todo)} 张（--force 可覆盖）' if todo != sel else ''))
    if a.dry_run:
        for m in todo:
            print(f'  [{m["tier"]}] {m["name"]} -> {m["out"]}')
        sys.exit(0)

    gen = GENS[a.provider]
    ok = fail = 0
    for i, m in enumerate(todo):
        out_path = os.path.join(OUT, m['id'] + '.png')
        print(f'[{i+1}/{len(todo)}] {m["name"]} ({m["id"]})')
        if a.dry_run:
            print(f'    prompt: {m["prompt"][:70]}...')
            continue
        try:
            good = gen(m['prompt'], out_path)   # 风格锚由各 provider 内部追加
        except KeyError as e:
            sys.exit(f'缺少环境变量 {e} —— 请先 export 对应 API key')
        if good:
            ok += 1
            print('    ✓ 保存', os.path.basename(out_path))
        else:
            fail += 1
            print('    ✗ 失败，跳过（重跑本脚本可补）')
        if i < len(todo) - 1 and a.interval:
            time.sleep(a.interval)
    print(f'完成 {ok}/{len(todo)}，失败 {fail}')


if __name__ == '__main__':
    main()
