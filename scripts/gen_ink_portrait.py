#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""水墨全身像绘制引擎（纯代码矢量绘制，不依赖任何图像生成服务）

为什么用代码画而不是 AI 出图：
  本环境所有图像生成端点都被拦（ImageGen 指向内网、Pollinations 限流 402/503），
  为保证「方案可交付、人人可有像」，改为用 pycairo 按人物特征参数化绘制。
  优点：零成本、秒级产出、351 人可批量、风格绝对统一、可逐人调参重绘。
  缺点：是「程式化水墨立像」而非手绘艺术品；若日后出图通道恢复，
        同名覆盖 PNG 即可，前端与排版无需改动。

输出：app/assets/avatars/{id}.png  760×1140（2:3 竖幅，宣纸底）
风格锚：宣纸米白、淡墨渲染衣纹、焦墨勾轮廓、朱砂点缀、留白、
        人物全身居中，头顶至足底完整入画，无边框无文字（姓名题签由前端叠加）。
"""
import math
import os
import random
import sys

import cairo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'app', 'assets', 'avatars')

W, H = 760, 1140


# ─────────────────────────── 纸张 ───────────────────────────
def paper(ctx):
    """宣纸底：暖白底 + 极淡不均匀晕 + 纤维噪点"""
    ctx.set_source_rgb(0.968, 0.953, 0.917)
    ctx.paint()

    rnd = random.Random(20261029)
    # 大块淡晕（模仿纸的吸墨不匀）
    for _ in range(28):
        x, y = rnd.uniform(-100, W + 100), rnd.uniform(-100, H + 100)
        r = rnd.uniform(160, 420)
        g = cairo.RadialGradient(x, y, 0, x, y, r)
        a = rnd.uniform(0.010, 0.030)
        g.add_color_stop_rgba(0, 0.80, 0.75, 0.62, a)
        g.add_color_stop_rgba(1, 0.80, 0.75, 0.62, 0)
        ctx.set_source(g)
        ctx.arc(x, y, r, 0, math.tau)
        ctx.fill()

    # 纤维：短细线
    ctx.set_line_width(0.7)
    for _ in range(1400):
        x, y = rnd.uniform(0, W), rnd.uniform(0, H)
        ln = rnd.uniform(2, 9)
        ang = rnd.uniform(0, math.pi)
        ctx.set_source_rgba(0.55, 0.48, 0.36, rnd.uniform(0.02, 0.07))
        ctx.move_to(x, y)
        ctx.line_to(x + math.cos(ang) * ln, y + math.sin(ang) * ln)
        ctx.stroke()


def paper_grain(ctx):
    """细颗粒：模拟熟宣表面的微噪（叠在人物之上，让墨与纸咬合）"""
    rnd = random.Random(777)
    for _ in range(26000):
        x, y = rnd.uniform(0, W), rnd.uniform(0, H)
        ctx.set_source_rgba(0.35, 0.30, 0.24, rnd.uniform(0.008, 0.030))
        ctx.rectangle(x, y, 1.0, 1.0)
        ctx.fill()


# ─────────────────────────── 笔法基元 ───────────────────────────
def wash(ctx, pts, color, alpha, width, taper=True):
    """淡墨晕染：宽笔触 + 低透明，两端收锋"""
    if len(pts) < 2:
        return
    r, g, b = color
    for i in range(len(pts) - 1):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        t = i / max(1, len(pts) - 2)
        w = width * (1 - 0.55 * abs(t - 0.5) * 2 if taper else 1)
        ctx.set_source_rgba(r, g, b, alpha)
        ctx.set_line_width(max(0.6, w))
        ctx.move_to(x0, y0)
        ctx.line_to(x1, y1)
        ctx.stroke()

    # 收笔处的墨积（笔锋停顿留下的深色）
    if taper:
        for (x, y) in (pts[0], pts[-1]):
            rad = width * 0.55
            gd = cairo.RadialGradient(x, y, 0, x, y, rad)
            gd.add_color_stop_rgba(0, r, g, b, alpha * 1.25)
            gd.add_color_stop_rgba(1, r, g, b, 0)
            ctx.set_source(gd)
            ctx.arc(x, y, rad, 0, math.tau)
            ctx.fill()


def stroke(ctx, pts, color, alpha, width):
    """焦墨勾线：细而实，用于轮廓与衣纹"""
    if len(pts) < 2:
        return
    ctx.set_source_rgba(*color, alpha)
    ctx.set_line_width(width)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.move_to(*pts[0])
    for p in pts[1:]:
        ctx.line_to(*p)
    ctx.stroke()


def curve(ctx, x0, y0, cx1, cy1, cx2, cy2, x1, y1):
    ctx.curve_to(cx1, cy1, cx2, cy2, x1, y1)


def blob(ctx, cx, cy, rx, ry, color, alpha, wobble=0.0, segs=48, rnd=None):
    """不规则椭圆（衣块、身体块的基本形），wobble 让轮廓有手绘感"""
    rnd = rnd or random.Random(1)
    ctx.new_path()
    for i in range(segs + 1):
        a = i / segs * math.tau
        k = 1 + (rnd.uniform(-wobble, wobble) if wobble else 0)
        x = cx + math.cos(a) * rx * k
        y = cy + math.sin(a) * ry * k
        if i == 0:
            ctx.move_to(x, y)
        else:
            ctx.line_to(x, y)
    ctx.close_path()
    ctx.set_source_rgba(*color, alpha)
    ctx.fill()


def grad_fill(ctx, path_fn, stops):
    """竖向渐变填充：用于袍服，上浓下淡（墨色下沉）"""
    ctx.save()
    path_fn()
    ctx.clip()
    lg = cairo.LinearGradient(0, 300, 0, 1100)
    for pos, col in stops:
        lg.add_color_stop_rgba(pos, *col)
    ctx.set_source(lg)
    ctx.paint()
    ctx.restore()


# ─────────────────────────── 造型 ───────────────────────────
# 画布坐标约定：人物高约 900px，头顶 y≈150，足底 y≈1060，中轴 x=380
CX = 380
HEAD_TOP = 150
HEAD_RY = 78
HEAD_CY = HEAD_TOP + HEAD_RY          # 228
NECK_Y = HEAD_CY + HEAD_RY - 10        # 296
SHOULDER_Y = 372
WAIST_Y = 640
HEM_Y = 1055


def head(ctx, skin, rnd):
    """头：鹅蛋形，留出下颌收窄"""
    path = lambda: (ctx.new_path(),
                     ctx.move_to(CX, HEAD_TOP),
                     ctx.curve_to(CX + 66, HEAD_TOP + 18, CX + 62, HEAD_CY + 46, CX + 34, HEAD_CY + HEAD_RY - 6),
                     ctx.curve_to(CX + 18, HEAD_CY + HEAD_RY + 4, CX - 18, HEAD_CY + HEAD_RY + 4, CX - 34, HEAD_CY + HEAD_RY - 6),
                     ctx.curve_to(CX - 62, HEAD_CY + 46, CX - 66, HEAD_TOP + 18, CX, HEAD_TOP),
                     ctx.close_path())
    ctx.save()
    path()
    ctx.clip()
    lg = cairo.LinearGradient(0, HEAD_TOP, 0, NECK_Y + 10)
    lg.add_color_stop_rgba(0, skin[0] * 1.02, skin[1] * 1.02, skin[2] * 1.01, 1)
    lg.add_color_stop_rgba(0.62, *skin, 1)
    lg.add_color_stop_rgba(1, skin[0] * 0.86, skin[1] * 0.84, skin[2] * 0.82, 1)
    ctx.set_source(lg)
    ctx.paint()
    # 侧脸暗部
    sg = cairo.LinearGradient(CX + 10, 0, CX + 66, 0)
    sg.add_color_stop_rgba(0, 0.55, 0.44, 0.36, 0)
    sg.add_color_stop_rgba(1, 0.55, 0.44, 0.36, 0.30)
    ctx.set_source(sg)
    ctx.paint()
    ctx.restore()

    # 脸缘右下淡阴影一笔（代替整圈轮廓，避免多边形切角感）
    stroke(ctx, [(CX + 44, HEAD_CY - 40), (CX + 50, HEAD_CY + 8), (CX + 30, HEAD_CY + 58)],
           (0.42, 0.32, 0.26), 0.22, 2.0)


def beard(ctx, color, length, width_top=26, dense=1.0, rnd=None):
    """髯：自两颊与下颌汇成一片，中轴对称下垂，末端收尖。
    length: 0=无须，1=短须，2=长髯及胸"""
    if length <= 0:
        return
    rnd = rnd or random.Random(3)
    y0 = HEAD_CY + HEAD_RY - 14          # 起于下颌
    ln = {1: 58, 2: 196}.get(length, 58)
    w = width_top

    # 主体：一片式，上宽（两颊）下窄收尖
    ctx.new_path()
    ctx.move_to(CX - w * 1.55, y0 - 18)                 # 左颊
    ctx.curve_to(CX - w * 1.1, y0 + ln * 0.42,
                 CX - w * 0.42, y0 + ln * 0.72,
                 CX, y0 + ln)                            # 收尖于中
    ctx.curve_to(CX + w * 0.42, y0 + ln * 0.72,
                 CX + w * 1.1, y0 + ln * 0.42,
                 CX + w * 1.55, y0 - 18)                 # 右颊
    ctx.curve_to(CX + w * 0.9, y0 + 16, CX - w * 0.9, y0 + 16, CX - w * 1.55, y0 - 18)
    ctx.close_path()
    g = cairo.LinearGradient(0, y0 - 10, 0, y0 + ln)
    g.add_color_stop_rgba(0, *color, 0.94 * dense)
    g.add_color_stop_rgba(0.66, *color, 0.78 * dense)
    g.add_color_stop_rgba(1, *color, 0.16 * dense)
    ctx.set_source(g)
    ctx.fill()

    # 髭：唇上两撇，接颊部
    for s in (-1, 1):
        ctx.new_path()
        ctx.move_to(CX + s * 4, HEAD_CY + 26)
        ctx.curve_to(CX + s * 24, HEAD_CY + 22, CX + s * 42, HEAD_CY + 32, CX + s * 52, HEAD_CY + 46)
        ctx.curve_to(CX + s * 30, HEAD_CY + 40, CX + s * 16, HEAD_CY + 40, CX + s * 4, HEAD_CY + 34)
        ctx.close_path()
        ctx.set_source_rgba(*color, 0.80 * dense)
        ctx.fill()

    # 髯丝：几笔焦墨顺流而下
    for _ in range(int(16 * dense)):
        x = CX + rnd.uniform(-w * 0.8, w * 0.8)
        y_start = y0 + rnd.uniform(4, 20)
        y_end = y0 + rnd.uniform(ln * 0.45, ln * 0.95)
        drift = (x - CX) * 0.35
        stroke(ctx, [(x, y_start), (x + drift * 0.6, (y_start + y_end) / 2), (x + drift, y_end)],
               color, 0.26 * dense, 0.9)


def face(ctx, brow_style, eye_style, rnd):
    """五官：以极少笔数取神"""
    ink = (0.16, 0.13, 0.11)
    eye_y = HEAD_CY + 10
    # 眉
    for s in (-1, 1):
        x0 = CX + s * 14
        x1 = CX + s * 50
        if brow_style == 'silkworm':      # 卧蚕眉（关羽）：粗而上挑
            stroke(ctx, [(x0, eye_y - 14), (CX + s * 30, eye_y - 22), (x1, eye_y - 16)], ink, 0.80, 5.2)
        elif brow_style == 'sharp':       # 剑眉（武将）：斜插入鬓
            stroke(ctx, [(x0, eye_y - 10), (x1, eye_y - 26)], ink, 0.82, 4.4)
        elif brow_style == 'long':        # 长眉（智者）：平缓延展
            stroke(ctx, [(x0, eye_y - 12), (CX + s * 32, eye_y - 14), (x1 + s * 4, eye_y - 8)], ink, 0.60, 3.2)
        else:                              # 一般
            stroke(ctx, [(x0, eye_y - 12), (CX + s * 32, eye_y - 16), (x1, eye_y - 12)], ink, 0.72, 4.0)

    # 眼
    for s in (-1, 1):
        ex = CX + s * 30
        if eye_style == 'phoenix':        # 丹凤眼：细长上挑
            ctx.new_path()
            ctx.move_to(ex - 20 * s, eye_y + 3)
            ctx.curve_to(ex - 8 * s, eye_y - 9, ex + 12 * s, eye_y - 8, ex + 20 * s, eye_y - 4)
            ctx.curve_to(ex + 10 * s, eye_y + 5, ex - 8 * s, eye_y + 5, ex - 20 * s, eye_y + 3)
            ctx.close_path()
            ctx.set_source_rgba(*ink, 0.80)
            ctx.fill()
            ctx.arc(ex + 4 * s, eye_y - 1, 3.4, 0, math.tau)
            ctx.set_source_rgba(0.05, 0.04, 0.03, 0.95)
            ctx.fill()
        elif eye_style == 'narrow':       # 细目（曹操）
            stroke(ctx, [(ex - 18 * s, eye_y), (ex, eye_y - 6), (ex + 18 * s, eye_y + 1)], ink, 0.85, 3.0)
            ctx.arc(ex + 3 * s, eye_y - 1, 2.8, 0, math.tau)
            ctx.set_source_rgba(0.05, 0.04, 0.03, 0.92)
            ctx.fill()
        else:
            stroke(ctx, [(ex - 16 * s, eye_y + 1), (ex, eye_y - 5), (ex + 16 * s, eye_y + 1)], ink, 0.80, 3.2)
            ctx.arc(ex + 2 * s, eye_y - 1, 3.0, 0, math.tau)
            ctx.set_source_rgba(0.05, 0.04, 0.03, 0.92)
            ctx.fill()

    # 鼻：一笔侧影 + 一笔鼻头
    stroke(ctx, [(CX + 2, eye_y + 12), (CX - 6, eye_y + 34), (CX + 6, eye_y + 40)], ink, 0.34, 1.6)
    stroke(ctx, [(CX - 8, eye_y + 41), (CX + 9, eye_y + 41)], ink, 0.26, 1.2)

    # 口（若被髯遮住则弱化）
    stroke(ctx, [(CX - 11, HEAD_CY + 30), (CX + 11, HEAD_CY + 30)], ink, 0.34, 1.8)


def hat(ctx, kind, color, accent=None):
    """冠帽：type 决定形制"""
    ink = (0.14, 0.12, 0.10)
    if kind == 'jinxian':     # 进贤冠（曹操）：前高后低，有梁
        ctx.new_path()
        ctx.move_to(CX - 72, HEAD_TOP + 46)
        ctx.line_to(CX - 56, HEAD_TOP - 26)
        ctx.line_to(CX + 56, HEAD_TOP - 26)
        ctx.line_to(CX + 72, HEAD_TOP + 46)
        ctx.close_path()
        ctx.set_source_rgba(*color, 0.92)
        ctx.fill()
        # 冠梁
        for i in (-1, 1):
            stroke(ctx, [(CX + i * 22, HEAD_TOP - 28), (CX + i * 16, HEAD_TOP + 24)], ink, 0.55, 2.4)
        # 帽正
        ctx.arc(CX, HEAD_TOP - 6, 7, 0, math.tau)
        ctx.set_source_rgba(*(accent or (0.72, 0.60, 0.36)), 0.85)
        ctx.fill()
    elif kind == 'lun':      # 纶巾（诸葛亮）：软巾，后有垂带
        ctx.new_path()
        ctx.move_to(CX - 66, HEAD_TOP + 20)
        ctx.curve_to(CX - 62, HEAD_TOP - 34, CX + 62, HEAD_TOP - 34, CX + 66, HEAD_TOP + 20)
        ctx.curve_to(CX + 40, HEAD_TOP - 4, CX - 40, HEAD_TOP - 4, CX - 66, HEAD_TOP + 20)
        ctx.close_path()
        ctx.set_source_rgba(*color, 0.90)
        ctx.fill()
        # 巾结与垂带
        ctx.new_path()
        ctx.move_to(CX - 60, HEAD_TOP + 6)
        ctx.curve_to(CX - 92, HEAD_TOP + 60, CX - 84, HEAD_TOP + 120, CX - 70, HEAD_TOP + 150)
        ctx.curve_to(CX - 78, HEAD_TOP + 100, CX - 80, HEAD_TOP + 50, CX - 50, HEAD_TOP + 10)
        ctx.close_path()
        ctx.set_source_rgba(*color, 0.62)
        ctx.fill()
    elif kind == 'helm':     # 武冠（关羽）：覆顶弓形帽体 + 束发带
        ctx.new_path()
        ctx.move_to(CX - 68, HEAD_TOP + 44)
        ctx.curve_to(CX - 72, HEAD_TOP - 34, CX + 72, HEAD_TOP - 34, CX + 68, HEAD_TOP + 44)
        ctx.line_to(CX + 58, HEAD_TOP + 50)
        ctx.curve_to(CX + 40, HEAD_TOP - 2, CX - 40, HEAD_TOP - 2, CX - 58, HEAD_TOP + 50)
        ctx.close_path()
        ctx.set_source_rgba(*color, 0.94)
        ctx.fill()
        # 束发带
        stroke(ctx, [(CX - 62, HEAD_TOP + 40), (CX + 62, HEAD_TOP + 40)], (0.10, 0.08, 0.06), 0.5, 3.0)


def robe(ctx, base, trim, style='civil', rnd=None):
    """袍身：上窄下阔的梯形轮廓，墨色下沉，衣纹用淡墨长笔"""
    rnd = rnd or random.Random(5)
    r, g, b = base
    shoulder_w = 108 if style == 'civil' else 122
    hem_w = 168 if style == 'civil' else 186

    def path():
        ctx.new_path()
        ctx.move_to(CX - shoulder_w, SHOULDER_Y)
        ctx.curve_to(CX - shoulder_w - 12, SHOULDER_Y + 130, CX - hem_w * 0.86, WAIST_Y + 120, CX - hem_w, HEM_Y)
        ctx.curve_to(CX - hem_w * 0.4, HEM_Y + 14, CX + hem_w * 0.4, HEM_Y + 14, CX + hem_w, HEM_Y)
        ctx.curve_to(CX + hem_w * 0.86, WAIST_Y + 120, CX + shoulder_w + 12, SHOULDER_Y + 130, CX + shoulder_w, SHOULDER_Y)
        ctx.curve_to(CX + 60, SHOULDER_Y - 34, CX - 60, SHOULDER_Y - 34, CX - shoulder_w, SHOULDER_Y)
        ctx.close_path()

    grad_fill(ctx, path, [
        (0.00, (r * 0.86, g * 0.86, b * 0.86, 0.96)),
        (0.32, (r, g, b, 0.94)),
        (0.72, (r * 1.06, g * 1.06, b * 1.06, 0.88)),
        (1.00, (r * 1.14, g * 1.12, b * 1.14, 0.62)),
    ])

    # 左肩受光 / 右侧压暗
    ctx.save()
    path()
    ctx.clip()
    lg = cairo.LinearGradient(CX - shoulder_w, 0, CX + hem_w, 0)
    lg.add_color_stop_rgba(0, 1, 0.98, 0.94, 0.20)
    lg.add_color_stop_rgba(0.45, 1, 1, 1, 0)
    lg.add_color_stop_rgba(1, 0.24, 0.18, 0.14, 0.26)
    ctx.set_source(lg)
    ctx.paint()

    # 衣褶：自肩下垂的淡墨长线，略有弯折
    ink = (r * 0.55, g * 0.52, b * 0.50)
    for i in range(9):
        sx = CX - shoulder_w + 16 + i * (shoulder_w * 2 - 32) / 8
        pts = []
        y = SHOULDER_Y + 30
        x = sx
        while y < HEM_Y - 10:
            pts.append((x, y))
            x += math.sin(y * 0.012 + i) * 5.5
            y += 46
        stroke(ctx, pts, ink, rnd.uniform(0.10, 0.20), rnd.uniform(1.6, 3.4))

    # 下摆墨沉
    hg = cairo.LinearGradient(0, HEM_Y - 200, 0, HEM_Y + 10)
    hg.add_color_stop_rgba(0, r * 0.5, g * 0.5, b * 0.5, 0)
    hg.add_color_stop_rgba(1, r * 0.5, g * 0.5, b * 0.5, 0.34)
    ctx.set_source(hg)
    ctx.paint()
    ctx.restore()

    # 轮廓：焦墨断续勾
    stroke(ctx, [(CX - shoulder_w, SHOULDER_Y), (CX - shoulder_w - 12, SHOULDER_Y + 130),
                 (CX - hem_w * 0.86, WAIST_Y + 120), (CX - hem_w, HEM_Y)],
           (0.20, 0.16, 0.13), 0.52, 2.0)
    stroke(ctx, [(CX + shoulder_w, SHOULDER_Y), (CX + shoulder_w + 12, SHOULDER_Y + 130),
                 (CX + hem_w * 0.86, WAIST_Y + 120), (CX + hem_w, HEM_Y)],
           (0.20, 0.16, 0.13), 0.52, 2.0)
    stroke(ctx, [(CX - hem_w, HEM_Y), (CX - hem_w * 0.4, HEM_Y + 12), (CX, HEM_Y + 14),
                 (CX + hem_w * 0.4, HEM_Y + 12), (CX + hem_w, HEM_Y)],
           (0.20, 0.16, 0.13), 0.46, 2.0)

    # 交领（右衽）
    stroke(ctx, [(CX - 46, SHOULDER_Y - 6), (CX - 22, SHOULDER_Y + 96), (CX + 18, SHOULDER_Y + 250)],
           (0.18, 0.14, 0.11), 0.66, 2.6)
    stroke(ctx, [(CX + 50, SHOULDER_Y - 6), (CX + 26, SHOULDER_Y + 96), (CX - 6, SHOULDER_Y + 250)],
           (0.18, 0.14, 0.11), 0.50, 2.2)
    # 领缘滚边：贴交领内侧的窄双线（弱金，宽 2.6/1.4）
    stroke(ctx, [(CX - 38, SHOULDER_Y + 2), (CX - 15, SHOULDER_Y + 94), (CX + 22, SHOULDER_Y + 240)],
           (trim[0] * 0.8, trim[1] * 0.72, trim[2] * 0.6), 0.40, 2.6)
    stroke(ctx, [(CX - 33, SHOULDER_Y + 4), (CX - 11, SHOULDER_Y + 92), (CX + 26, SHOULDER_Y + 236)],
           (trim[0] * 0.8, trim[1] * 0.72, trim[2] * 0.6), 0.28, 1.4)

    # 腰带
    wtop, wbot = WAIST_Y - 8, WAIST_Y + 24
    ctx.new_path()
    ctx.move_to(CX - shoulder_w - 4, wtop)
    ctx.line_to(CX + shoulder_w + 4, wtop)
    ctx.line_to(CX + shoulder_w + 10, wbot)
    ctx.line_to(CX - shoulder_w - 10, wbot)
    ctx.close_path()
    ctx.set_source_rgba(0.30, 0.24, 0.18, 0.82)
    ctx.fill()
    stroke(ctx, [(CX - shoulder_w, wtop), (CX + shoulder_w, wtop)], (0.12, 0.10, 0.08), 0.5, 1.2)
    stroke(ctx, [(CX - shoulder_w - 6, wbot), (CX + shoulder_w + 6, wbot)], (0.12, 0.10, 0.08), 0.5, 1.2)
    # 带钩
    ctx.arc(CX, (wtop + wbot) / 2, 8, 0, math.tau)
    ctx.set_source_rgba(0.74, 0.62, 0.36, 0.9)
    ctx.fill()


def sleeves(ctx, base, style='civil'):
    """广袖：自肩外侧垂落，形成两个大弧"""
    r, g, b = base
    for s in (-1, 1):
        outer = 128 if style == 'civil' else 138
        drop = 640 if style == 'civil' else 610
        ctx.new_path()
        ctx.move_to(CX + s * 104, SHOULDER_Y + 4)
        ctx.curve_to(CX + s * (outer + 34), SHOULDER_Y + 60,
                     CX + s * (outer + 26), drop - 70,
                     CX + s * outer, drop)
        ctx.curve_to(CX + s * (outer - 44), drop + 16,
                     CX + s * (72), drop - 24,
                     CX + s * 76, SHOULDER_Y + 96)
        ctx.close_path()
        g2 = cairo.LinearGradient(0, SHOULDER_Y, 0, drop)
        g2.add_color_stop_rgba(0, r * 0.94, g * 0.94, b * 0.94, 0.95)
        g2.add_color_stop_rgba(1, r * 1.10, g * 1.08, b * 1.10, 0.72)
        ctx.set_source(g2)
        ctx.fill()
        # 袖口暗部
        ctx.new_path()
        ctx.move_to(CX + s * (outer - 4), drop - 40)
        ctx.curve_to(CX + s * (outer + 4), drop - 6, CX + s * (outer - 20), drop + 10, CX + s * (outer - 44), drop + 12)
        ctx.set_source_rgba(0.22, 0.17, 0.13, 0.30)
        ctx.set_line_width(9)
        ctx.stroke()
        # 袖缘线
        stroke(ctx, [(CX + s * 104, SHOULDER_Y + 6), (CX + s * (outer + 30), SHOULDER_Y + 80),
                     (CX + s * (outer + 20), drop - 60), (CX + s * outer, drop)],
               (0.20, 0.16, 0.13), 0.22, 1.4)


def prop_sword(ctx):
    """按剑：剑斜握于右手侧，鞘尖向下，剑柄在腰侧手的位置"""
    # 鞘
    ctx.new_path()
    ctx.move_to(CX + 150, 700)
    ctx.line_to(CX + 196, 986)
    ctx.set_line_width(11)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_source_rgba(0.22, 0.20, 0.18, 0.88)
    ctx.stroke()
    # 鞘口与鞘尾饰
    for x, y, w in ((CX + 150, 700, 13), (CX + 196, 986, 11)):
        ctx.new_path()
        ctx.arc(x, y, w * 0.55, 0, math.tau)
        ctx.set_source_rgba(0.72, 0.60, 0.34, 0.92)
        ctx.fill()
    # 剑柄（短，斜上）
    ctx.new_path()
    ctx.move_to(CX + 150, 700)
    ctx.line_to(CX + 122, 648)
    ctx.set_line_width(9)
    ctx.set_source_rgba(0.28, 0.22, 0.16, 0.92)
    ctx.stroke()
    # 剑格
    ctx.new_path()
    ctx.move_to(CX + 108, 654)
    ctx.line_to(CX + 138, 642)
    ctx.set_line_width(7)
    ctx.set_source_rgba(0.70, 0.58, 0.32, 0.95)
    ctx.stroke()


def prop_dao(ctx):
    """青龙偃月刀：长柄立于身侧，刀头为半月弧"""
    x = CX + 196
    # 柄
    ctx.new_path()
    ctx.move_to(x - 6, 1040)
    ctx.line_to(x + 10, 400)
    ctx.set_line_width(9)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_source_rgba(0.30, 0.24, 0.16, 0.92)
    ctx.stroke()
    # 柄上缠绳
    for i in range(16):
        y = 460 + i * 34
        stroke(ctx, [(x - 6 + (y - 1040) * -0.0026 - 5, y), (x - 6 + (y - 1040) * -0.0026 + 5, y + 8)],
               (0.14, 0.11, 0.08), 0.40, 2.0)
    # 刀头：偃月形
    ctx.new_path()
    ctx.move_to(x + 12, 400)
    ctx.curve_to(x + 74, 372, x + 96, 268, x + 52, 196)
    ctx.curve_to(x + 30, 250, x + 22, 330, x + 12, 400)
    ctx.close_path()
    lg = cairo.LinearGradient(x, 196, x + 90, 400)
    lg.add_color_stop_rgba(0, 0.72, 0.75, 0.74, 0.95)
    lg.add_color_stop_rgba(0.6, 0.52, 0.56, 0.56, 0.94)
    lg.add_color_stop_rgba(1, 0.36, 0.40, 0.41, 0.92)
    ctx.set_source(lg)
    ctx.fill()
    stroke(ctx, [(x + 12, 400), (x + 74, 372), (x + 96, 268), (x + 52, 196)],
           (0.18, 0.20, 0.20), 0.55, 2.2)
    # 刀锋高光
    stroke(ctx, [(x + 20, 392), (x + 70, 360), (x + 88, 274)], (1, 1, 1), 0.55, 3.0)
    # 吞口
    ctx.arc(x + 10, 400, 10, 0, math.tau)
    ctx.set_source_rgba(0.72, 0.60, 0.34, 0.95)
    ctx.fill()


def prop_staff(ctx):
    """羽扇（诸葛亮）"""
    x, y = CX - 186, 596
    for i in range(13):
        a = math.radians(196 + i * 10.8)
        ctx.new_path()
        ctx.move_to(x, y)
        ctx.line_to(x + math.cos(a) * 74, y + math.sin(a) * 74)
        ctx.set_line_width(2.0)
        ctx.set_source_rgba(0.94, 0.92, 0.86, 0.85)
        ctx.stroke()
    ctx.arc(x, y, 6, 0, math.tau)
    ctx.set_source_rgba(0.30, 0.24, 0.16, 0.9)
    ctx.fill()
    stroke(ctx, [(x, y + 4), (x + 10, y + 62)], (0.28, 0.22, 0.16), 0.7, 4.0)


# ─────────────────────────── 装配 ───────────────────────────
SPECS = {
    'cao_cao': dict(
        robe=(0.50, 0.20, 0.19), trim=(0.74, 0.62, 0.36),
        hat='jinxian', hat_color=(0.17, 0.15, 0.14), accent=(0.74, 0.62, 0.36),
        skin=(0.906, 0.812, 0.706), brow='sharp', eye='narrow',
        beard=2, beard_color=(0.16, 0.13, 0.11), beard_width=24,
        style='civil', props=['sword'], seed=7,
    ),
    'guan_yu': dict(
        robe=(0.20, 0.34, 0.24), trim=(0.72, 0.62, 0.34),
        hat='helm', hat_color=(0.16, 0.22, 0.17), accent=(0.72, 0.60, 0.34),
        skin=(0.62, 0.33, 0.26), brow='silkworm', eye='phoenix',
        beard=2, beard_color=(0.11, 0.09, 0.08), beard_width=40,
        style='martial', props=['dao'], seed=13,
    ),
    'zhuge_liang': dict(
        robe=(0.92, 0.90, 0.85), trim=(0.55, 0.50, 0.42),
        hat='lun', hat_color=(0.86, 0.84, 0.78), accent=(0.55, 0.50, 0.42),
        skin=(0.918, 0.836, 0.750), brow='long', eye='normal',
        beard=1, beard_color=(0.14, 0.12, 0.10), beard_width=18,
        style='civil', props=['staff'], seed=21,
    ),
}


def draw(pid, spec, size=(W, H)):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size[0], size[1])
    ctx = cairo.Context(surf)
    ctx.scale(size[0] / W, size[1] / H)

    rnd = random.Random(spec.get('seed', 1))
    paper(ctx)

    # 人物整体：脚下淡墨投影
    pg = cairo.RadialGradient(CX, HEM_Y + 26, 4, CX, HEM_Y + 26, 230)
    pg.add_color_stop_rgba(0, 0.45, 0.40, 0.32, 0.20)
    pg.add_color_stop_rgba(1, 0.45, 0.40, 0.32, 0)
    ctx.set_source(pg)
    ctx.arc(CX, HEM_Y + 26, 230, 0, math.tau)
    ctx.fill()

    # 层次：袖 → 袍 → 道具 → 颈 → 头 → 五官 → 髯 → 冠
    # （袍在下、头髯在上，髯才能自然垂到胸前袍面）
    sleeves(ctx, spec['robe'], spec['style'])
    robe(ctx, spec['robe'], spec['trim'], spec['style'], rnd)
    for p in spec['props']:
        {'sword': prop_sword, 'dao': prop_dao, 'staff': prop_staff}[p](ctx)
    ctx.new_path()
    ctx.move_to(CX - 24, NECK_Y - 8)
    ctx.line_to(CX + 24, NECK_Y - 8)
    ctx.line_to(CX + 31, NECK_Y + 62)
    ctx.line_to(CX - 31, NECK_Y + 62)
    ctx.close_path()
    ctx.set_source_rgba(*spec['skin'], 0.97)
    ctx.fill()
    # 颈下阴影（严格 clip 在颈形内，防渐变外溢污染纸底）
    ctx.save()
    ctx.new_path()
    ctx.move_to(CX - 24, NECK_Y - 8)
    ctx.line_to(CX + 24, NECK_Y - 8)
    ctx.line_to(CX + 31, NECK_Y + 62)
    ctx.line_to(CX - 31, NECK_Y + 62)
    ctx.close_path()
    ctx.clip()
    ng = cairo.LinearGradient(0, NECK_Y + 10, 0, NECK_Y + 66)
    ng.add_color_stop_rgba(0, 0.42, 0.33, 0.26, 0)
    ng.add_color_stop_rgba(1, 0.42, 0.33, 0.26, 0.38)
    ctx.set_source(ng)
    ctx.paint()
    ctx.restore()
    head(ctx, spec['skin'], rnd)
    face(ctx, spec['brow'], spec['eye'], rnd)
    beard(ctx, spec['beard_color'], spec['beard'], spec['beard_width'], rnd=rnd)
    hat(ctx, spec['hat'], spec['hat_color'], spec['accent'])

    paper_grain(ctx)

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, pid + '.png')
    surf.write_to_png(path)
    return path


def main():
    ids = sys.argv[1:] or list(SPECS)
    for pid in ids:
        if pid not in SPECS:
            print('未知人物：', pid)
            continue
        p = draw(pid, SPECS[pid])
        print('✓', os.path.relpath(p, ROOT))


if __name__ == '__main__':
    main()
