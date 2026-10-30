#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""事件/地图改造：
1) 战役卡 minimap：悬停提示"单击放大"，点击进全屏推演页（含播放按钮）
2) 地图页三栏：左列表加 地名/战役 页签（点战役在主图播放战线推演）、中地图（可缩放）、右详情栏
"""
import io, sys

F = 'app/reader_template.html'
s = io.open(F, encoding='utf-8').read()

def rep(old, new, tag):
    global s
    assert s.count(old) == 1, f'anchor fail: {tag} (count={s.count(old)})'
    s = s.replace(old, new)
    print('ok:', tag)

# ---------- 1. CSS ----------
rep("""  .plist .dt .lit{color:var(--accent)}""",
"""  .plist .dt .lit{color:var(--accent)}
  /* 左列表（地名/战役页签）与右侧详情栏 */
  .plist.left{border-left:0;border-right:1px solid var(--line)}
  .plist .tabs{display:flex;border-bottom:1px solid var(--line);flex:none}
  .plist .tabs button{flex:1;border:0;background:transparent;font-family:inherit;font-size:12px;
    color:var(--ink2);padding:8px 0;cursor:pointer;border-bottom:2px solid transparent}
  .plist .tabs button:hover{background:#f4ead9}
  .plist .tabs button.on{color:var(--accent);border-bottom-color:var(--accent);background:#fbf7ee}
  /* 战役卡小图：悬停提示单击放大 */
  .bwrap{position:relative;cursor:zoom-in}
  .bwrap .zhint{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);
    background:rgba(30,24,14,.8);color:#f5edda;font-size:12.5px;padding:7px 15px;border-radius:16px;
    opacity:0;transition:opacity .18s;pointer-events:none;white-space:nowrap}
  .bwrap:hover .zhint{opacity:1}
  /* 全屏战线推演页 */
  .bmask{position:fixed;inset:0;z-index:300;background:rgba(22,17,10,.94);display:none;flex-direction:column}
  .bmask.on{display:flex}
  .bmask .btop{flex:none;display:flex;align-items:center;gap:12px;padding:10px 18px;color:#f5edda}
  .bmask .btop b{font-weight:400;font-size:15px}
  .bmask .btop .btn{background:#3a3125;color:#f5edda;border:1px solid #5c4f39;cursor:pointer}
  .bmask svg{flex:1;min-height:0;width:100%}
  .bmask .bdesc{flex:none;min-height:46px;padding:9px 18px 13px;color:#e8ddc4;font-size:12.5px;line-height:1.7}
  /* 地图页底部战线推演条 */
  .bmpbar{position:absolute;left:50%;bottom:14px;transform:translateX(-50%);display:none;
    align-items:center;gap:10px;background:rgba(251,247,238,.96);border:1px solid var(--line);
    border-radius:6px;padding:7px 13px;font-size:12px;max-width:76%;box-shadow:0 2px 10px rgba(40,30,15,.18)}
  .bmpbar b{font-weight:400;color:var(--accent);white-space:nowrap}
  .bmpbar .btn{cursor:pointer}
  .bmpbar .d{color:#4a443b;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:400px}""",
'css')

# ---------- 2. 地图页 HTML：三栏 ----------
rep("""    <div class="view" id="v-places">
      <div class="mapsplit">
        <div class="mapstage">
          <svg id="bigmap" preserveAspectRatio="xMidYMid meet"></svg>
          <div class="mzoom">
            <button id="mzo" title="缩小">−</button>
            <div class="lb" id="mzlb">1.00×</div>
            <button id="mzi" title="放大">＋</button>
            <button class="fit" id="mzfit" title="回到全图">全图</button>
          </div>
          <div class="maphint">滚轮 / 双击 <b>缩放</b>　·　拖拽 <b>平移</b>　·　点击点位 <b>定位</b></div>
        </div>
        <div class="plist">
          <div class="sr"><input id="pq" placeholder="检索地名 / 今地"></div>
          <div class="bd" id="plist"></div>
          <div class="dt" id="pdetail"><div class="e">点击列表或地图上的点位，此处显示该地详情。</div></div>
        </div>
      </div>
    </div>""",
"""    <div class="view" id="v-places">
      <div class="mapsplit">
        <div class="plist left">
          <div class="tabs" id="ptabs"><button data-t="place" class="on">地名</button><button data-t="battle">战役</button></div>
          <div class="sr"><input id="pq" placeholder="检索地名 / 今地 / 战役"></div>
          <div class="bd" id="plist"></div>
        </div>
        <div class="mapstage">
          <svg id="bigmap" preserveAspectRatio="xMidYMid meet"></svg>
          <div class="mzoom">
            <button id="mzo" title="缩小">−</button>
            <div class="lb" id="mzlb">1.00×</div>
            <button id="mzi" title="放大">＋</button>
            <button class="fit" id="mzfit" title="回到全图">全图</button>
          </div>
          <div class="bmpbar" id="bmpbar">
            <b id="bmpname"></b><button class="btn" id="bmpplay">▶ 推演</button><span id="bmpn"></span><span class="d" id="bmpd"></span>
          </div>
          <div class="maphint">滚轮 / 双击 <b>缩放</b>　·　拖拽 <b>平移</b>　·　点击点位 <b>定位</b></div>
        </div>
        <div class="plist"><div class="dt" id="pdetail"><div class="e">点击左侧列表（地名 / 战役页签）或地图上的点位，此处显示详情。</div></div></div>
      </div>
    </div>""",
'v-places html')

# ---------- 3. 全屏推演页 HTML（挂在 mask 之后） ----------
rep("""<div class="mask" id="mask"><div class="card" id="card"></div></div>""",
"""<div class="mask" id="mask"><div class="card" id="card"></div></div>

<div class="bmask" id="bmask">
  <div class="btop"><b id="bmt"></b><span class="grow"></span>
    <button class="btn" id="bmp">▶ 推演战线</button>
    <button class="btn" id="bmx">✕ 关闭</button></div>
  <svg id="bmap" preserveAspectRatio="xMidYMid meet"></svg>
  <div class="bdesc" id="bsd"></div>
</div>""",
'bmask html')

# ---------- 4. 战役卡 minimap 加放大提示 ----------
rep("""  h += `<div class="sec"><h4>战线推进 <span class="locked">比例锁定</span></h4><svg class="minimap" id="bm" preserveAspectRatio="xMidYMid meet"></svg>
    <div class="playbar"><button class="btn" id="play">▶ 推演战线</button><span class="nsteps" id="nst"></span></div>
    <div class="stepdesc" id="sd"></div></div>`;""",
"""  h += `<div class="sec"><h4>战线推进 <span class="locked">比例锁定</span></h4>
    <div class="bwrap"><svg class="minimap" id="bm" preserveAspectRatio="xMidYMid meet"></svg>
      <div class="zhint">🔍 单击放大 · 可播放推演</div></div>
    <div class="playbar"><button class="btn" id="play">▶ 推演战线</button><span class="nsteps" id="nst"></span></div>
    <div class="stepdesc" id="sd"></div></div>`;""",
'bm wrap')

# ---------- 5. 提炼推演场景构建器 + 重写 openBattle 内部 + 全屏页 ----------
rep("""  /* 战线图：底图来自内核，节点走同一套「data-sz 屏幕像素」协议；
     镜头由脚本推进（锁定），先看全局，再逐年推近。 */
  const svg = $('bm');
  svg._refs = MC.drawBase(svg, C, GEO);
  const gPath = el('g', {}), gLive = el('g', {});
  svg.append(gPath, gLive);
  const N = b.front_line;
  const XY = N.map(n => ({ x: n.pixel_x, y: n.pixel_y }));
  const BZ = 7;
  const xs = N.map(n => n.pixel_x), ys = N.map(n => n.pixel_y);
  const midX = (Math.min(...xs) + Math.max(...xs)) / 2, midY = (Math.min(...ys) + Math.max(...ys)) / 2;
  const fitZ = Math.min(C.w / (Math.max(...xs) - Math.min(...xs) + 180),
                         C.h / (Math.max(...ys) - Math.min(...ys) + 180), 9);
  MC.battlePath(gPath, XY, { ghost: true, sz: 3, dash: '9 7' });
  let i = 0;
  const draw = upto => {
    gLive.innerHTML = '';
    const pts = XY.slice(0, upto + 1);
    const pz = MC.displayZoom(svg, C, BZ);
    if (pts.length > 1) MC.battlePath(gLive, pts, { sz: 2.4 });
    pts.forEach((q, k) => {
      MC.battleNode(gLive, q, pz, {
        past: k !== upto, up: k % 2,
        label: N[k].time_seq + '. ' + N[k].label
      });
    });
    const n = N[upto];
    svg.setAttribute('viewBox', MC.viewBoxStr(n.pixel_x, n.pixel_y, BZ, C.w, C.h));
    MC.decorScale(svg._refs, svg, C, BZ);
    MC.applySpacing(gPath, pz);
    $('nst').textContent = (upto + 1) + ' / ' + N.length;
    $('sd').innerHTML = `<b style="color:var(--accent)">${n.time_seq}. ${esc(n.kind)}·${esc(n.label)}</b>　${esc(n.desc)}`;
  };
  const fit = () => {
    svg.setAttribute('viewBox', MC.viewBoxStr(midX, midY, fitZ, C.w, C.h));
    const pz = MC.decorScale(svg._refs, svg, C, fitZ);
    MC.applySpacing(gPath, pz);
    return pz;
  };
  fit();
  MC.lockZoom(svg);            // 战线图镜头由脚本推进，用户不能缩放
  draw(0);
  fit();
  $('play').onclick = () => {
    if (timer) { clearInterval(timer); timer = null; }
    i = 0; draw(0);
    timer = setInterval(() => { i++; if (i >= N.length) { clearInterval(timer); timer = null; return; } draw(i); }, 1200);
  };
}
window.openBattle = openBattle;""",
"""  /* 先全局，再推演（小图锁定镜头）；单击放大进全屏推演页 */
  const sc = buildBattleScene($('bm'), b, (i, n) => {
    $('nst').textContent = (i + 1) + ' / ' + sc.N.length;
    $('sd').innerHTML = `<b style="color:var(--accent)">${n.time_seq}. ${esc(n.kind)}·${esc(n.label)}</b>　${esc(n.desc)}`;
  });
  MC.lockZoom($('bm'));        // 小图镜头由脚本推进，用户不能缩放
  sc.draw(0); sc.fit();
  let bi = 0;
  $('play').onclick = () => {
    if (timer) { clearInterval(timer); timer = null; }
    bi = 0; sc.draw(0);
    timer = setInterval(() => { bi++; if (bi >= sc.N.length) { clearInterval(timer); timer = null; return; } sc.draw(bi); }, 1200);
  };
  $('bm').onclick = () => openBattleStage(id);
}

/* ===== 战线推演场景构建器：卡片小图 / 全屏页共用（底图 + 幽灵全程线 + 实况层） =====
   节点走同一套「data-sz 屏幕像素」协议；draw(upto) 镜头推进，fit() 回全局。 */
function buildBattleScene(svg, b, hook) {
  svg.innerHTML = '';
  svg._refs = MC.drawBase(svg, C, GEO);
  const gPath = el('g', {}), gLive = el('g', {});
  svg.append(gPath, gLive);
  const N = b.front_line;
  const XY = N.map(n => ({ x: n.pixel_x, y: n.pixel_y }));
  const BZ = 7;
  const xs = XY.map(q => q.x), ys = XY.map(q => q.y);
  const midX = (Math.min(...xs) + Math.max(...xs)) / 2, midY = (Math.min(...ys) + Math.max(...ys)) / 2;
  const fitZ = Math.min(C.w / (Math.max(...xs) - Math.min(...xs) + 180),
                         C.h / (Math.max(...ys) - Math.min(...ys) + 180), 9);
  MC.battlePath(gPath, XY, { ghost: true, sz: 3, dash: '9 7' });
  return {
    N, BZ, fitZ, midX, midY, gPath, gLive,
    draw(upto, z) {
      gLive.innerHTML = '';
      const pts = XY.slice(0, upto + 1);
      const zz = z || BZ;
      const pz = MC.displayZoom(svg, C, zz);
      if (pts.length > 1) MC.battlePath(gLive, pts, { sz: 2.4 });
      pts.forEach((q, k) => {
        MC.battleNode(gLive, q, pz, { past: k !== upto, up: k % 2, label: N[k].time_seq + '. ' + N[k].label });
      });
      svg.setAttribute('viewBox', MC.viewBoxStr(N[upto].pixel_x, N[upto].pixel_y, zz, C.w, C.h));
      MC.decorScale(svg._refs, svg, C, zz);
      MC.applySpacing(gPath, pz);
      if (hook) hook(upto, N[upto]);
    },
    fit() {
      svg.setAttribute('viewBox', MC.viewBoxStr(midX, midY, fitZ, C.w, C.h));
      const pz = MC.decorScale(svg._refs, svg, C, fitZ);
      MC.applySpacing(gPath, pz);
      return pz;
    }
  };
}

/* ===== 全屏战线推演页（卡片小图「单击放大」进入） ===== */
let stageTimer = null;
function stopStage() { if (stageTimer) { clearInterval(stageTimer); stageTimer = null; } }
function openBattleStage(id) {
  const b = BT.find(x => x.id === id);
  if (!b) return;
  stopBattleMapPlay();
  stopStage();
  $('bmt').textContent = b.name + ' · 战线推演';
  $('bsd').innerHTML = '<span style="opacity:.6">点「▶ 推演战线」逐步播放战线推进，每步自动推近镜头；看完点 ✕ 关闭。</span>';
  $('bmpn').textContent = '';
  $('bmask').classList.add('on');
  const sc = buildBattleScene($('bmap'), b, (i, n) => {
    $('bmpn').textContent = (i + 1) + ' / ' + sc.N.length;
    $('bsd').innerHTML = `<b style="color:#e0b25c">${n.time_seq}. ${esc(n.kind)}·${esc(n.label)}</b>　${esc(n.desc)}`;
  });
  sc.draw(0); sc.fit();
  let si = 0;
  $('bmp').onclick = () => {
    stopStage();
    si = 0; sc.draw(0);
    stageTimer = setInterval(() => { si++; if (si >= sc.N.length) { stopStage(); return; } sc.draw(si); }, 1200);
  };
}
$('bmx').onclick = () => { stopStage(); $('bmask').classList.remove('on'); };
document.addEventListener('keydown', e => { if (e.key === 'Escape' && $('bmask').classList.contains('on')) $('bmx').onclick(); });
window.openBattleStage = openBattleStage;""",
'scene+stage')

# ---------- 6. renderPlaces：进入时清战役覆盖层；onApply 记录 pz 并重排战线 ----------
rep("""function renderPlaces() {
  $('side-hd').textContent = '地名';""",
"""function renderPlaces() {
  stopBattleMapPlay();
  $('side-hd').textContent = '地名';""",
'renderPlaces stop')

rep("""    onApply: (V, pz) => {
      dots.forEach(c => c.setAttribute('r', (c._r || 3.4) / pz));
      MC.decorScale(svg._refs, svg, C, V.s);
      const lb = $('mzlb'); if (lb) lb.textContent = V.s.toFixed(2) + '×';
    }""",
"""    onApply: (V, pz) => {
      if (MV) MV.pz = pz;
      dots.forEach(c => c.setAttribute('r', (c._r || 3.4) / pz));
      MC.decorScale(svg._refs, svg, C, V.s);
      if (BM && BM.gPath) { MC.applySpacing(BM.gPath, pz); MC.applySpacing(BM.gLive, pz); }
      const lb = $('mzlb'); if (lb) lb.textContent = V.s.toFixed(2) + '×';
    }""",
'onApply pz')

rep("""/* ===== 地图视图的缩放状态（仅此一处可缩放）：状态机交给 MapCore.createView ===== */
let MV = null;""",
"""/* ===== 地图视图的缩放状态（仅此一处可缩放）：状态机交给 MapCore.createView ===== */
let MV = null;
let BM = null;            /* 主图上正在推演的战役 {b,gPath,gLive,N,XY,i,timer,fitZ} */
let ptTab = 'place';      /* 左列表页签：place=地名 battle=战役 */""",
'mv/bm vars')

# ---------- 7. selectPlaceOnMap：点地名时停掉战役推演 ----------
rep("""function selectPlaceOnMap(p) {
  if (p.pixel_x == null) return;
  mvTo(p.pixel_x, p.pixel_y, zoomFor(p));""",
"""function selectPlaceOnMap(p) {
  if (p.pixel_x == null) return;
  stopBattleMapPlay();
  mvTo(p.pixel_x, p.pixel_y, zoomFor(p));""",
'selectPlace stop')

# ---------- 8. renderPList：页签化（地名/战役） ----------
rep("""function renderPList() {
  const kw = ($('pq').value || '').trim();
  const arr = Object.values(L).filter(p => !kw || p.name.includes(kw) || (p.modern_name || '').includes(kw) || (p.ancient_admin || '').includes(kw));""",
"""function renderPList() {
  const kw = ($('pq').value || '').trim();
  if (ptTab === 'battle') {
    const arr = BT.filter(b => !kw || b.name.includes(kw) || (b.place_name || '').includes(kw) ||
      ((EV.find(e => e.id === b.event_id) || { name: '' }).name || '').includes(kw));
    $('plist').innerHTML = arr.map(b =>
      `<div class="it" data-bid="${b.id}">
        <div><span>${esc(b.name)}</span><span class="sub">${esc(b.place_name || '')}</span></div>
        <span class="ty">${b.year} 年</span></div>`).join('') || '<div class="empty" style="font-size:12px">无匹配</div>';
    $('plist').querySelectorAll('.it').forEach(e => e.onclick = () => selectBattleOnMap(BT.find(x => x.id === e.dataset.bid)));
    return;
  }
  const arr = Object.values(L).filter(p => !kw || p.name.includes(kw) || (p.modern_name || '').includes(kw) || (p.ancient_admin || '').includes(kw));""",
'renderPList tabs')

# ---------- 9. 主图战线推演函数（接在 renderPList 之后） ----------
rep("""  $('plist').querySelectorAll('.it').forEach(e => e.onclick = () => selectPlaceOnMap(L[e.dataset.id]));
}""",
"""  $('plist').querySelectorAll('.it').forEach(e => e.onclick = () => selectPlaceOnMap(L[e.dataset.id]));
}

/* ===== 地图页 · 战役战线推演（左列表「战役」页签点入，主图播放） ===== */
function drawMapStep(i) {
  if (!BM) return;
  BM.i = i;
  BM.gLive.innerHTML = '';
  const pz = (MV && MV.pz) ? MV.pz : 1;
  const pts = BM.XY.slice(0, i + 1);
  if (pts.length > 1) MC.battlePath(BM.gLive, pts, { sz: 2.4 });
  pts.forEach((q, k) => MC.battleNode(BM.gLive, q, pz,
    { past: k !== i, up: k % 2, label: BM.N[k].time_seq + '. ' + BM.N[k].label }));
  const n = BM.N[i];
  $('bmpn').textContent = (i + 1) + ' / ' + BM.N.length;
  $('bmpd').textContent = n.time_seq + '. ' + n.kind + '·' + n.label + '　' + n.desc;
}
function selectBattleOnMap(b) {
  stopBattleMapPlay();
  const svg = $('bigmap');
  if (!svg._refs) return;
  const N = b.front_line;
  const XY = N.map(n => ({ x: n.pixel_x, y: n.pixel_y }));
  const xs = XY.map(q => q.x), ys = XY.map(q => q.y);
  const midX = (Math.min(...xs) + Math.max(...xs)) / 2, midY = (Math.min(...ys) + Math.max(...ys)) / 2;
  const fitZ = Math.min(C.w / (Math.max(...xs) - Math.min(...xs) + 160),
                         C.h / (Math.max(...ys) - Math.min(...ys) + 160), 7);
  const gPath = el('g', {}), gLive = el('g', {});
  svg.append(gPath, gLive);
  MC.battlePath(gPath, XY, { ghost: true, sz: 3, dash: '9 7' });
  BM = { b, gPath, gLive, N, XY, i: -1, timer: null, fitZ };
  drawMapStep(0);
  mvTo(midX, midY, fitZ, 600);
  $('bmpname').textContent = b.name;
  $('bmpbar').style.display = 'flex';
  const parent = EV.find(e => e.id === b.event_id);
  $('pdetail').innerHTML = `
    <h5>${esc(b.name)}<span>战役</span></h5>
    <div class="r">
      <span class="k">年份</span><span class="v">${b.year} 年　${esc(b.date_text || '')}</span>
      <span class="k">交战</span><span class="v">${esc((b.belligerents || []).map(x => x.side || x).join(' × ') || '—')}</span>
      <span class="k">结果</span><span class="v">${esc(b.result || '—')}</span>
      ${b.casualties_note ? `<span class="k">伤亡</span><span class="v">${esc(b.casualties_note)}</span>` : ''}
      <span class="k">地点</span><span class="v">${esc(b.place_name || '—')}</span>
    </div>
    <div class="n">${esc(b.summary || '')}${parent ? `<br><span class="lit">父事件 · ${esc(parent.name)}</span>` : ''}
      <br><span class="lit">战线已在主图标出，点「▶ 推演」播放推进；地图可自由缩放。</span></div>`;
  $('plist').querySelectorAll('.it.on').forEach(e => e.classList.remove('on'));
  const it = $('plist').querySelector(`.it[data-bid="${b.id}"]`);
  if (it) { it.classList.add('on'); it.scrollIntoView({ block: 'nearest' }); }
}
function stopBattleMapPlay() {
  if (BM) {
    if (BM.timer) clearInterval(BM.timer);
    if (BM.gPath) BM.gPath.remove();
    if (BM.gLive) BM.gLive.remove();
    BM = null;
  }
  const pb = $('bmpbar'); if (pb) pb.style.display = 'none';
}
$('bmpplay').onclick = () => {
  if (!BM) return;
  if (BM.timer) { clearInterval(BM.timer); BM.timer = null; return; }   // 再点一次暂停
  let i = 0;
  drawMapStep(0);
  mvTo(BM.N[0].pixel_x, BM.N[0].pixel_y, Math.min(BM.fitZ, 6), 500);
  BM.timer = setInterval(() => {
    i++;
    if (i >= BM.N.length) { clearInterval(BM.timer); BM.timer = null; return; }
    drawMapStep(i);
    mvTo(BM.N[i].pixel_x, BM.N[i].pixel_y, Math.min(BM.fitZ, 6), 500);
  }, 1400);
};""",
'map battle funcs')

# ---------- 10. 页签绑定 ----------
rep("$('pq').oninput = renderPList;",
"""$('pq').oninput = renderPList;
$('ptabs').querySelectorAll('button').forEach(b => b.onclick = () => {
  ptTab = b.dataset.t;
  $('ptabs').querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b));
  renderPList();
});""",
'ptabs bind')

io.open(F, 'w', encoding='utf-8').write(s)
print('ALL DONE')
