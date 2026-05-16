# 投资报告 Agent · 设计系统

> 田中一光式东方秩序 — Ikko Tanaka · Eastern Order
> 最后更新: 2026-05-17

## 设计宣言

**「投资报告的终极价值不是数据，是判断。」**

田中一光用极简几何形体表达复杂信息的哲学，与投资研究的内核一致：
从噪音中提炼信号，用留白承托结论。

三条核心原则：
1. **每一个像素必须服务于理解** — 不装饰、不炫耀、不 cliché
2. **留白是结论的呼吸空间** — 密集数据需要空白来承托，而非挤压
3. **和纸温润，数据不冷漠** — 暖灰底替代纯白，深棕替代纯黑

## 色板

```css
:root {
  /* 底色 */
  --bg-warm:       #FAF8F5;   /* 和纸暖白 — 全屏底色 */
  --bg-surface:    #F3F0EC;   /* 浅茶 — 卡片/面板底色 */
  --bg-elevated:   #FFFFFF;   /* 纯白 — 弹出层/输入框 */

  /* 文字 */
  --ink-primary:   #2D2420;   /* 深棕 — 主文字，替代 #000 */
  --ink-secondary: #6B5E58;   /* 棕灰 — 辅助文字 */
  --ink-tertiary:  #9E9288;   /* 浅棕灰 — 禁用/水印 */

  /* 强调 */
  --accent:        #C04A1A;   /* 朱砂红 — 唯一点缀色。CTA/关键数字/买入评级 */
  --accent-hover:  #A03D12;   /* 深朱砂 — hover */
  --accent-soft:   #F5E6DD;   /* 极淡朱砂 — 选中背景 */

  /* 数据色板 */
  --data-positive: #3D6B4F;   /* 苔绿 — 正向指标/买入 */
  --data-negative: #C04A1A;   /* 复用朱砂 — 负向/卖出 */
  --data-neutral:  #9E9288;   /* 浅棕灰 — 中性 */
  --data-series-1: #2D2420;   /* 深棕 */
  --data-series-2: #C04A1A;   /* 朱砂 */
  --data-series-3: #6B5E58;   /* 棕灰 */
  --data-series-4: #D4C5B9;   /* 米灰 */
  --data-series-5: #3D6B4F;   /* 苔绿 */

  /* 边框/分割 */
  --border-light: #E8E2DB;    /* 浅米 — 分割线 */
  --border:       #D4C5B9;    /* 米灰 — 边框 */
}
```

## 字体系统

| 角色 | 字体 | 备选 | 使用场景 |
|------|------|------|---------|
| **Display** | `Noto Serif SC` | `Source Han Serif SC` | 报告标题、章节标题、重要引语 |
| **Body** | `Noto Sans SC` | `-apple-system, PingFang SC` | 正文、UI 文字 |
| **Mono** | `JetBrains Mono` | `SF Mono` | 财务数据、代码块、ticker |
| **English Display** | `Playfair Display` | `Georgia` | 英文标题、数字大字报 |
| **English Body** | `Inter` | `-apple-system` | 英文正文 |

**选用逻辑**：田中一光在 MUJI 时代的作品大量使用明朝体（宋体）作标题、ゴシック体（黑体）作正文。思源宋体/黑体是这个传统的现代延续。

## 间距系统：8pt 网格

```
space-1:   8px    (0.5rem)   — 紧凑内边距
space-2:  16px    (1rem)     — 标准内间距
space-3:  24px    (1.5rem)   — 段落间距
space-4:  32px    (2rem)     — 节间距
space-5:  48px    (3rem)     — 区块间距
space-6:  64px    (4rem)     — 大段留白
space-7:  96px    (6rem)     — 页级留白
space-8: 128px    (8rem)     — 封面留白
```

**铁律**：留白至少占可视面积的 40%。内容拥挤时扩张容器而非压缩间距。

## 报告排版（从 Web 到 PDF 一致）

| 元素 | Web | PDF |
|------|-----|-----|
| 报告标题 | 28px / 1.3 | 22pt |
| 章标题 | 22px / 1.4 | 16pt |
| 节标题 | 18px / 1.4 | 13pt |
| 正文 | 16px / 1.8 | 11pt / 1.8 |
| 数据标注 | 14px | 9pt |
| 脚注 | 12px | 8pt |
| 关键数字 | 36px / 1.2 | 24pt / 1.2 |

**行距原则**：正文行距 ≥ 1.6（中文需要比英文更大的行距来呼吸），标题 1.2-1.4

## 图表设计语言

- 所有图表使用 `--data-series-*` 色板
- 无边框、无背景色、无网格线（或极淡）
- Y 轴刻度在右侧（东方传统竖排从右读）
- 数据标签直接标注在数据点旁，不依赖图例
- 标题在图表下方（田中一光式的「图在下，文在上」）

## 反 AI Slop 清单

| ❌ 禁止 | ✅ 采用 |
|---------|---------|
| 紫色/蓝色渐变背景 | 和纸暖白 + 留白 |
| 圆角卡片 + 左 accent border | 平面区块 + 细线分隔 |
| emoji 作图标 | 无图标（文字即信息）或极简几何形 |
| 赛博霓虹/深蓝底 | 暖白底 + 深棕字 |
| Inter/Roboto 全家桶 | Noto Serif + Noto Sans 配对 |
| 阴影/elevation 分层 | 留白和线条建层级 |
| 装饰性 icon/dot/stats | 只放有判断力的数据 |
