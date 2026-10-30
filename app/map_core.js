/* ============================================================================
   读三国 · 地图内核 MapCore
   ----------------------------------------------------------------------------
   唯一实现：只在 app/map_core.js 里维护，build.py 在构建时把本文件内容内联进
   map_test.html 与 reader.html（占位符 /*__MAPCORE__*\/）。**不要在模板里再写
   第二份底图/缩放/注记逻辑**——两套代码漂移是此前多轮「改了一处另一处没改」的根源。

   三条硬规则（历史踩坑总结，改动前先读）
   1) 屏幕像素恒定：凡「观感尺寸」不随缩放变化的元素（选中靶心、战线节点），
      一律写 data-sz = 屏幕像素，再由 applySpacing(root, pz) 按 1/pz 折回画布单位。
      动画每帧都要重新 apply 一次，否则缩放过程中会跑形。
   2) 感知缩放 pz ≠ 视图比例 z：viewBox 显示宽度往往小于画布宽（卡片内嵌小图更小），
      屏幕上的真实倍率是 z × clientWidth / C.w。所有注记字号、阈值都按 pz 算，
      否则小图上标签会缩成看不见的白点。
   3) 数据里的坐标已由构建脚本投影成像素，前端不做任何投影运算。
   ========================================================================== */
window.MapCore = (function () {
  'use strict';
  var NS = 'http://www.w3.org/2000/svg';
  var num = function (v) { return Math.round(v * 1000) / 1000; };

  function el(n, a) {
    var e = document.createElementNS(NS, n);
    if (a) for (var k in a) if (a[k] != null) e.setAttribute(k, a[k]);
    return e;
  }
  function dLine(pts) { return pts.map(function (p, i) { return (i ? 'L' : 'M') + p[0] + ',' + p[1]; }).join(' '); }
  /* pts 既可以是单环 [[x,y],…]，也可以是「多环」[[[x,y],…],…]——同一州的
     主环 + 飞地/离岛必须画成一条 path，否则前端按「每州 2 条 path」配对会错位
     （多环州点州名时边界线不高亮，见 build.py::_zhoupoly_refit 的说明）。 */
  function dPoly(pts) {
    if (pts && pts.length && Array.isArray(pts[0]) && Array.isArray(pts[0][0]))
      return pts.map(function (r) { return dLine(r) + ' Z'; }).join(' ');
    return dLine(pts) + ' Z';
  }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }
  /* 汉字按 1em、其他按 .52em 估宽：名牌每帧定位时用它代替 getBBox（重排代价太高） */
  function textW(s, fs) {
    var n = 0;
    for (var i = 0; i < String(s).length; i++) n += /[\u3400-\u9fff\uff00-\uffef]/.test(String(s)[i]) ? 1 : 0.52;
    return n * fs;
  }

  /* 地名类型 → 定位比例。兜底表与 scripts/build.py 的 SCALE_BY_TYPE 同源；
     build 会把 DATA.scale_by_type 注进来，正式页面以数据为准。 */
  var ZOOM_BY_TYPE = {
    '都城': 2.6, '州域': 1.5, '郡治': 2.8, '重镇': 2.8, '城': 3.2, '县': 3.2,
    '关隘': 3.4, '渡口': 3.0, '要津': 3.0, '战场': 3.0, '山': 3.0, '原': 3.0,
    '水系': 1.2, '宫殿': 3.6, '陵墓': 3.6
  };
  function zoomFor(type, table) { return (table || ZOOM_BY_TYPE)[type] || 3.0; }

  /* ---------------- 底图 ---------------- */
  /* 地形晕渲（构建时生成的 PNG，已按同一画布投影） */
  function terrainLayer(svg, C, GEO) {
    if (GEO.terrain) {
      var img = el('image', { x: 0, y: 0, width: C.w, height: C.h, preserveAspectRatio: 'none' });
      img.setAttribute('href', GEO.terrain);
      svg.appendChild(img);
      return img;
    }
    svg.appendChild(el('rect', { x: 0, y: 0, width: C.w, height: C.h, fill: '#f3ede0' }));
    for (var x = 0; x < C.w; x += 100) svg.appendChild(el('line', { x1: x, y1: 0, x2: x, y2: C.h, stroke: '#e7dfcd', 'stroke-width': 1 }));
    for (var y = 0; y < C.h; y += 100) svg.appendChild(el('line', { x1: 0, y1: y, x2: C.w, y2: y, stroke: '#e7dfcd', 'stroke-width': 1 }));
    return null;
  }
  /* 水系（河 + 湖），大势视图用它做淡显底 */
  function waterLayer(GEO, opacity) {
    var g = el('g', { 'pointer-events': 'none' });
    if (opacity != null) g.setAttribute('opacity', opacity);
    (GEO.rivers || []).forEach(function (r) {
      g.appendChild(el('path', { d: dLine(r.pts), fill: 'none', stroke: r.color, 'stroke-width': r.w, 'stroke-linecap': 'round', opacity: .85 }));
    });
    (GEO.lakes || []).forEach(function (l) {
      g.appendChild(el('path', { d: dPoly(l.pts), fill: '#a8c4d4', stroke: '#7fa2b8', 'stroke-width': .8, opacity: .85 }));
    });
    return g;
  }

  /* 完整底图：地形 → 岸线 → 州界 → 湖 → 河 → 州名 → 县点 → 县名/水名注记
     返回 refs，供 decorScale / 选中态消隐注记使用 */
  function drawBase(svg, C, GEO) {
    svg.innerHTML = '';
    /* 数据裁剪框比画布外扩一圈（投影留余量），整层裁到画布矩形，避免越界绘制 */
    var defs = el('defs', {});
    svg.appendChild(defs);
    var cp = el('clipPath', { id: 'cvclip' });
    cp.appendChild(el('rect', { x: 0, y: 0, width: C.w, height: C.h }));
    defs.appendChild(cp);
    /* 跨区域地理高亮的斜纹填充：青灰 45° 细纹——地理分区≠行政界线的另一种语言
       （州=红实线、郡=橙实线、分区=青斜纹，三者一眼可分） */
    var pat = el('pattern', { id: 'hatchRegion', width: 8, height: 8, patternUnits: 'userSpaceOnUse',
                              patternTransform: 'rotate(45)' });
    pat.appendChild(el('rect', { width: 8, height: 8, fill: 'rgba(70,110,112,.34)' }));
    pat.appendChild(el('line', { x1: 0, y1: 0, x2: 0, y2: 8, stroke: 'rgba(47,81,83,.72)', 'stroke-width': 3 }));
    defs.appendChild(pat);

    var base = el('g', { 'clip-path': 'url(#cvclip)' });
    svg.appendChild(base);
    terrainLayer(base, C, GEO);

    if (!GEO.terrain)
      (Array.isArray(GEO.coast[0][0]) ? GEO.coast : [GEO.coast]).forEach(function (seg) {
        base.appendChild(el('path', { d: dLine(seg), fill: 'none', stroke: '#8a7a5c', 'stroke-width': 2.2, 'stroke-linejoin': 'round' }));
      });

    /* 州界：米白晕底 + 淡紫虚线（与县名暖褐、水名藏蓝区分），描边按屏幕像素恒定 */
    var gZhouPoly = el('g', {});
    base.appendChild(gZhouPoly);
    (GEO.zhoupoly || []).forEach(function (poly) {
      var d = dPoly(poly.pts || poly);
      gZhouPoly.appendChild(el('path', { d: d, fill: 'none', stroke: '#fdf8ea', 'stroke-width': 3, opacity: .3, 'vector-effect': 'non-scaling-stroke' }));
      gZhouPoly.appendChild(el('path', { d: d, fill: 'none', stroke: '#8b5a9e', 'stroke-width': 1.1, 'stroke-dasharray': '7 6', 'stroke-linecap': 'round', opacity: .62, 'vector-effect': 'non-scaling-stroke' }));
    });

    /* 三州交汇「界碑」：≥3 州环共享的坐标点画实心小点。
       虚线 dash 相位在各弧独立，三州共点处可能恰好都是间隙，观感像一道微缝——
       界碑点把交汇处钉住，既是标准制图符号，也顺手消了这个观感问题。
       （数据层审计 scripts/audit_zhou_gaps.py：相邻州距离全 0，共点精确共享。） */
    var zhouPtCount = {};
    (GEO.zhoupoly || []).forEach(function (poly) {
      var seenInPoly = {};
      (poly.pts || poly).forEach(function (p) {
        var k = p[0] + ',' + p[1];
        if (seenInPoly[k]) return;
        seenInPoly[k] = 1;
        (zhouPtCount[k] = zhouPtCount[k] || { n: 0, x: p[0], y: p[1] }).n++;
      });
    });
    Object.keys(zhouPtCount).forEach(function (k) {
      var v = zhouPtCount[k];
      if (v.n < 3) return;
      /* zhoupoly 的 pts 在构建时已投影为画布坐标，直接用 */
      base.appendChild(el('circle', {
        cx: v.x, cy: v.y, r: 2.2, fill: '#8b5a9e', opacity: .8,
        stroke: '#f7f2e6', 'stroke-width': .8, 'paint-order': 'stroke',
        'vector-effect': 'non-scaling-stroke', 'pointer-events': 'none'
      }));
    });

    base.appendChild(waterLayer(GEO, null));

    /* 郡界：与州界同为行政界线，但弱一档——州界是紫实虚加晕底、字大而重；
       郡界用更细的浅赭褐点线、无晕底，只在放大到能看清县名时才浮现（pz≥1.6）。
       每个郡一个 <g data-jun>，内含主环 + 飞地环，供 junHighlight 单独提亮。 */
    var gJunPoly = el('g', { 'pointer-events': 'none' });
    base.appendChild(gJunPoly);
    (GEO.junpoly || []).forEach(function (j) {
      var g = el('g', { 'data-jun': j.n });
      var rings = [j.p].concat(j.e || []);
      rings.forEach(function (ring) {
        if (!ring || ring.length < 3) return;
        g.appendChild(el('path', {
          d: dPoly(ring), fill: 'none', stroke: '#5c6f8e', 'stroke-width': 0.75,
          'stroke-dasharray': '3 3.5', 'stroke-linecap': 'round', opacity: .42,
          'vector-effect': 'non-scaling-stroke'
        }));
      });
      gJunPoly.appendChild(g);
    });

    var gZhouLb = el('g', { 'pointer-events': 'none' });
    base.appendChild(gZhouLb);
    (GEO.zhou || []).forEach(function (z) {
      var t = el('text', {
        x: z.x, y: z.y, 'text-anchor': 'middle', fill: '#5d3f6b', 'font-size': 26,
        'font-family': 'serif', opacity: .9, 'letter-spacing': 4,
        stroke: '#f7f2e6', 'stroke-width': 2, 'paint-order': 'stroke', 'stroke-linejoin': 'round',
        'vector-effect': 'non-scaling-stroke', 'data-zhou': z.name
      });
      t.textContent = z.name;
      gZhouLb.appendChild(t);
    });

    /* 羌中：凉州与益州、司隶西部之间的留白不是漏画——东汉此地为羌胡所居，
       未设郡县（谭图作「羌中」）。加注记说明，读者才不会当成渲染缺口报 bug。
       坐标 (106.1,35.7) 经 build.py 同款投影换算 → (486.4, 383.1)。 */
    var qzT = el('text', {
      x: 486.4, y: 383.1, 'text-anchor': 'middle', fill: '#6b5a45', 'font-size': 15,
      'font-family': 'serif', opacity: .62, 'letter-spacing': 3,
      stroke: '#f7f2e6', 'stroke-width': 2, 'paint-order': 'stroke', 'stroke-linejoin': 'round',
      'vector-effect': 'non-scaling-stroke'
    });
    qzT.textContent = '羌中';
    gZhouLb.appendChild(qzT);
    var qzN = el('text', {
      x: 486.4, y: 398.1, 'text-anchor': 'middle', fill: '#8a7a5c', 'font-size': 9.5,
      'font-family': 'serif', opacity: .6, 'letter-spacing': 1,
      stroke: '#f7f2e6', 'stroke-width': 1.8, 'paint-order': 'stroke', 'stroke-linejoin': 'round',
      'vector-effect': 'non-scaling-stroke'
    });
    qzN.textContent = '羌胡居之 · 汉未设郡';
    gZhouLb.appendChild(qzN);

    /* 郡名注记：字号显著小于州名（州 26 / 郡 13），颜色偏褐、字距收紧，
       只标郡名本身（去掉「郡/国/尹」后缀，与地名页的层级命名一致）。
       默认藏，放大到 pz≥2.2 才出——一屏 104 个郡名会盖住县名。 */
    var gJunLb = el('g', { 'pointer-events': 'none', opacity: 0 });
    base.appendChild(gJunLb);
    (GEO.junpoly || []).forEach(function (j) {
      var nm = String(j.n || '').replace(/(郡|国|尹|属国)$/, '');
      if (!nm) return;
      var t = el('text', {
        x: j.s[0], y: j.s[1] - 5, 'text-anchor': 'middle', fill: '#4f6280', 'font-size': 13,
        'font-family': 'serif', opacity: .82, 'letter-spacing': 2,
        stroke: '#f7f2e6', 'stroke-width': 1.8, 'paint-order': 'stroke', 'stroke-linejoin': 'round',
        'vector-effect': 'non-scaling-stroke', 'data-junlb': j.n
      });
      t.textContent = nm;
      gJunLb.appendChild(t);
    });

    /* 汉县点位已删（2026-10 用户定案）：满屏棕点遮挡地形。
       地名文字保留，且默认以文字中心对准该地实际位置。 */
    var gCty = el('g', {});
    svg.appendChild(gCty);
    var ctyDots = [];

    var gCapLb = el('g', { 'pointer-events': 'none' });   // 郡国治所
    var gCntLb = el('g', { 'pointer-events': 'none' });   // 属县
    svg.append(gCapLb, gCntLb);
    (GEO.counties || []).forEach(function (c) {
      var cap = c.tier === '都';
      var t = el('text', {
        /* 文字中心（横竖双向）落在县治实际坐标上：text-anchor=middle +
           dominant-baseline=central，不再向右上偏移 */
        x: c.x, y: c.y, 'text-anchor': 'middle', 'dominant-baseline': 'central',
        'font-size': 12,
        fill: cap ? '#5a3c10' : '#4a443b', 'font-family': 'serif', 'font-weight': cap ? 600 : 400,
        stroke: '#f3ede0', 'stroke-width': 2, 'paint-order': 'stroke', 'stroke-linejoin': 'round',
        'vector-effect': 'non-scaling-stroke'
      });
      t.textContent = c.name;
      (cap ? gCapLb : gCntLb).appendChild(t);
    });

    /* 水名注记：同名只标最长一段，无名河不标 */
    var gWlb = el('g', { 'pointer-events': 'none' });
    svg.appendChild(gWlb);
    var seen = new Map();
    (GEO.lakes || []).forEach(function (l) {
      if (!seen.has(l.name) || l.pts.length > seen.get(l.name).length) seen.set(l.name, l.pts);
    });
    (GEO.rivers || []).forEach(function (r) {
      if (!r.name || r.w < 1.3) return;
      if (!seen.has(r.name) || r.pts.length > seen.get(r.name).length) seen.set(r.name, r.pts);
    });
    seen.forEach(function (pts, name) {
      var m = pts[Math.floor(pts.length / 2)];
      var t = el('text', {
        x: m[0] + 4, y: m[1] - 3, 'font-size': 11, fill: '#2e4d61', 'font-family': 'serif', opacity: .95,
        stroke: '#f3ede0', 'stroke-width': 2.4, 'paint-order': 'stroke', 'stroke-linejoin': 'round',
        'vector-effect': 'non-scaling-stroke'
      });
      t.textContent = name;
      gWlb.appendChild(t);
    });

    return { base: base, zhouPoly: gZhouPoly, zhouLb: gZhouLb, junPoly: gJunPoly, junLb: gJunLb,
             ctyDots: ctyDots, capLb: gCapLb, cntLb: gCntLb, wlb: gWlb };
  }

  /* ---------------- 缩放与注记分级 ---------------- */
  /* 感知缩放：屏幕上真实倍率 = 视图比例 × 显示宽 / 画布宽 */
  function displayZoom(svg, C, z) {
    var w = (svg && svg.clientWidth) || 0, h = (svg && svg.clientHeight) || 0;
    if (w < 8) w = C.w;                       // 尚未布局（隐藏视图）时退化为画布宽
    if (h < 8) h = C.h;
    /* preserveAspectRatio=meet 的实际缩放 = min(W/vw, H/vh)。
       旧版只看宽度，在扁长容器（全屏推演、卡片小图）里高边先触底，
       「屏幕像素恒定」协议被高宽比打折扣——这就是战线标注
       调了 30/38px 实际只有 ~15px 的根因。 */
    return z * Math.min(w / C.w, h / C.h);
  }
  function viewBoxStr(cx, cy, z, w, h) {
    var vw = w / z, vh = h / z;
    return (cx - vw / 2).toFixed(1) + ' ' + (cy - vh / 2).toFixed(1) + ' ' + vw.toFixed(1) + ' ' + vh.toFixed(1);
  }
  /* 一组画布坐标点的自适应取景比例（z：viewBox 宽 = C.w/z）。
     取景要「按东西本身的跨度定」，不能按类型给死数字：长江横跨半张图，
     汉水只占一小块，同一个 1.2× 必然一个看不到头、一个漂在大片空白里。
     pad 为可用比例（.88 = 四周共留 12%），minSpan 兜住极短对象（小溪、单点），
     否则沿河几百米的支流会被怼成满屏一条线。 */
  function fitZoom(C, xs, ys, opt) {
    opt = opt || {};
    var pad = opt.pad == null ? .88 : opt.pad;
    var minSpan = opt.minSpan == null ? 260 : opt.minSpan;
    var maxZ = opt.maxZ == null ? 6 : opt.maxZ;
    var wx = Math.max(Math.max.apply(null, xs) - Math.min.apply(null, xs), minSpan);
    var hy = Math.max(Math.max.apply(null, ys) - Math.min.apply(null, ys), minSpan * C.h / C.w);
    return Math.max(1, Math.min(C.w * pad / wx, C.h * pad / hy, maxZ));
  }
  /* min/max 用 reduce 而非 Math.min(...arr)：长江折线 800+ 点、全量多段河过千点，
     展开成实参在部分引擎（Safari / 老 V8）会撞调用栈上限。 */
  function extent(a) {
    var lo = Infinity, hi = -Infinity;
    for (var i = 0; i < a.length; i++) { if (a[i] < lo) lo = a[i]; if (a[i] > hi) hi = a[i]; }
    return a.length ? [lo, hi] : [0, 0];
  }
  /* 分级：州名/州界 → 水名 → 郡治 → 属县；字号随 √pz 增长并设屏幕上限（放大才看得清，
     但不至于一屏挤出二十个大字）。 */
  function decorScale(refs, svg, C, z) {
    if (!refs) return 1;
    var pz = displayZoom(svg, C, z);
    var zf = pz <= 2.5 ? 1 : Math.max(0, 1 - (pz - 2.5));
    refs.zhouLb.setAttribute('opacity', (0.8 * zf).toFixed(2));
    refs.zhouPoly.setAttribute('opacity', zf.toFixed(2));
    /* 只对「州名」做字号与描边反算：同组里还挂着「羌中 / 羌胡居之·汉未设郡」两枚
       地理注记（15 / 9.5px），一刀切会把它们放大成州名大小。state 打 data-zhou 标记。 */
    var zt = refs.zhouLb.querySelectorAll('text[data-zhou]');
    for (var i = 0; i < zt.length; i++) {
      zt[i].setAttribute('font-size', (26 / pz).toFixed(3));
      /* 字号按 1/pz 反算成屏幕恒定，描边却是 non-scaling-stroke（永远 2 屏幕像素）——
         屏幕放得越大，字越大、白晕越细，pz≥2.6 时字被地形吃掉。同步按 1/pz 放大描边。 */
      zt[i].setAttribute('stroke-width', (26 / pz * .077).toFixed(3));
    }
    /* 郡界：起步就淡淡可见（pz<1.6 时 .35 让读者知道还有一层行政界线），
       放大后浮到 .55；郡名 pz≥2.2 才出字，字号 13→随缩放反向补偿保持屏幕恒定。
       若当前有郡被高亮（junLb 被外部强制显形），这里不再把透明度压回 0——
       否则镜头动画的每一帧都会把「高亮时显名」覆盖掉。 */
    if (refs.junPoly) refs.junPoly.setAttribute('opacity', pz >= 1.6 ? 0.55 : 0.35);
    if (refs.junLb) {
      var forced = refs.junLb.dataset.force === '1';
      if (!forced) refs.junLb.setAttribute('opacity', pz >= 2.2 ? 0.9 : 0);
      var jt = refs.junLb.querySelectorAll('text');
      for (var k = 0; k < jt.length; k++) jt[k].setAttribute('font-size', ((jt[k]._fs || 13) / pz).toFixed(3));
    }
    /* 县点已删，ctyDots 保留空数组以兼容调用方 */
    var fsCap = Math.min(30, 9 * Math.sqrt(pz) + 4);
    var fsCnt = Math.min(26, 8 * Math.sqrt(pz) + 4);
    refs.capLb.setAttribute('opacity', pz >= 2.6 ? 1 : 0);
    refs.cntLb.setAttribute('opacity', pz >= 5 ? 1 : 0);
    refs.wlb.setAttribute('opacity', pz >= 2.0 ? 1 : 0);
    var ls = [[refs.capLb, fsCap], [refs.cntLb, fsCnt], [refs.wlb, fsCnt]];
    ls.forEach(function (pair) {
      var ts = pair[0].querySelectorAll('text');
      for (var j = 0; j < ts.length; j++) ts[j].setAttribute('font-size', (pair[1] / pz).toFixed(3));
    });
    return pz;
  }
  /* 锁定视图（卡片内嵌小图）：无交互，比例只由调用方决定 */
  function lockZoom(svg) {
    if (!svg) return;
    svg.onwheel = function (e) { e.preventDefault(); };
    svg.ondblclick = function (e) { e.preventDefault(); };
    svg.onpointerdown = svg.onpointermove = svg.onpointerup = svg.onpointercancel = null;
    svg.style.cursor = 'default';
    /* none 而非 pan-y：小图放在可滚动卡片里，pan-y 会把纵向滑动让给卡片，
       横向滑动落到 SVG 上又被 createView 摘了 handler，等于拖不动也滚不动。 */
    svg.style.touchAction = 'none';
  }

  /* ---------------- 屏幕像素恒定层 ---------------- */
  /* 元素协议：data-sz（屏幕像素尺寸）；文字可带 data-ax/ay/dx/dy 锚点偏移；
     圆点 data-stroke 描边；线 data-dash。整个组一次性重算。 */
  /* 战线节点大字号档开关：只有「全屏推演 / 卡片推演场景」置 true，
     总览地图侧栏的小战线推演保持默认档，避免挤占主图。 */
  var BIG_NODE = false;
  function setBigNode(v) { BIG_NODE = !!v; }

  function applySpacing(root, pz) {
    if (!root || !pz) return;
    var k = 1 / pz;
    var nodes = root.querySelectorAll('[data-sz]');
    for (var i = 0; i < nodes.length; i++) {
      var e = nodes[i], v = +e.dataset.sz, tn = e.tagName.toLowerCase();
      if (BIG_NODE && e.dataset.szBig) v = +e.dataset.szBig;
      if (tn === 'text') {
        e.setAttribute('font-size', num(v * k));
        if (e.dataset.ax != null) {
          e.setAttribute('x', num((+e.dataset.ax) + (+e.dataset.dx || 0) * k));
          e.setAttribute('y', num((+e.dataset.ay) + (+e.dataset.dy || 0) * k));
        }
        if (e.dataset.halo) e.setAttribute('stroke-width', num(+e.dataset.halo * k * (BIG_NODE && e.dataset.haloBig ? +e.dataset.haloBig / +e.dataset.halo : 1)));
      } else if (tn === 'circle') {
        e.setAttribute('r', num(v * k));
        if (e.dataset.stroke) e.setAttribute('stroke-width', num(+e.dataset.stroke * k));
      } else {
        e.setAttribute('stroke-width', num(v * k));
        if (e.dataset.dash) e.setAttribute('stroke-dasharray', e.dataset.dash.split(' ').map(function (x) { return num(+x * k); }).join(' '));
      }
    }
  }

  /* ---------------- 选中态：靶心 + 米白名牌 ----------------
     默认挂在点位下方，贴下缘翻上方，左右夹回画布内。
     尺寸全部按屏幕像素定义，place(pz) 每帧重算（缩放动画中不跑形）。 */
  function makeFocus(layer, C, getPz, refs) {
    var items = [];
    function dimSame(name, on) {
      if (!refs) return;
      [refs.capLb, refs.cntLb].forEach(function (g) {
        var ts = g.querySelectorAll('text');
        for (var i = 0; i < ts.length; i++) if (ts[i].textContent === name) ts[i].setAttribute('opacity', on ? 0 : 1);
      });
    }
    function place() {
      var pz = getPz() || 1, k = 1 / pz;
      var fsU = 14 * k, padX = 6.5 * k, padY = 4 * k, R = 14 * k, gap = 6 * k;
      items.forEach(function (it) {
        it.halo.setAttribute('r', R);
        it.ring.setAttribute('r', R);
        it.ring.setAttribute('stroke-width', 1.1 * k);
        it.dot.setAttribute('r', 3.4 * k);
        it.text.setAttribute('font-size', fsU);
        var w = textW(it.name, fsU) + padX * 2, h = fsU + padY * 2;
        var below = it.y + R + gap + h <= C.h - 2 * k;
        var bx = Math.min(Math.max(it.x - w / 2, 2 * k), Math.max(2 * k, C.w - w - 2 * k));
        var by = below ? it.y + R + gap : it.y - R - gap - h;
        it.rect.setAttribute('x', bx); it.rect.setAttribute('y', by);
        it.rect.setAttribute('width', w); it.rect.setAttribute('height', h);
        it.rect.setAttribute('stroke-width', .8 * k);
        it.text.setAttribute('x', bx + w / 2);
        it.text.setAttribute('y', by + h / 2 + fsU * .36);
      });
    }
    function add(x, y, name, color) {
      var pz = getPz() || 1, k = 1 / pz;
      var halo = el('circle', { cx: x, cy: y, r: 14 * k, fill: color, 'fill-opacity': .1, 'pointer-events': 'none' });
      var ring = el('circle', { cx: x, cy: y, r: 14 * k, fill: 'none', stroke: color, opacity: .62, 'pointer-events': 'none' });
      var dot = el('circle', { cx: x, cy: y, r: 3.4 * k, fill: color, 'pointer-events': 'none' });
      var plate = el('g', { 'pointer-events': 'none' });
      var rect = el('rect', { rx: 3.5, ry: 3.5, fill: '#f8f3e7', 'fill-opacity': .95, stroke: color, 'stroke-opacity': .5 });
      var text = el('text', { fill: color, 'font-family': 'serif', 'font-weight': 600, 'text-anchor': 'middle' });
      text.textContent = name;
      plate.append(rect, text);
      layer.append(halo, ring, dot, plate);
      items.push({ halo: halo, ring: ring, dot: dot, rect: rect, text: text, x: x, y: y, name: name });
      dimSame(name, true);
      place();
    }
    function clear() {
      items.forEach(function (it) { dimSame(it.name, false); });
      layer.innerHTML = '';
      items.length = 0;
    }
    return { add: add, clear: clear, place: place, items: items };
  }

  /* ---------------- 战线节点（屏幕像素恒定） ----------------
     两级字号（用户要求「战线说明文字至少与郡名同级」）：
       默认档 24/30 —— 总览地图侧栏的小战线推演
       大字号档 30/38 —— 全屏推演 / 卡片推演场景（由 setBigNode 全局切换） */
  function battleNode(g, n, pz, opt) {
    opt = opt || {};
    var past = !!opt.past;
    g.appendChild(el('circle', {
      cx: n.x, cy: n.y, fill: past ? '#fffdf8' : '#9c2b1f', stroke: '#9c2b1f',
      'data-sz': past ? 4.2 : 8, 'data-sz-big': past ? 5 : 9.5, 'data-stroke': 2
    }));
    var t = el('text', {
      fill: past ? '#5c5449' : '#7d1f16', 'font-family': 'serif', 'font-weight': past ? 400 : 600,
      stroke: '#f3ede0', 'paint-order': 'stroke', 'stroke-linejoin': 'round',
      'data-sz': past ? 24 : 30, 'data-sz-big': past ? 30 : 38, 'data-halo': 4, 'data-halo-big': 5,
      'data-ax': n.x, 'data-ay': n.y, 'data-dx': 9, 'data-dy': (opt.up ? -7 : 12)
    });
    t.textContent = opt.label;
    g.appendChild(t);
    applySpacing(g, pz);
    return t;
  }
  function battlePath(g, pts, opt) {
    opt = opt || {};
    g.appendChild(el('polyline', {
      points: pts.map(function (n) { return n.x + ',' + n.y; }).join(' '),
      fill: 'none', stroke: '#9c2b1f', opacity: opt.ghost ? .14 : .8,
      'stroke-linejoin': 'round',
      'data-sz': opt.sz, 'data-dash': opt.dash || null
    }));
  }

  /* ---------------- 可交互视图（滚轮 / 双击 / 拖拽 / 按钮） ---------------- */
  function createView(svg, C, opt) {
    opt = opt || {};
    var MIN = opt.min == null ? 1 : opt.min, MAX = opt.max == null ? 14 : opt.max;
    var V = { cx: C.w / 2, cy: C.h / 2, s: 1 };
    var anim = null, pz = displayZoom(svg, C, 1);
    var hooks = opt.onApply == null ? [] : (Array.isArray(opt.onApply) ? opt.onApply : [opt.onApply]);

    function apply() {
      var w = C.w / V.s, h = C.h / V.s;
      svg.setAttribute('viewBox',
        (V.cx - w / 2).toFixed(1) + ' ' + (V.cy - h / 2).toFixed(1) + ' ' + w.toFixed(1) + ' ' + h.toFixed(1));
      pz = displayZoom(svg, C, V.s);
      for (var i = 0; i < hooks.length; i++) hooks[i](V, pz);
      if (opt.onZoomLabel) opt.onZoomLabel(V.s);
    }
    function clamp() {
      var w = C.w / V.s, h = C.h / V.s;
      V.cx = Math.min(Math.max(V.cx, w / 2), C.w - w / 2);
      V.cy = Math.min(Math.max(V.cy, h / 2), C.h - h / 2);
      if (V.s <= MIN + 1e-6) { V.cx = C.w / 2; V.cy = C.h / 2; }
    }
    function stop() { if (anim) { cancelAnimationFrame(anim); anim = null; } }
    function animateTo(cx, cy, s, dur) {
      stop();
      dur = dur == null ? 480 : dur;
      var a = { cx: V.cx, cy: V.cy, s: V.s };
      var b = { cx: cx, cy: cy, s: Math.min(MAX, Math.max(MIN, s)) };
      var t0 = performance.now();
      var step = function (now) {
        var k = Math.min(1, Math.max(0, (now - t0) / dur)), e = 1 - Math.pow(1 - k, 3);
        /* 比例走对数插值，视觉上匀速；中心线性插值 */
        V.s = Math.exp(Math.log(a.s) + (Math.log(b.s) - Math.log(a.s)) * e);
        V.cx = a.cx + (b.cx - a.cx) * e;
        V.cy = a.cy + (b.cy - a.cy) * e;
        clamp(); apply();
        if (k < 1) anim = requestAnimationFrame(step); else anim = null;
      };
      anim = requestAnimationFrame(step);
    }
    function zoomAt(px, py, f) {
      stop();
      var s1 = Math.min(MAX, Math.max(MIN, V.s * f));
      if (Math.abs(s1 - V.s) < 1e-6) return;
      V.cx = px - (px - V.cx) * (s1 / V.s);
      V.cy = py - (py - V.cy) * (s1 / V.s);
      V.s = s1; clamp(); apply();
    }
    function toUser(ev) {
      var pt = svg.createSVGPoint(); pt.x = ev.clientX; pt.y = ev.clientY;
      return pt.matrixTransform(svg.getScreenCTM().inverse());
    }
    function bind(ids) {
      ids = ids || {};
      /* 用 on* 属性而非 addEventListener：同一张图重复渲染（切视图回来）时不会叠加监听器 */
      svg.onwheel = function (e) {
        e.preventDefault();
        var p = toUser(e);
        zoomAt(p.x, p.y, e.deltaY < 0 ? 1.15 : 1 / 1.15);
      };
      svg.ondblclick = function (e) { e.preventDefault(); var p = toUser(e); zoomAt(p.x, p.y, 1.7); };
      var drag = null;
      svg.onpointerdown = function (e) {
        if (e.button !== 0) return;
        stop();
        var m = svg.getScreenCTM();
        drag = { id: e.pointerId, sx: e.clientX, sy: e.clientY, cx: V.cx, cy: V.cy, k: 1 / (m ? m.a : 1) };
        svg.setPointerCapture(e.pointerId);
        svg.classList.add('grabbing');
      };
      svg.onpointermove = function (e) {
        if (!drag || e.pointerId !== drag.id) return;
        V.cx = drag.cx - (e.clientX - drag.sx) * drag.k;
        V.cy = drag.cy - (e.clientY - drag.sy) * drag.k;
        clamp(); apply();
      };
      var end = function (e) { if (!drag || (e && e.pointerId !== drag.id)) return; drag = null; svg.classList.remove('grabbing'); };
      svg.onpointerup = end;
      svg.onpointercancel = end;
      var zi = ids.zi && document.getElementById(ids.zi);
      var zo = ids.zo && document.getElementById(ids.zo);
      var zf = ids.fit && document.getElementById(ids.fit);
      if (zi) zi.onclick = function () { zoomAt(V.cx, V.cy, 1.5); };
      if (zo) zo.onclick = function () { zoomAt(V.cx, V.cy, 1 / 1.5); };
      if (zf) zf.onclick = function () { animateTo(C.w / 2, C.h / 2, 1); };
    }
    function pzNow() { return pz; }
    return { V: V, apply: apply, clamp: clamp, animateTo: animateTo, zoomAt: zoomAt, toUser: toUser, bind: bind, stop: stop, pz: pzNow };
  }

  return {
    el: el, dLine: dLine, dPoly: dPoly, esc: esc, textW: textW, num: num,
    zoomFor: zoomFor, ZOOM_BY_TYPE: ZOOM_BY_TYPE,
    drawBase: drawBase, terrainLayer: terrainLayer, waterLayer: waterLayer,
    displayZoom: displayZoom, viewBoxStr: viewBoxStr, fitZoom: fitZoom, extent: extent,
    decorScale: decorScale, lockZoom: lockZoom,
    applySpacing: applySpacing, makeFocus: makeFocus, battleNode: battleNode, battlePath: battlePath,
    setBigNode: setBigNode,
    createView: createView
  };
})();
