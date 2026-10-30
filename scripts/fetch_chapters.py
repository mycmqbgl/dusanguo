#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""抓取《三国演义》第 11–20 回原文（sanguo.5000yan.com，第 N 回 = 964+N.html）。
清洗：去站点剧情简介 / 正文内嵌 <a> 链接 / 广告段；输出 build 段落格式（空行分段）。"""
import io, os, re, time, urllib.request

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
OUT = 'data/source'
os.makedirs(OUT, exist_ok=True)

def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8', errors='ignore')

def clean(html):
    # 去内嵌链接
    html = re.sub(r'<a [^>]*>([^<]*)</a>', r'\1', html)
    # 取正文容器（站点用 .show / .content 类，逐个尝试）
    m = None
    for pat in (r'<div[^>]*class="[^"]*(?:show_txt|content|show)[^"]*"[^>]*>(.*?)</div>',
                r'<article[^>]*>(.*?)</article>'):
        mm = re.search(pat, html, re.S)
        if mm and '却说' in mm.group(1):
            m = mm
            break
    body = m.group(1) if m else html
    # 块级标签 → 换行；行内标签 → 直接删除（否则段落被切碎）
    body = re.sub(r'<script.*?</script>', '', body, flags=re.S)
    body = re.sub(r'<style.*?</style>', '', body, flags=re.S)
    body = re.sub(r'<br[^>]*>|</p>|</div>|</h\d>', '\n', body, flags=re.I)
    body = re.sub(r'<[^>]+>', '', body)
    body = body.replace('&nbsp;', ' ').replace('&ldquo;', '"').replace('&rdquo;', '"')
    body = body.replace('&mdash;', '—').replace('&amp;', '&').replace('&gt;', '>').replace('&lt;', '<')
    # 逐行清洗
    keep, seen_body = [], False
    for ln in body.split('\n'):
        t = ln.strip()
        if not t:
            continue
        # 站点噪声
        if re.search(r'5000言|5000yan|上一篇|下一篇|章节目录|小说推荐|www\.|https?:|版权|责任编辑|手机阅读|加入书签|错误报告|CHAPTER|在线阅读|无弹窗', t):
            continue
        # 剧情简介段（站点在正文前放本章概要，特征：短句概述+「这一回」）
        if not seen_body:
            if re.match(r'^(?:第[一二三四五六七八九十百]+回|[一二三四五六七八九十百]{2,4}[、．.])', t):
                continue  # 标题行
            if '却说' in t or '且说' in t or re.search(r'[。：]"?$', t):
                seen_body = True
            else:
                continue  # 简介行未出现正文特征前丢弃
        keep.append(t)
    return '\n\n'.join(keep) + '\n'

for no in range(11, 21):
    url = 'https://sanguo.5000yan.com/%d.html' % (964 + no)
    out = os.path.join(OUT, 'ch%03d.txt' % no)
    if os.path.exists(out) and os.path.getsize(out) > 8000:
        print('第%2d回 已存在，跳过' % no)
        continue
    try:
        txt = clean(fetch(url))
        # 基本断言：正文长度合理、起止特征
        assert len(txt) > 3500, '正文过短 %d' % len(txt)
        assert txt.rstrip().endswith('且听下文分解。'), '结尾特征不符: ' + txt[-60:]
        io.open(out, 'w', encoding='utf-8').write(txt)
        print('第%2d回 ok %d 字' % (no, len(txt)))
    except Exception as e:
        print('第%2d回 FAIL %s' % (no, e))
    time.sleep(1.2)
