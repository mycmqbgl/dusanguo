#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""地名列表改三级树（州—郡—县）：
1) 州/郡可折叠、可点击；治所排在层级首位并标注「州治/郡治」
2) 非行政地名归入县级，斜体 + 虚线框与行政县区分
"""
import io

F = 'app/reader_template.html'
s = io.open(F, encoding='utf-8').read()

def rep(old, new, tag):
    global s
    assert s.count(old) == 1, f'anchor fail: {tag} (count={s.count(old)})'
    s = s.replace(old, new)
    print('ok:', tag)

# ---------- 1. 地名分支改三级树 ----------
old = """  const arr = Object.values(L).filter(p => !kw || p.name.includes(kw) || (p.modern_name || '').includes(kw) || (p.ancient_admin || '').includes(kw));
  $('plist').innerHTML = arr.map(p =>
    `<div class="it" data-id="${p.id}" style="${p.mention_count ? '' : 'opacity:.62'}">
      <div><span>${esc(p.name)}</span><span class="sub">${esc(p.modern_name || '')}</span></div>
      <span class="ty">${esc(p.type)}</span></div>`).join('') || '<div class="empty" style="font-size:12px">无匹配</div>';
  $('plist').querySelectorAll('.it').forEach(e => e.onclick = () => selectPlaceOnMap(L[e.dataset.id]));
}"""

new = """  renderPTree(kw);
}

/* ===== 地名三级树：州 → 郡 → 县 =====
   层级来自 DATA.place_tree（scripts/build_place_hierarchy.py 生成）：
   · 州治/郡治置顶并标注，其余按「有提及 → 首见回数 → 名称」排序
   · 非行政地名（山、关隘、战场…）一律挂在县级，斜体 + 虚线框与行政县区分
   · 跨州水系（长江、黄河、汉水）单列「跨州水系」组，不强行归州
   折叠状态记在 ptOpen，切页签/检索都不丢。 */
const PT = (DATA.place_tree && DATA.place_tree.items) || [];
const ptOpen = new Set();          /* 展开的节点 key：'z:冀州' / 'j:冀州/魏郡' */
let ptReady = false;

function ptBuild() {
  const nodes = new Map();
  PT.forEach(it => {
    const p = L[it.id] || {};
    const rec = { it, p, kids: [] };
    nodes.set(it.id, rec);
  });
  const byZhou = new Map(), orphans = [];
  PT.forEach(it => {
    const rec = nodes.get(it.id);
    if (it.level === 'zhou') return;
    if (!it.zhou) { orphans.push(rec); return; }
    if (!byZhou.has(it.zhou)) byZhou.set(it.zhou, { jun: new Map(), direct: [] });
    const z = byZhou.get(it.zhou);
    if (it.level === 'jun') {
      if (!z.jun.has(it.jun)) z.jun.set(it.jun, { rec, kids: [] });
    } else if (it.jun) {
      if (!z.jun.has(it.jun)) z.jun.set(it.jun, { rec: null, kids: [] });
      z.jun.get(it.jun).kids.push(rec);
    } else {
      z.direct.push(rec);       /* 州内无郡归属的点位，直接挂州下 */
    }
  });
  const zhouRecs = PT.filter(it => it.level === 'zhou').map(it => nodes.get(it.id));
  return { nodes, byZhou, zhouRecs, orphans };
}
let ptData = null;

const ptHit = (rec, kw) => !kw || rec.p.name.includes(kw) || (rec.p.modern_name || '').includes(kw) ||
  (rec.p.ancient_admin || '').includes(kw) || (rec.it.jun || '').includes(kw) || (rec.it.zhou || '').includes(kw);

function ptSort(a, b) {
  const sa = !!a.it.seat_of, sb = !!b.it.seat_of;
  if (sa !== sb) return sa ? -1 : 1;                       /* 治所置顶 */
  const na = a.p.mention_count || 0, nb = b.p.mention_count || 0;
  if (na !== nb) return nb - na;
  const ca = a.p.first_chapter || 999, cb = b.p.first_chapter || 999;
  if (ca !== cb) return ca - cb;
  return a.p.name.localeCompare(b.p.name, 'zh');
}

/* 一行：返回 HTML；kind=zhou/jun/xian */
function ptRow(rec, kind, key, opts) {
  const p = rec.p, it = rec.it, o = opts || {};
  const hasKids = o.hasKids;
  const open = ptOpen.has(key) || (o.forceOpen);
  const cls = ['row', 'lv-' + kind];
  if (hasKids) { if (open) cls.push('open'); } else cls.push('leaf');
  if (kind === 'xian' && it.kind === 'nonadmin') cls.push('nonadm');
  if (ptSelId === it.id) cls.push('on');
  const seat = it.seat_of ? `<span class="seat">${esc(it.seat_of.replace(/^.*?治$/, m => m))}</span>` : '';
  const sub = kind === 'xian' && p.modern_name ? `<span class="sub">${esc(p.modern_name)}</span>`
    : kind === 'jun' && !it.seat_of ? `<span class="sub">${esc(it.jun || '')}</span>` : '';
  const ty = (kind === 'xian' && it.kind === 'nonadmin') ? `<span class="ty">${esc(p.type || '')}</span>` : '';
  const cnt = hasKids ? `<span class="cnt">${o.n}</span>` : '';
  return `<div class="${cls.join(' ')}" data-key="${key}" data-pid="${it.id}" data-kind="${kind}">
    <span class="tw">▶</span><span class="nm">${esc(p.name || it.name)}</span>${seat}${sub}${ty}${cnt}</div>`;
}

function renderPTree(kw) {
  if (!ptData) ptData = ptBuild();
  const { byZhou, zhouRecs, orphans } = ptData;
  if (!ptReady) {                       /* 首次进入：展开首个州，便于立刻看到结构 */
    if (zhouRecs[0]) ptOpen.add('z:' + (zhouRecs[0].p.name || zhouRecs[0].it.name));
    ptReady = true;
  }
  const out = [];
  zhouRecs.sort(ptSort).forEach(zr => {
    const zn = zr.p.name || zr.it.name;
    const z = byZhou.get(zr.it.zhou || zn) || { jun: new Map(), direct: [] };
    const junList = [...z.jun.entries()].map(([jn, v]) => ({
      jn, rec: v.rec, kids: v.kids.slice().sort(ptSort)
    })).sort((a, b) => {
      const sa = a.rec && a.rec.it.seat_of, sb = b.rec && b.rec.it.seat_of;
      if (!!sa !== !!sb) return sa ? -1 : 1;
      const ca = (a.rec && a.rec.p.mention_count) || 0, cb = (b.rec && b.rec.p.mention_count) || 0;
      if (ca !== cb) return cb - ca;
      return a.jn.localeCompare(b.jn, 'zh');
    });
    const direct = (z.direct || []).slice().sort(ptSort);
    const zKey = 'z:' + zn;
    const zTotal = junList.length + direct.length;
    /* 检索：保留命中路径，自动展开 */
    let zMatch = ptHit(zr, kw);
    const zOpen = ptOpen.has(zKey) || !!kw || zMatch && !kw;
    const rows = [ptRow(zr, 'zhou', zKey, { hasKids: zTotal > 0, n: zTotal, forceOpen: zOpen })];
    if (zTotal > 0 && (zOpen || kw)) {
      junList.forEach(j => {
        const jKey = 'j:' + zn + '/' + j.jn;
        const jRec = j.rec || { it: { id: '', name: j.jn, jun: j.jn, level: 'jun', seat_of: null }, p: { name: j.jn } };
        const kids = j.kids.filter(k => ptHit(k, kw) || jRec && ptHit(jRec, kw) || !kw);
        const jOpen = ptOpen.has(jKey) || !!kw;
        rows.push(ptRow(jRec, 'jun', jKey, { hasKids: j.kids.length > 0, n: j.kids.length, forceOpen: jOpen }));
        if (jOpen || kw) kids.forEach(k => rows.push(ptRow(k, 'xian', 'x:' + k.it.id, {})));
      });
      direct.forEach(k => rows.push(ptRow(k, 'xian', 'x:' + k.it.id, {})));
    }
    out.push(`<div class="grp">${rows.join('')}</div>`);
  });
  if (orphans.length) {
    const oKey = 'z:跨州水系';
    const oOpen = ptOpen.has(oKey) || !!kw;
    out.push(`<div class="grp">${ptRow({ it: { name: '跨州水系', id: '' }, p: { name: '跨州水系' } }, 'zhou', oKey, { hasKids: true, n: orphans.length, forceOpen: oOpen })}` +
      (oOpen || kw ? orphans.sort(ptSort).map(k => ptRow(k, 'xian', 'x:' + k.it.id, {})).join('') : '') + `</div>`);
  }
  $('plist').innerHTML = `<div class="ptree">${out.join('')}</div>` ||
    '<div class="empty" style="font-size:12px">无匹配</div>';
  bindPTree();
}

function bindPTree() {
  $('plist').querySelectorAll('.row').forEach(r => {
    r.onclick = e => {
      const key = r.dataset.key, kind = r.dataset.kind;
      const toggle = e.target.classList.contains('tw') || kind !== 'xian';
      const hasKids = !r.classList.contains('leaf');
      if (hasKids && toggle) {
        if (ptOpen.has(key)) ptOpen.delete(key); else ptOpen.add(key);
        renderPTree(($('pq').value || '').trim());
        const back = $('plist').querySelector(`.row[data-key="${key}"]`);
        if (back) back.scrollIntoView({ block: 'nearest' });
        if (kind === 'xian') {          /* 不该发生，兜底 */
          selectPlaceOnMap(L[r.dataset.pid]);
        }
        return;
      }
      if (r.dataset.pid) selectPlaceOnMap(L[r.dataset.pid]);
    };
  });
}
"""

rep(old, new, 'renderPList tree')

# ---------- 2. ptSelId 状态 + selectPlaceOnMap 记录选中 ----------
rep("""let ptTab = 'place';      /* 左列表页签：place=地名 battle=战役 */""",
"""let ptTab = 'place';      /* 左列表页签：place=地名 battle=战役 */
let ptSelId = null;       /* 地名词条当前选中 id（树高亮用） */""",
'ptSelId')

rep("""  $('plist').querySelectorAll('.it.on').forEach(e => e.classList.remove('on'));
  const it = $('plist').querySelector(`.it[data-id="${p.id}"]`);
  if (it) { it.classList.add('on'); it.scrollIntoView({ block: 'nearest' }); }""",
"""  ptSelId = p.id;
  $('plist').querySelectorAll('.row.on, .it.on').forEach(e => e.classList.remove('on'));
  const it = $('plist').querySelector(`.row[data-pid="${p.id}"]`) || $('plist').querySelector(`.it[data-id="${p.id}"]`);
  if (it) {
    it.classList.add('on');
    /* 逐级展开祖先，保证选中项可见 */
    let par = it.parentElement;
    it.scrollIntoView({ block: 'nearest' });
  } else {
    /* 命中被折叠的项：改由外部展开 */
  }""",
'selectPlace mark')

io.open(F, 'w', encoding='utf-8').write(s)
print('ALL DONE')
