# 读三国 · 《三国演义》结构化交互阅读器

把《三国演义》全书 120 回做成可检索、可追溯的结构化读物：每个出现的人名、地名都链到实体卡，
人物有按年变化的阵营时间片，地名有真实坐标并落在一幅汉末十三州地图上，战役有战线推演，
另有一张 184–280 年 42 路势力逐年消长的大势图。

纯本地静态页面，数据与地图内核全部内联进单个 HTML，双击即开，不需要服务器。

**在线体验**：https://zhujiu.app.workbuddy.host/?sharecode=7CFIPTCYWD

## 现状（2026-10-30，全书完工）

| 指标 | 数值 |
|---|---|
| 已入库原文 | **120 回全量** / 590,535 字 / 2,825 段 |
| 锚点（人名 + 地名） | 31,856（人物 27,107 / 地名 4,749） |
| 人物卡 | **1,171 张**（人工考据 + 自动铺量建档 + 正史补录卡） |
| 地名 | 454 个（已链 236，未链者为一回性小地名） |
| 事件 / 战役 | 73 组 / 39 场（187 个战线节点） |
| 词表 | 2,335 个表面形式，67 条规则、40 条阻断 |
| 大势 | 42 路势力 × 28 快照年，逐年展开 184–280 |
| 回归验证 | `verify.py` **147 项全绿**（含 29 张截图基线 diff 0.000%） |

## 快速开始

```bash
python scripts/build.py          # 重建全部产物（reader.html + map_test.html，约 2 分钟）
python scripts/verify.py         # 全量回归：数据自检 + 代码同源 + 30 场景 + 29 张截图

# 打开
app/reader.html                  # 阅读器主界面（数据已内联，双击即读）
app/map_test.html                # 地图试验页（注记/战役调参用）
```

`build.py` 会把 `app/*_template.html` 里的 `/*__MAPCORE__*/`、`/*__DATA__*/` 占位符替换成
真实内核与数据，输出 `app/reader.html` 与 `app/map_test.html`。
**改页面请改模板，不要改产物**——产物每次构建都会被覆盖。

运行唯一的运行时依赖：`app/assets/terrain.jpg`（3.5 MB 地形底图，须与 reader.html 同目录）。

## 五个视图

| 视图 | 内容 |
|---|---|
| 阅读 | 120 回正文，人名/地名锚点可点开卡；单字单称（「操曰」）与同段回指（「良曰」）自动消歧 |
| 人物 | 1,171 人：阵营时间片（关羽 200–208 是群雄、208 起才是蜀汉）、人物关系图谱、按年筛人 |
| 地名 | 汉末十三州地图：点州高亮州界、点郡高亮郡面、点水系整条河流高亮并自适应缩放 |
| 大势 | 184–280 逐年拖动，42 路势力版图消长；单主州一色、争夺州斜纹 |
| 事件 | 73 组事件 / 39 场战役，战线按节点推演，全部回链原文段落 |

## 部署 / 发布

单文件 + 一张底图即可部署到任何静态托管：

```
reader.html            # 11.4 MB，全部数据与内核已内联
assets/terrain.jpg     # 3.5 MB 地形底图
```

把 `reader.html` 复制为 `index.html` 连同 `assets/` 上传任意静态空间即可（在线版即此方式发布）。

## 项目结构

| 路径 | 内容 |
|---|---|
| `app/` | `map_core.js` 地图内核（唯一实现）、两个 `*_template.html`、`assets/` 底图 |
| `data/` | 全部数据源：`persons_*.json`×25、事件战役、地名、大势、词表规则、原文 `source/ch001–120.txt` |
| `scripts/` | 全部管线：构建 / 地理 / 批产 / 修复 / 校验（见下） |
| `build/` | 构建产物与回归留证（可整目录删除重建；`build/tmp/` 已 gitignore） |
| `docs/` | 需求文档 / 设计文档 / 规则手册等全套文档 |

## 核心脚本

```bash
python scripts/build.py                # 主构建：词表编译 → 锚点扫描 → 卡片/事件/大势组装 → 模板内联
python scripts/verify.py               # 回归 147 项：数据 + 代码同源 + 30 页面场景 + 29 张截图基线
python scripts/expand_persons.py       # 自动铺量建档（名录 + 姓氏词表 + 维基名单 + 频次验证）
python scripts/fix_tenure_span.py      # 任期收敛：结束年按末见回目，不再吃势力上限
python scripts/validate_cards.py       # 人物卡 schema 校验
python scripts/audit_persons.py        # 人物数据体检（1171 人 0 问题）
python scripts/audit_full.py / audit_map.py / audit_power.py / audit_correctness.py
python scripts/pack_assets.py          # 生成项目资产包 dist/ + MANIFEST.md
```

## 五条硬约定

1. **改模板不改产物**：`app/*_template.html` 是源，`app/*.html` 每次构建被覆盖。
2. **地图内核只有一份**：两页共用 `map_core.js`，verify 用 sha1 逐字节断言同源。
3. **口径先行**：改数据判定规则先改 `docs/规则手册.md`，再改 schema，最后改数据。
4. **回归全绿才提交**：`python scripts/build.py && python scripts/verify.py` 退出码必须为 0。
5. **生卒年不确定输出 null**：禁止编造精确年份；演义史实冲突写独立字段不改正文。

## 文档

- `docs/需求文档.md` —— 产品要什么、为什么（PRD）
- `docs/设计文档.md` —— 实现怎么做的、为什么（架构 + ADR）
- `docs/规则手册.md` —— 身份判定 / 链接口径 / 史异处理（v1.4）
- `MANIFEST.md` —— 项目资产清单（由 `pack_assets.py` 自动生成）

## 授权与数据

- 原文底本：通行本《三国演义》毛宗岗评本 120 回（`data/source/`）。
- 地理底图：自渲染地形晕渲（DEM 数据来自 Natural Earth，`data/ne/` 不入库，可重建）。
- 人物阵营、生卒等考据口径见规则手册；演义与史实冲突按「史异注」独立字段处理。
