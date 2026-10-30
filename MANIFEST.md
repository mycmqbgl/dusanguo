# 读三国 · 项目资产清单

> 生成于 2026-10-30，由 `scripts/pack_assets.py` 自动产出。**本目录即项目真相**：
> 本地工作区只是工作副本，任何改动先落在这里，再同步回本地构建。

## 一、这份资产里有什么

| 目录 | 内容 | 体积 |
|---|---|---|
| `(根目录)` | `README.md` 项目入口 + `MANIFEST.md` 本清单 | 5.5 KB |
| `docs` | 需求文档 / 设计文档 / 规则手册 / 待确认问题 / 待办清单 / 各期报告 | 1.4 MB |
| `app` | 前端源：`map_core.js` 地图内核、两个 `*_template.html`、`assets/terrain.jpg` | 15.1 MB |
| `scripts` | 构建、抓取、地理、校验脚本（`build.py` / `prepare_geo.py` / `verify.py` …） | 1.1 MB |
| `data` | 数据源：人物卡、事件战役、地名、大势、词表规则、原文 `source/chNNN.txt` | 4.7 MB |

文件合计 **296 个 / 22.4 MB**。

## 二、其中的生成物（可打开即读，勿手改）

| 文件 | 体积 | 说明 |
|---|---|---|
| `app/reader.html` | 10.9 MB | 数据与内核已内联的单文件成品页，双击即读 |
| `app/map_test.html` | 643.6 KB | 数据与内核已内联的单文件成品页，双击即读 |

这两份是 `build.py` 把 `data/` 与 `app/map_core.js` 内联进模板后的产物。
放进来是为了让资产**脱离 Python 环境也能直接打开**；但它们是只读快照——
要改内容改 `app/*_template.html` 或 `data/`，再重建，**不要直接编辑这两个文件**，
否则下次构建会被覆盖，且会重新制造「两份实现」的老问题。

## 三、没有放进来什么（以及怎么重建）

| 排除项 | 是什么 | 重建方式 |
|---|---|---|
| `build/` | 全部构建产物（book/places/persons/chapters/events/battles/power/verify/shots/tmp） | `python scripts/build.py` 一条命令重建，约 2 分钟 |
| `data/ne/` | Natural Earth 10m 海岸线/河流/湖泊 + DEM 网格缓存（145 MB 外部数据） | 从 naturalearthdata.com 下 10m 矢量包放入 `data/ne/`，DEM 由 `scripts/build_terrain.py` 自动缓存 |
| `app/assets/terrain.png` | 地形图 PNG 母版（21 MB） | `python scripts/build_terrain.py` 从 `data/ne/` 重新渲染 |
| `.workbuddy/` | 会话与记忆目录（本机私有） | — |

合计排除约 1.15 GB。这些全部可以再生成，放进资产只会引出「改了模板忘了重建 /
拿旧产物当真相」的老问题。

## 四、现状数字

| 项 | 值 |
|---|---|
| 已入库回目 | 第 1–120 回 |
| 正文字数 | 590,535 |
| 段落数 | 2,825 |
| 正文锚点 | 31,856 条 |
| 人物卡 | 1171 张 |
| 地名 | 454 个 |
| 事件 | 73 个 |
| 战役 | 39 场 |

## 五、从这份资产重建整站

```bash
# 1) 取回资产到本地工作目录，装依赖
pip install shapely pillow numpy
# 2) 补外部地理数据到 data/ne/（见第三节「没有放进来什么」）
# 3) 重建
python scripts/build.py        # 生成 build/ 与 app/reader.html、app/map_test.html
python scripts/verify.py       # 147 项回归，退出码 0 即可交付
```

## 六、维护约定

1. **资产为准**：文档、数据、脚本、前端源的修改先落资产，本地副本随后对齐。
2. **构建产物不入资产**：`build/` 与两个成品页只在本地存在，需要时重建。
3. **改动必过回归**：`python scripts/verify.py` 退出码 0 才能算完；数据类改动还会跑 `validate_cards.py`。
4. **文档与待办同步**：改了口径先改 `docs/规则手册.md` 与 `docs/需求文档.md`，待办镜像 `docs/待办清单.md` 跟着走。

