#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""事件/地图改造回归：
1) 战役卡 minimap 悬停提示 + 单击放大 → 全屏推演页 + 播放
2) 地图页三栏布局 / 页签切换 / 点战役主图推演
"""
from playwright.sync_api import sync_playwright

URL = 'file:///workspace/读三国-project/app/reader.html'
ok = []
def chk(name, cond):
    ok.append((name, bool(cond)))
    print(('PASS' if cond else 'FAIL'), name)

with sync_playwright() as pw:
    br = pw.chromium.launch(executable_path='/usr/bin/chromium')
    pg = br.new_page(viewport={'width': 1500, 'height': 900})
    errors = []
    pg.on('pageerror', lambda e: errors.append(str(e)))
    pg.goto(URL)
    pg.wait_for_timeout(800)

    # ---- 1. 战役卡：放大提示与全屏推演页 ----
    pg.evaluate("setView('events')")
    pg.wait_for_timeout(400)
    pg.evaluate("openBattle('chi_bi_battle')")
    pg.wait_for_timeout(600)
    chk('战役卡 bwrap/zhint 存在', pg.evaluate("!!document.querySelector('.bwrap .zhint')"))
    chk('zhint 文案含放大', pg.evaluate("document.querySelector('.zhint').textContent.includes('单击放大')"))
    pg.evaluate("openBattleStage('chi_bi_battle')")
    pg.wait_for_timeout(600)
    chk('全屏页打开', pg.evaluate("document.getElementById('bmask').classList.contains('on')"))
    chk('全屏页标题', pg.evaluate("document.getElementById('bmt').textContent.includes('战线推演')"))
    chk('全屏页推演进度', pg.evaluate("document.getElementById('bmpn').textContent.length > 0"))
    # 2026-10-29 定案：进入全屏自动开始推演；按钮为 播放/暂停 一体
    pg.wait_for_timeout(2600)
    n1 = pg.evaluate("document.getElementById('bmpn').textContent")
    chk('自动播放推进 (>1)', n1 not in ('', '1 / ' + n1.split(' / ')[-1]))
    print('  进度:', n1)
    # 播放中点击 = 暂停（进度冻结）；已播完点击 = 重新推演（进度回退）
    btn = pg.evaluate("document.getElementById('bmp').textContent")
    pg.click('#bmp')
    pg.wait_for_timeout(200)
    if '暂停' in btn:
        paused = pg.evaluate("document.getElementById('bmpn').textContent")
        chk('暂停按钮文案', pg.evaluate("document.getElementById('bmp').textContent.includes('继续')"))
        pg.wait_for_timeout(2600)
        chk('暂停后进度冻结', pg.evaluate("document.getElementById('bmpn').textContent") == paused)
        pg.click('#bmp')
        pg.wait_for_timeout(2600)
        n2 = pg.evaluate("document.getElementById('bmpn').textContent")
        chk('续播推进 (>暂停时)', n2 != paused)
        print('  暂停时:', paused, '→ 续播后:', n2)
    else:
        n2 = pg.evaluate("document.getElementById('bmpn').textContent")
        chk('重新推演回退', n2 != n1)
        print('  已播完，重新推演:', n1, '→', n2)
    pg.keyboard.press('Escape')
    pg.wait_for_timeout(300)
    chk('Esc 关闭全屏页', pg.evaluate("!document.getElementById('bmask').classList.contains('on')"))

    # ---- 2. 地图页三栏 + 页签 + 战役推演 ----
    pg.evaluate("setView('places')")
    pg.wait_for_timeout(600)
    chk('左列表在左(首列 tabs)', pg.evaluate("document.querySelector('#v-places .plist.left .tabs') !== null"))
    chk('详情栏在最右', pg.evaluate("document.querySelector('#v-places .mapsplit > .plist:last-child #pdetail') !== null"))
    chk('列表宽 < 地图宽', pg.evaluate("document.querySelector('#v-places .plist.left').offsetWidth < document.querySelector('#v-places .mapstage').offsetWidth"))
    # 地名点击 → 详情在右栏
    pg.evaluate("selectPlaceOnMap(L['suan_zao'] || Object.values(L)[0])")
    pg.wait_for_timeout(700)
    chk('点地名右栏出详情', pg.evaluate("document.getElementById('pdetail').textContent.includes('今地') || document.getElementById('pdetail').textContent.length > 20"))
    # 页签切战役
    pg.evaluate("document.querySelector('#ptabs button[data-t=battle]').click()")
    pg.wait_for_timeout(300)
    cnt = pg.evaluate("document.querySelectorAll('#plist .it').length")
    chk('战役列表非空', cnt > 0)
    print('  战役条目:', cnt)
    # 点第一个战役 → 主图推演
    pg.evaluate("document.querySelector('#plist .it').click()")
    pg.wait_for_timeout(1000)
    chk('推演条显示', pg.evaluate("document.getElementById('bmpbar').style.display === 'flex'"))
    chk('推演条有战役名', pg.evaluate("document.getElementById('bmpname').textContent.length > 0"))
    chk('详情栏切战役信息', pg.evaluate("document.getElementById('pdetail').textContent.includes('交战')"))
    # 播放
    pg.click('#bmpplay')
    pg.wait_for_timeout(3200)
    prog = pg.evaluate("document.getElementById('bmpn').textContent")
    chk('主图推演推进', '/' in prog and not prog.startswith('1 / '))
    print('  主图进度:', prog)
    # 暂停推演后可自由缩放（播放中镜头由推演接管，暂停即还给人手）
    pg.click('#bmpplay')          # 再点一次 = 暂停
    pg.wait_for_timeout(900)
    z0 = pg.evaluate("document.getElementById('mzlb').textContent")
    pg.evaluate("document.getElementById('mzo').click()")
    pg.wait_for_timeout(400)
    z1 = pg.evaluate("document.getElementById('mzlb').textContent")
    chk('暂停后地图可缩放', z0 != z1)
    print('  缩放:', z0, '->', z1)
    # 再点地名 → 推演停止、条隐藏
    pg.evaluate("selectPlaceOnMap(L['suan_zao'] || Object.values(L)[0])")
    pg.wait_for_timeout(500)
    chk('点地名后推演条隐藏', pg.evaluate("document.getElementById('bmpbar').style.display === 'none'"))
    # ---- 第三轮反馈项 ----
    chk('全局侧栏已隐藏(noside)', pg.evaluate("document.body.classList.contains('noside')"))
    pg.evaluate("setView('places')")   # 重进地图页，验证默认态
    pg.wait_for_timeout(600)
    chk('红点默认隐藏', pg.evaluate("MV.dotsWrap.style.display === 'none'"))
    pg.evaluate("selectPlaceOnMap(L['suan_zao'] || Object.values(L)[0])")
    pg.wait_for_timeout(700)
    chk('选中地名后红点显示', pg.evaluate("(MV.dotsWrap.style.display||'') !== 'none'"))
    chk('选中地名有名牌标注', pg.evaluate("MV.focus.items.length === 1 && MV.focus.items[0].name.length > 0"))
    chk('全图只有一个红点', pg.evaluate("Array.from(MV.dots.values()).filter(c=>c.style.display!=='none').length === 1"))
    # 州域：不点红点，高亮底图州界+州名
    pg.evaluate("selectPlaceOnMap(L['ji_zhou'])")
    pg.wait_for_timeout(1200)
    chk('州域无红点无名牌', pg.evaluate("MV.zHi && MV.zHi.name === '冀州' && MV.focus.items.length === 0"))
    chk('州界线高亮(红实线加粗)', pg.evaluate("(()=>{const z=MV.zPoly.get('冀州');return z.line.getAttribute('stroke')==='#7d1f16' && z.line.getAttribute('stroke-dasharray')==='none'})()"))
    chk('其余州界淡出', pg.evaluate("parseFloat(MV.zPoly.get('幽州').line.getAttribute('opacity')) < 0.4"))
    chk('州名加重', pg.evaluate("(()=>{const t=Array.from(MV.svgZhouLb.querySelectorAll('text')).find(t=>t.textContent==='冀州');return t.getAttribute('font-weight')==='700'})()"))
    chk('州域详情文案', pg.evaluate("document.getElementById('pdetail').textContent.includes('州界')"))
    # 切回普通地名：州界复原
    pg.evaluate("selectPlaceOnMap(L['suan_zao'])")   # 纯县点：既非州也非郡，应完全复原
    pg.wait_for_timeout(900)
    chk('切回地名州界复原', pg.evaluate("MV.zPoly.get('冀州').line.getAttribute('stroke')==='#8b5a9e' && MV.zHi === null"))
    chk('恒定信息在右栏底部', pg.evaluate("document.getElementById('pdfoot').textContent.includes('个点位')"))
    # 自适应镜头：主图推演时比例应随段变化（播放两步后读 mzlb）
    pg.evaluate("document.querySelector('#ptabs button[data-t=battle]').click()")
    pg.wait_for_timeout(300)
    # 选节点最多的战役，保证有多步推演可对比比例
    pg.evaluate("selectBattleOnMap(BT.reduce((m,b)=>b.front_line.length>m.front_line.length?b:m))")
    pg.wait_for_timeout(900)
    pg.click('#bmpplay')
    pg.wait_for_timeout(2300)
    zA = pg.evaluate("document.getElementById('mzlb').textContent")
    pg.wait_for_timeout(1600)
    zB = pg.evaluate("document.getElementById('mzlb').textContent")
    chk('主图镜头随段自适应(比例在变)', zA != zB)
    print('  主图比例:', zA, '->', zB)
    # 页签回地名
    pg.evaluate("document.querySelector('#ptabs button[data-t=place]').click()")
    pg.wait_for_timeout(300)
    chk('页签回地名(树渲染)', pg.evaluate("document.querySelectorAll('#plist .row.lv-zhou').length >= 13"))


    # ---- 第五轮：州级判定修正 / 郡界高亮 / 跨区域地理分层 ----
    pg.evaluate("selectPlaceOnMap(L['ji_zhou'])")
    pg.wait_for_timeout(700)
    chk('①冀州(州域)亮州界', pg.evaluate("MV.zHi && MV.zHi.name === '冀州'"))
    pg.evaluate("selectPlaceOnMap(L['xu_zhou'])")
    pg.wait_for_timeout(900)
    chk('①徐州(州治)同样亮州界', pg.evaluate("MV.zHi && MV.zHi.name === '徐州'"))
    chk('①徐州州界变红实线', pg.evaluate("(()=>{const z=MV.zPoly.get('徐州');return z.line.getAttribute('stroke')==='#7d1f16' && z.line.getAttribute('stroke-dasharray')==='none'})()"))
    # 郡界层：数据齐、默认弱化（比州界细）
    chk('③郡界数据齐全(>=100)', pg.evaluate("(GEO.junpoly||[]).length >= 100"))
    chk('③郡界默认比州界弱', pg.evaluate("(()=>{const g=document.querySelector('[data-jun] path');return parseFloat(g.getAttribute('stroke-width')) < 1.2 && g.getAttribute('stroke')!=='#8b5a9e'})()"))
    # 郡高亮：走「无卡郡行」路径（junFocus）——有卡的郡治县点应只定位不亮郡（见⑧）
    pg.evaluate("junFocus('颍川郡')")
    pg.wait_for_timeout(900)
    chk('③郡高亮生效', pg.evaluate("MV.jHi && /颍川/.test(MV.jHi.name)"))
    chk('③郡界变实线加粗', pg.evaluate("(()=>{const g=[...MV.jPoly.values()].flat().find(p=>p.getAttribute('stroke')==='#c2641f');return !!g && parseFloat(g.getAttribute('stroke-width'))>1.2 && g.getAttribute('stroke-dasharray')==='none'})()"))
    chk('③郡高亮加粗可辨(线宽≥3，2026-10 定案：郡高亮须醒目，不再弱于州)', pg.evaluate("(()=>{const g=[...MV.jPoly.values()].flat().find(p=>p.getAttribute('stroke')==='#c2641f');return parseFloat(g.getAttribute('stroke-width')) >= 3})()"))
    chk('③郡名注记显形', pg.evaluate("parseFloat(MV.svgJunLb.getAttribute('opacity')) > 0.5"))
    # ② 江东/淮南：不在州列表，单列跨区域地理组
    chk('②江东淮南不算州节点', pg.evaluate("PT.filter(x=>x.level==='zhou'&&['江东','淮南'].includes(x.name)).length === 0"))
    chk('②江东淮南归 region 层', pg.evaluate("PT.filter(x=>x.level==='region').map(x=>x.name).sort().join(',')==='江东,淮南'"))
    pg.evaluate("document.querySelector('#ptabs button[data-t=place]').click()")
    pg.wait_for_timeout(400)
    chk('②跨区域地理组存在', pg.evaluate("!!document.querySelector('#plist .grp-region')"))
    pg.evaluate("ptOpen.add('z:地区'); renderPTree('')")
    pg.wait_for_timeout(300)
    chk('②组内有 region 行', pg.evaluate("document.querySelectorAll('#plist .row.lv-region').length >= 1"))
    # ④ 地点卡小图与地图页同语言：州/郡不画红点而亮界线
    pg.evaluate("openPlace(L['ji_zhou'].id)")
    pg.wait_for_timeout(800)
    chk('④州地点卡小图无红点靶心', pg.evaluate("""document.querySelectorAll('#mm .focus-target, #mm circle[fill="#9c2b1f"]').length === 0"""))
    chk('④州地点卡小图亮州界', pg.evaluate("(()=>{const svg=document.getElementById('mm');const ps=[...svg.querySelectorAll('path')].filter(p=>p.getAttribute('stroke')==='#7d1f16');return ps.length>0})()"))
    pg.evaluate("closeCard()")
    pg.wait_for_timeout(300)

    # 跨区域地理高亮（青斜纹）
    pg.evaluate("selectPlaceOnMap(L['jiang_dong'])")
    pg.wait_for_timeout(900)
    chk('②江东斜纹高亮', pg.evaluate("MV.rHi && MV.rHi.name==='江东' && !!document.querySelector('#bigmap defs pattern#hatchRegion')"))
    chk('②江东高亮时州郡复位', pg.evaluate("MV.zHi===null && MV.jHi===null"))
    chk('②江东详情文案', pg.evaluate("document.getElementById('pdetail').textContent.includes('地理分区')"))
    pg.evaluate("selectPlaceOnMap(L['huainan'])")
    pg.wait_for_timeout(900)
    chk('②淮南切换正常', pg.evaluate("""MV.rHi && MV.rHi.name==='淮南' && document.querySelectorAll('#bigmap path[fill="url(#hatchRegion)"]').length>=1"""))
    pg.evaluate("selectPlaceOnMap(L['suan_zao'])")
    pg.wait_for_timeout(700)
    chk('②切县点后分区高亮清除', pg.evaluate("MV.rHi===null"))

    # ---- 第七轮反馈项 ----
    # 地区组默认收起（全树默认折叠），先展开再取 region 行
    pg.evaluate("ptOpen.add('z:地区'); renderPTree('')")
    pg.wait_for_timeout(300)
    # ① 11 个地理分区全部可高亮（树里点纯地理分区行）
    pg.evaluate("""(()=>{const row=[...document.querySelectorAll('#plist .row[data-kind=region]')].find(x=>x.querySelector('.nm').textContent==='河北');row.click()})()""")
    pg.wait_for_timeout(900)
    chk('⑦河北(纯地理区)可高亮', pg.evaluate("MV.rHi && MV.rHi.name==='河北'"))
    chk('⑦纯地理区有界线(虚线+斜纹)', pg.evaluate("""document.querySelectorAll('#bigmap path[fill="url(#hatchRegion)"]').length>=1 && !!document.querySelector('#bigmap path[stroke-dasharray="12 6"]')"""))
    chk('⑦纯地理区有大字注记', pg.evaluate("MV.rHi.t !== null && MV.rHi.t.textContent==='河北'"))
    # ② region 行不再带「非行政」徽标
    chk('⑦region行无非行政徽标', pg.evaluate("[...document.querySelectorAll('#plist .row[data-kind=region]')].every(x=>!x.querySelector('.ty'))"))
    # ③ 水系：全部列出 + 点击高亮完整水系
    nrv = pg.evaluate("(DATA.geo.rivers||[]).filter(r=>r.name).map(r=>r.name).filter((v,i,a)=>a.indexOf(v)===i).length")
    pg.evaluate("ptOpen.add('z:跨州水系'); renderPTree('')")
    pg.wait_for_timeout(300)
    nrvrow = pg.evaluate("[...document.querySelectorAll('#plist .row[data-kind=river]')].length")
    chk('⑦水系全部列出', nrvrow >= nrv and nrv >= 30)
    pg.evaluate("""(()=>{const row=[...document.querySelectorAll('#plist .row[data-kind=river]')].find(x=>x.querySelector('.nm').textContent==='汉水');row.click()})()""")
    pg.wait_for_timeout(900)
    chk('⑦水系高亮(蓝线无红点)', pg.evaluate("""MV.rivHi && MV.rivHi.name==='汉水'
        && Array.from(MV.dots.values()).filter(c=>c.style.display!=='none').length===0
        && !!document.querySelector('#bigmap path[stroke="#1d6ea8"]')"""))
    chk('⑦水系详情文案', pg.evaluate("document.getElementById('pdetail').textContent.includes('水系')"))
    # ④ 州名行不再带「州治」徽标；州治列在郡下
    chk('⑦州行无州治徽标', pg.evaluate("[...document.querySelectorAll('#plist .row[data-kind=zhou]')].every(x=>!(x.querySelector('.seat')||{textContent:''}).textContent.includes('州治'))"))
    chk('⑦州治县列在郡下', pg.evaluate("(DATA.place_tree.items.some(it=>it.level==='xian' && it.seat_of && it.seat_of.includes('州治')))"))
    # ⑤ 无地点卡郡可点：谯郡高亮郡界
    pg.evaluate("ptOpen.add('z:益州'); renderPTree('')")
    pg.wait_for_timeout(300)
    pg.evaluate("""(()=>{const row=[...document.querySelectorAll('#plist .row[data-kind=jun]')].find(x=>x.querySelector('.nm').textContent==='上庸郡');row.click()})()""")
    pg.wait_for_timeout(900)
    chk('⑦上庸郡(无卡)点名字亮郡界', pg.evaluate("MV.jHi && MV.jHi.name==='上庸郡'"))
    # 同名郡治点（颍川/巨鹿/中山…）是有卡的县点，点它应落红点定位，不得亮整个郡
    chk('⑧同名郡治点不亮郡界(只落红点)', pg.evaluate(
        "(()=>{const ids=['ying_chuan','ju_lu','zhong_shan','hongnong','dan_yang','chen_liu'];"
        "return ids.every(i=>{const p=L[i];if(!p)return true;selectPlaceOnMap(p);"
        "return MV.jHi===null && MV.dots.get(p.id) && MV.dots.get(p.id).style.display!=='none';})})()"))
    chk('⑧无卡郡仍亮郡界(对照)', pg.evaluate("(()=>{junFocus('上庸郡');return MV.jHi&&MV.jHi.name==='上庸郡'})()"))
    # 郡与郡治县必须拆成两条独立条目：郡行(无卡,亮郡界) + 郡治县行(有卡,落红点)
    chk('⑧郡行与郡治县为两条独立条目', pg.evaluate(
        "(()=>{const j=DATA.place_tree.items.filter(x=>x.level==='jun'&&x.jun==='颍川郡');"
        "const x=DATA.place_tree.items.filter(x=>x.level==='xian'&&x.jun==='颍川郡'&&x.seat_of);"
        "return j.length===1 && j[0].id.startsWith('__jun_') && x.length===1 && x[0].seat_of==='颍川郡治';})()"))
    chk('⑧树中郡行点名字亮郡界', pg.evaluate(
        "(()=>{ptOpen.add('z:豫州');ptOpen.add('j:豫州/颍川郡');renderPTree('');"
        "const r=document.querySelector('#plist .row[data-key=\"j:豫州/颍川郡\"]');"
        "if(!r)return false;r.querySelector('.nm').click();return MV.jHi&&MV.jHi.name==='颍川郡';})()"))
    chk('⑧树种郡行子项含郡治县(同名字)', pg.evaluate(
        "[...document.querySelectorAll('#plist .row.lv-xian .nm')].some(x=>x.textContent==='颍川')"))
    chk('⑦郡全集入树(>=120)', pg.evaluate("Object.values(DATA.place_tree.meta.juns).flat().length>=120 && (DATA.geo.junpoly||[]).length>=120"))
    # 沿海州界贴合：州界点应落在海岸线上（距离≈0）
    # z.pts 可能是单环 [[x,y],…] 或多环 [[[x,y],…],…]（同一州主环+飞地，
    # 见 build.py::_zhoupoly_refit），两种都要能取到点。
    chk('州界贴合海岸(徐州)', pg.evaluate("(()=>{const z=GEO.zhoupoly.find(z=>z.name==='徐州');"
        "const rings=(Array.isArray(z.pts[0][0])?z.pts:[z.pts]);const cs=GEO.coast.flat();"
        "return rings.some(r=>r.some(p=>cs.some(c=>Math.hypot(c[0]-p[0],c[1]-p[1])<0.5)))})()"))

    print('页面 JS 错误:', errors if errors else '无')
    chk('无 JS 报错', not errors)
    pg.screenshot(path='build/verify/reg_events_map.png')
    br.close()

fails = [n for n, c in ok if not c]
print(f'共 {len(ok)} 项，失败 {len(fails)} 项', fails if fails else '')
