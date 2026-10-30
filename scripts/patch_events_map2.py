#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第二轮反馈：
1) 战线推演镜头自适应：按相邻节点跨度放缩（长距离拉远/短距离推近），平滑过渡（小图 rAF 插值，主图 mvTo 缓动）
2) 地图页隐藏全局左侧栏；「共147个点位」等恒定信息并入右栏底部 footer
3) 主图推演只标当前节点文字，减少遮挡
4) 地图页默认隐藏全部红点；选中地名后显示红点并用「靶心+名牌」标注地名
"""
import io

F = 'app/reader_template.html'
s = io.open(F, encoding='utf-8').read()

def rep(old, new, tag, cnt=1):
    global s
    assert s.count(old) == cnt, f'anchor fail: {tag} (count={s.count(old)})'
    s = s.replace(old, new)
    print('ok:', tag)

# ---------- 1. CSS ----------
rep("""  .bmpbar .d{color:#4a443b;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:400px}""",
"""  .bmpbar .d{color:#4a443b;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:400px}
  /* 地图页有自己的左列表：隐藏全局侧栏 */
  body.noside aside{display:none}
  /* 右栏：详情 + 恒定信息 footer */
  .plist .dtcol{display:flex;flex-direction:column;flex:1;min-height:0;width:100%}
  .plist .dtcol .dt{flex:1;max-height:none;min-height:0}
  .plist .dtcol .dt.pdfoot{flex:none;border-top:1px solid var(--line);color:var(--ink2);font-size:11.5px;line-height:1.9}""",
'css2')

# ---------- 2. 右栏 HTML：dtcol + pdfoot ----------
rep("""        <div class="plist"><div class="dt" id="pdetail"><div class="e">点击左侧列表（地名 / 战役页签）或地图上的点位，此处显示详情。</div></div></div>""",
"""        <div class="plist"><div class="dtcol">
          <div class="dt" id="pdetail"><div class="e">点击左侧列表（地名 / 战役页签）或地图上的点位，此处显示详情。</div></div>
          <div class="dt pdfoot" id="pdfoot"></div>
        </div></div>""",
'right panel html')

# ---------- 3. setView：地图页隐藏全局侧栏 ----------
rep("""  $('side-bd').classList.toggle('pwlist', v === 'power');""",
"""  $('side-bd').classList.toggle('pwlist', v === 'power');
  document.body.classList.toggle('noside', v === 'places');""",
'setView noside')

# ---------- 4. renderPlaces：恒定信息进 pdfoot；红点默认隐藏；焦点名牌 ----------
rep("""function renderPlaces() {
  stopBattleMapPlay();
  $('side-hd').textContent = '地名';
  $('side-bd').innerHTML = `<div style="padding:9px 12px;font-size:11.5px;color:var(--ink2);line-height:1.9">
    共 ${Object.keys(L).length} 个点位<br>已在本 ${DATA.chapters.length} 回中出现 ${DATA.stats.places_linked} 个<br>
    <span style="color:var(--ink3)">地图可自由缩放，点击点位即定位</span></div>`;
  $('side-ft').style.display = 'none';
  const svg = $('bigmap');
  svg._refs = MC.drawBase(svg, C, GEO);
  const gP = el('g', {});
  const dots = new Map();""",
"""function renderPlaces() {
  stopBattleMapPlay();
  $('pdfoot').innerHTML = `共 ${Object.keys(L).length} 个点位<br>已在本 ${DATA.chapters.length} 回中出现 ${DATA.stats.places_linked} 个<br>
    <span style="color:var(--ink3)">地图可自由缩放，点击点位即定位</span>`;
  const svg = $('bigmap');
  svg._refs = MC.drawBase(svg, C, GEO);
  const gP = el('g', { style: 'display:none' });   /* 红点默认隐藏：选中地名后才出现 */
  const dots = new Map();""",
'renderPlaces head')

rep("""  svg.appendChild(gP);
  /* 可交互视图：滚轮/双击/拖拽/按钮由内核统一绑定；每次进入本视图重建，状态复位到全图 */
  MV = MC.createView(svg, C, {
    onApply: (V, pz) => {
      if (MV) MV.pz = pz;
      dots.forEach(c => c.setAttribute('r', (c._r || 3.4) / pz));
      MC.decorScale(svg._refs, svg, C, V.s);
      if (BM && BM.gPath) { MC.applySpacing(BM.gPath, pz); MC.applySpacing(BM.gLive, pz); }
      const lb = $('mzlb'); if (lb) lb.textContent = V.s.toFixed(2) + '×';
    }
  });
  MV.dots = dots;""",
"""  const gF = el('g', {});
  svg.append(gP, gF);
  /* 可交互视图：滚轮/双击/拖拽/按钮由内核统一绑定；每次进入本视图重建，状态复位到全图 */
  MV = MC.createView(svg, C, {
    onApply: (V, pz) => {
      if (MV) MV.pz = pz;
      dots.forEach(c => c.setAttribute('r', (c._r || 3.4) / pz));
      MC.decorScale(svg._refs, svg, C, V.s);
      if (BM && BM.gPath) { MC.applySpacing(BM.gPath, pz); MC.applySpacing(BM.gLive, pz); }
      if (MV && MV.focus) MV.focus.place();
      const lb = $('mzlb'); if (lb) lb.textContent = V.s.toFixed(2) + '×';
    }
  });
  MV.dots = dots;
  MV.dotsWrap = gP;
  MV.focus = MC.makeFocus(gF, C, () => (MV && MV.pz) || 1, svg._refs);   /* 选中地名：靶心 + 名牌 */
  MV.focus.place();""",
'renderPlaces view')

# ---------- 5. selectPlaceOnMap：显示红点 + 名牌标注 ----------
rep("""  stopBattleMapPlay();
  mvTo(p.pixel_x, p.pixel_y, zoomFor(p));
  if (MV.dots) MV.dots.forEach(c => c.setAttribute('fill', '#b3a690'));
  const d = MV.dots && MV.dots.get(p.id); if (d) d.setAttribute('fill', '#9c2b1f');""",
"""  stopBattleMapPlay();
  mvTo(p.pixel_x, p.pixel_y, zoomFor(p));
  if (MV.dotsWrap) MV.dotsWrap.style.display = '';     /* 选中地名后才显示红点 */
  if (MV.dots) MV.dots.forEach(c => c.setAttribute('fill', c._r > 4 ? '#9c2b1f' : '#b3a690'));
  const d = MV.dots && MV.dots.get(p.id); if (d) d.setAttribute('fill', '#9c2b1f');
  if (MV.focus) { MV.focus.clear(); MV.focus.add(p.pixel_x, p.pixel_y, p.name, '#9c2b1f'); }""",
'selectPlace focus')

# ---------- 6. buildBattleScene 重写：自适应镜头 + 平滑插值 ----------
i0 = s.index('function buildBattleScene(svg, b, hook) {')
i1 = s.index('/* ===== 全屏战线推演页（卡片小图「单击放大」进入） ===== */')
s = s[:i0] + """function buildBattleScene(svg, b, hook) {
  svg.innerHTML = '';
  svg._refs = MC.drawBase(svg, C, GEO);
  const gPath = el('g', {}), gLive = el('g', {});
  svg.append(gPath, gLive);
  const N = b.front_line;
  const XY = N.map(n => ({ x: n.pixel_x, y: n.pixel_y }));
  const xs = XY.map(q => q.x), ys = XY.map(q => q.y);
  const midX = (Math.min(...xs) + Math.max(...xs)) / 2, midY = (Math.min(...ys) + Math.max(...ys)) / 2;
  const fitZ = Math.min(C.w / (Math.max(...xs) - Math.min(...xs) + 150),
                         C.h / (Math.max(...ys) - Math.min(...ys) + 150), 15);
  MC.battlePath(gPath, XY, { ghost: true, sz: 3, dash: '9 7' });
  /* 节点层：allLab=全局总览时标全部节点，推演中只标当前步，减少遮挡 */
  const renderNodes = (upto, allLab) => {
    gLive.innerHTML = '';
    const pts = XY.slice(0, upto + 1);
    if (pts.length > 1) MC.battlePath(gLive, pts, { sz: 2.4 });
    pts.forEach((q, k) => MC.battleNode(gLive, q, 1, {
      past: k !== upto, up: k % 2,
      label: (allLab || k === upto) ? N[k].time_seq + '. ' + N[k].label : null
    }));
  };
  /* viewBox 平滑插值（对数缩放 + 缓出），锁定场景的镜头动画 */
  let cur = null, anim = null;
  const applyVB = () => {
    svg.setAttribute('viewBox', MC.viewBoxStr(cur.cx, cur.cy, cur.z, C.w, C.h));
    const pz = MC.displayZoom(svg, C, cur.z);
    MC.decorScale(svg._refs, svg, C, cur.z);
    MC.applySpacing(gPath, pz); MC.applySpacing(gLive, pz);
  };
  const setVB = (t, dur) => {
    if (anim) { cancelAnimationFrame(anim); anim = null; }
    if (!cur || !dur) { cur = { cx: t.cx, cy: t.cy, z: t.z }; applyVB(); return; }
    const a = { ...cur }, t0 = performance.now();
    const step = now => {
      const k = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - k, 3);
      cur = { cx: a.cx + (t.cx - a.cx) * e, cy: a.cy + (t.cy - a.cy) * e,
              z: Math.exp(Math.log(a.z) + (Math.log(t.z) - Math.log(a.z)) * e) };
      applyVB();
      if (k < 1) anim = requestAnimationFrame(step); else anim = null;
    };
    anim = requestAnimationFrame(step);
  };
  /* 每步镜头自适应：本步与相邻节点的跨度决定比例，长距离行军拉远、短距离事件推近 */
  const camFor = i => {
    const a = XY[Math.max(0, i - 1)], c = XY[i];
    const span = Math.max(Math.abs(c.x - a.x), Math.abs(c.y - a.y), 80);
    return { cx: (a.x + c.x) / 2, cy: (a.y + c.y) / 2,
             z: Math.max(2.5, Math.min(C.w * .55 / span, C.h * .55 / span, 16)) };
  };
  return {
    N, fitZ, midX, midY, gPath, gLive,
    draw(upto, dur) {
      this._i = upto;
      renderNodes(upto, false);
      setVB(camFor(upto), dur || 0);
      if (hook) hook(upto, N[upto]);
    },
    fit(dur) {
      renderNodes(this._i == null ? 0 : this._i, true);
      setVB({ cx: midX, cy: midY, z: fitZ }, dur || 0);
    }
  };
}

""" + s[i1:]
print('ok: buildBattleScene rewrite')

# ---------- 7. 小图 / 全屏页调用点：先总览再平滑推近 ----------
rep("""  sc.draw(0); sc.fit();""",
"""  sc.fit(0);               // 先全局总览（标全部节点）
  sc.draw(0, 700);         // 再平滑推近第一步""",
'sc init', cnt=2)

rep("""    bi = 0; sc.draw(0);
    timer = setInterval(() => { bi++; if (bi >= sc.N.length) { clearInterval(timer); timer = null; return; } sc.draw(bi); }, 1200);""",
"""    bi = 0; sc.draw(0, 700);
    timer = setInterval(() => { bi++; if (bi >= sc.N.length) { clearInterval(timer); timer = null; return; } sc.draw(bi, 700); }, 1200);""",
'card play')

rep("""    si = 0; sc.draw(0);
    stageTimer = setInterval(() => { si++; if (si >= sc.N.length) { stopStage(); return; } sc.draw(si); }, 1200);""",
"""    si = 0; sc.draw(0, 700);
    stageTimer = setInterval(() => { si++; if (si >= sc.N.length) { stopStage(); return; } sc.draw(si, 700); }, 1200);""",
'stage play')

# ---------- 8. 主图推演：只标当前步文字；镜头按段自适应平滑 ----------
rep("""  pts.forEach((q, k) => MC.battleNode(BM.gLive, q, pz,
    { past: k !== i, up: k % 2, label: BM.N[k].time_seq + '. ' + BM.N[k].label }));""",
"""  pts.forEach((q, k) => MC.battleNode(BM.gLive, q, pz,
    { past: k !== i, up: k % 2, label: k === i ? BM.N[k].time_seq + '. ' + BM.N[k].label : null }));""",
'map step label')

rep("""function selectBattleOnMap(b) {
  stopBattleMapPlay();
  const svg = $('bigmap');
  if (!svg._refs) return;""",
"""function selectBattleOnMap(b) {
  stopBattleMapPlay();
  const svg = $('bigmap');
  if (!svg._refs) return;
  if (MV && MV.dotsWrap) MV.dotsWrap.style.display = 'none';   /* 推演时隐藏地名红点，减少遮挡 */
  if (MV && MV.focus) MV.focus.clear();""",
'selectBattle hide dots')

rep("""$('bmpplay').onclick = () => {
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
"""/* 主图每步镜头：本步与相邻节点的跨度自适应，长距离行军拉远、短距离事件推近；mvTo 自带缓动 */
function battleStepCam(i) {
  const N = BM.N;
  const a = N[Math.max(0, i - 1)], c = N[i];
  const span = Math.max(Math.abs(c.pixel_x - a.pixel_x), Math.abs(c.pixel_y - a.pixel_y), 80);
  return {
    cx: (a.pixel_x + c.pixel_x) / 2, cy: (a.pixel_y + c.pixel_y) / 2,
    z: Math.max(2.5, Math.min(C.w * .5 / span, C.h * .5 / span, 14))
  };
}
$('bmpplay').onclick = () => {
  if (!BM) return;
  if (BM.timer) { clearInterval(BM.timer); BM.timer = null; return; }   // 再点一次暂停
  let i = 0;
  drawMapStep(0);
  const c0 = battleStepCam(0);
  mvTo(c0.cx, c0.cy, c0.z, 700);
  BM.timer = setInterval(() => {
    i++;
    if (i >= BM.N.length) { clearInterval(BM.timer); BM.timer = null; return; }
    drawMapStep(i);
    const c = battleStepCam(i);
    mvTo(c.cx, c.cy, c.z, 700);
  }, 1400);
};""",
'map play cam')

io.open(F, 'w', encoding='utf-8').write(s)
print('ALL DONE')
