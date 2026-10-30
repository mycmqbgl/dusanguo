#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三轮反馈：
1) 地名：一次只显示选中那一个红点（其余不显示）
2) 州域（冀州/兖州…）：不显示红点，改为高亮底图原有州名 + 州界线
"""
import io

F = 'app/reader_template.html'
s = io.open(F, encoding='utf-8').read()

def rep(old, new, tag):
    global s
    assert s.count(old) == 1, f'anchor fail: {tag} (count={s.count(old)})'
    s = s.replace(old, new)
    print('ok:', tag)

# ---------- 1. drawBase 后存州界路径，便于高亮 ----------
rep("""  const svg = $('bigmap');
  svg._refs = MC.drawBase(svg, C, GEO);
  const gP = el('g', { style: 'display:none' });   /* 红点默认隐藏：选中地名后才出现 */""",
"""  const svg = $('bigmap');
  svg._refs = MC.drawBase(svg, C, GEO);
  /* 州界路径按名称索引（底图按 zhoupoly 顺序生成，每条 2 个 path：晕底 + 虚线） */
  const zPoly = new Map();
  const zPaths = Array.from(svg._refs.zhouPoly.children);
  (GEO.zhoupoly || []).forEach((poly, i) => {
    zPoly.set(poly.name, { halo: zPaths[i * 2], line: zPaths[i * 2 + 1] });
  });
  const gP = el('g', { style: 'display:none' });   /* 红点默认隐藏：选中地名后才出现一个 */""",
'zPoly index')

rep("""  MV.dots = dots;
  MV.dotsWrap = gP;""",
"""  MV.dots = dots;
  MV.dotsWrap = gP;
  MV.zPoly = zPoly;
  MV.zHi = null;      /* 当前高亮的州 {name, halo, line} */""",
'mv zPoly')

# ---------- 2. 州界高亮 / 复原 ----------
rep("""/* 点击点位：只缩放定位 + 右侧详情，不弹卡片 */""",
"""/* 州界高亮：底图原州界描粗变色 + 州名加重放大；其余州界轻微淡出，凸显选区 */
function zhouHighlight(name) {
  const z = MV && MV.zPoly ? MV.zPoly.get(name) : null;
  if (!z) return;
  zhouClearHighlight();
  MV.zHi = { name: name };
  (GEO.zhoupoly || []).forEach(poly => {
    const q = MV.zPoly.get(poly.name);
    if (!q) return;
    const on = poly.name === name;
    q.line.setAttribute('stroke', on ? '#7d1f16' : '#8b5a9e');
    q.line.setAttribute('stroke-width', on ? 2.4 : 1.1);
    q.line.setAttribute('stroke-dasharray', on ? 'none' : '7 6');
    q.line.setAttribute('opacity', on ? 1 : .26);
    q.halo.setAttribute('stroke', on ? '#f6e3c8' : '#fdf8ea');
    q.halo.setAttribute('opacity', on ? .85 : .16);
    q.halo.setAttribute('stroke-width', on ? 6 : 3);
  });
  const ts = MV.svgZhouLb ? MV.svgZhouLb.querySelectorAll('text') : [];
  for (let i = 0; i < ts.length; i++) {
    const on = ts[i].textContent === name;
    ts[i].setAttribute('fill', on ? '#7d1f16' : '#5d3f6b');
    ts[i].setAttribute('font-size', on ? 34 : 26);
    ts[i].setAttribute('font-weight', on ? 700 : 400);
    ts[i].setAttribute('opacity', on ? 1 : .5);
  }
}
function zhouClearHighlight() {
  if (!MV || !MV.zHi || !MV.zPoly) return;
  MV.zHi = null;
  MV.zPoly.forEach(q => {
    q.line.setAttribute('stroke', '#8b5a9e');
    q.line.setAttribute('stroke-width', 1.1);
    q.line.setAttribute('stroke-dasharray', '7 6');
    q.line.setAttribute('opacity', .62);
    q.halo.setAttribute('stroke', '#fdf8ea');
    q.halo.setAttribute('stroke-width', 3);
    q.halo.setAttribute('opacity', .3);
  });
  const ts = MV.svgZhouLb ? MV.svgZhouLb.querySelectorAll('text') : [];
  for (let i = 0; i < ts.length; i++) {
    ts[i].setAttribute('fill', '#5d3f6b');
    ts[i].setAttribute('font-size', 26);
    ts[i].setAttribute('font-weight', 400);
    ts[i].setAttribute('opacity', .9);
  }
  if (typeof MC.decorScale === 'function' && MV.pz) MC.decorScale($('bigmap')._refs, $('bigmap'), C, MV.pz);
}

/* 点击点位：只缩放定位 + 右侧详情，不弹卡片 */""",
'zhou highlight')

# ---------- 3. selectPlaceOnMap：州域走州界高亮；地名只留一个红点 ----------
rep("""  stopBattleMapPlay();
  mvTo(p.pixel_x, p.pixel_y, zoomFor(p));
  if (MV.dotsWrap) MV.dotsWrap.style.display = '';     /* 选中地名后才显示红点 */
  if (MV.dots) MV.dots.forEach(c => c.setAttribute('fill', c._r > 4 ? '#9c2b1f' : '#b3a690'));
  const d = MV.dots && MV.dots.get(p.id); if (d) d.setAttribute('fill', '#9c2b1f');
  if (MV.focus) { MV.focus.clear(); MV.focus.add(p.pixel_x, p.pixel_y, p.name, '#9c2b1f'); }""",
"""  stopBattleMapPlay();
  if (MV.focus) MV.focus.clear();
  if (MV.dots) MV.dots.forEach(c => { c.style.display = 'none'; });   /* 一次只留一个红点 */
  /* 州域：不点红点，改高亮底图原有的州名与州界线，镜头对准州名 */
  if (p.type === '州域' && MV.zPoly && MV.zPoly.has(p.name)) {
    zhouHighlight(p.name);
    if (MV.dotsWrap) MV.dotsWrap.style.display = 'none';
    const z = GEO.zhou.find(z => z.name === p.name) || { x: p.pixel_x, y: p.pixel_y };
    mvTo(z.x, z.y, 1.9);
  } else {
    zhouClearHighlight();
    mvTo(p.pixel_x, p.pixel_y, zoomFor(p));
    if (MV.dotsWrap) MV.dotsWrap.style.display = '';
    const d = MV.dots && MV.dots.get(p.id); if (d) { d.style.display = ''; d.setAttribute('fill', '#9c2b1f'); }
    if (MV.focus) MV.focus.add(p.pixel_x, p.pixel_y, p.name, '#9c2b1f');
  }""",
'selectPlace one dot')

# ---------- 4. 详情文案随类型变化 ----------
rep("""    <div class="n">已定位，比例 ${zoomFor(p).toFixed(1)}×。可继续缩放或拖拽查看周边。</div>`;""",
"""    <div class="n">${p.type === '州域'
      ? '已高亮该州州界与州名（底图原有注记），压暗其余州界以便辨认。可继续缩放或拖拽查看。'
      : '已定位，比例 ' + zoomFor(p).toFixed(1) + '×。可继续缩放或拖拽查看周边。'}</div>`;""",
'pdetail note')

# ---------- 5. 只在需要时才记州名层 ----------
rep("""  MV.dots = dots;
  MV.dotsWrap = gP;""",
"""  MV.dots = dots;
  MV.dotsWrap = gP;
  MV.svgZhouLb = svg._refs.zhouLb;""",
'svgZhouLb')

# ---------- 6. 战役推演时也清掉州界高亮 ----------
rep("""  if (MV && MV.dotsWrap) MV.dotsWrap.style.display = 'none';   /* 推演时隐藏地名红点，减少遮挡 */
  if (MV && MV.focus) MV.focus.clear();""",
"""  if (MV && MV.dotsWrap) MV.dotsWrap.style.display = 'none';   /* 推演时隐藏地名红点，减少遮挡 */
  if (MV && MV.focus) MV.focus.clear();
  if (MV && MV.dots) MV.dots.forEach(c => { c.style.display = 'none'; });
  zhouClearHighlight();""",
'selectBattle clear zhou')

io.open(F, 'w', encoding='utf-8').write(s)
print('ALL DONE')
