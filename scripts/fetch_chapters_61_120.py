# -*- coding: utf-8 -*-
"""抓取《三国演义》第 61–120 回原文（sanguo.5000yan.com，第 N 回 = 964+N.html）。
在 fetch_chapters.py 基础上放宽结尾断言（后 60 回结尾句式多变），并顺手抓回目标题，
汇总打印成章目索引 JSON（供人工核对后并入 data/chapters.json）。"""
import io, os, re, json, time, urllib.request

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'source')
END_RE = re.compile(r'(且[听看]下[文回]分解。|下文便[见晓]。|下回便见。|未识[、。].{0,30}$|毕竟.{0,20}如何，?且听下回.{0,8}。)$')
# 第 120 回是全书终章，以古风收束而非套语
END120 = re.compile(r'后人凭吊空牢骚。$')
# 站点 h1 自身截断的标题，按通行毛本回目补正
TITLE_FIX = {
    106: '公孙渊兵败死襄平 司马懿诈病赚曹爽',
    119: '假投降巧计成虚话 再受禅依样画葫芦',
    120: '荐杜预老将献新谋 降孙皓三分归一统',
}


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8', errors='ignore')


def get_title(html):
    m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
    if not m:
        m = re.search(r'<title>([^<_]+)', html)
    t = (m.group(1) if m else '').strip()
    t = re.sub(r'_.*$', '', t)
    t = re.sub(r'^第[一二三四五六七八九十百零\d]+回\s*', '', t)
    return t.replace('\u3000', ' ').strip()


def clean(html):
    html = re.sub(r'<a [^>]*>([^<]*)</a>', r'\1', html)
    m = None
    for pat in (r'<div[^>]*class="[^"]*(?:show_txt|content|show)[^"]*"[^>]*>(.*?)</div>',
                r'<article[^>]*>(.*?)</article>'):
        mm = re.search(pat, html, re.S)
        if mm and ('却说' in mm.group(1) or '且说' in mm.group(1) or '话说' in mm.group(1)):
            m = mm
            break
    body = m.group(1) if m else html
    body = re.sub(r'<script.*?</script>', '', body, flags=re.S)
    body = re.sub(r'<style.*?</style>', '', body, flags=re.S)
    body = re.sub(r'<br[^>]*>|</p>|</div>|</h\d>', '\n', body, flags=re.I)
    body = re.sub(r'<[^>]+>', '', body)
    body = body.replace('&nbsp;', ' ').replace('&ldquo;', '"').replace('&rdquo;', '"')
    body = body.replace('&mdash;', '—').replace('&amp;', '&').replace('&gt;', '>').replace('&lt;', '<')
    keep, seen_body = [], False
    for ln in body.split('\n'):
        t = ln.strip()
        if not t:
            continue
        if re.search(r'5000言|5000yan|上一篇|下一篇|章节目录|小说推荐|www\.|https?:|版权|责任编辑|手机阅读|加入书签|错误报告|CHAPTER|在线阅读|无弹窗', t):
            continue
        if not seen_body:
            if re.match(r'^(?:第[一二三四五六七八九十百]+回|[一二三四五六七八九十百]{2,4}[、．.])', t):
                continue
            if '却说' in t or '且说' in t or '话说' in t or re.search(r'[。：]"?$', t):
                seen_body = True
            else:
                continue
        keep.append(t)
    return '\n\n'.join(keep) + '\n'


titles = {}
for no in range(61, 121):
    url = 'https://sanguo.5000yan.com/%d.html' % (964 + no)
    out = os.path.join(OUT, 'ch%03d.txt' % no)
    if os.path.exists(out) and os.path.getsize(out) > 8000:
        print('第%2d回 已存在，跳过' % no)
        continue
    try:
        html = fetch(url)
        title = get_title(html)
        txt = clean(html)
        assert len(txt) > 3500, '正文过短 %d' % len(txt)
        tail = txt.rstrip()[-30:]
        assert (END120.search(txt.rstrip()) if no == 120 else END_RE.search(txt.rstrip())), '结尾特征不符: ' + tail
        io.open(out, 'w', encoding='utf-8').write(txt)
        titles[no] = TITLE_FIX.get(no, title)
        print('第%2d回 ok %d 字 %s' % (no, len(txt), title))
    except Exception as e:
        print('第%2d回 FAIL %s' % (no, e))
    time.sleep(1.2)

# 汇总已抓全部（含历史）标题
have = sorted(int(f[2:5]) for f in os.listdir(OUT) if re.match(r'ch\d{3}\.txt$', f) and int(f[2:5]) >= 61)
if have and len(have) == 60:
    io.open(os.path.join(OUT, 'titles_61_120.json'), 'w', encoding='utf-8').write(
        json.dumps(titles, ensure_ascii=False, indent=1))
    print('标题索引写出 titles_61_120.json：%d 条' % len(titles))
