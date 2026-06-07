# 前端布局设计与色彩选择

> 适用版本：`zong-ce-frontend@0.1.0`
> 技术栈：Vue 3 + Vite 6 + Pinia + Vue Router 4 + TypeScript
> 样式入口：`frontend/src/styles/main.css`
> UI 图标：`lucide-vue-next`

---

## 一、技术栈概览

| 类别 | 选型 |
| --- | --- |
| 框架 | Vue 3（`<script setup lang="ts">`） |
| 构建工具 | Vite 6 |
| 状态管理 | Pinia |
| 路由 | Vue Router 4（History 模式） |
| 图标 | lucide-vue-next |
| 类型检查 | vue-tsc |
| 视觉特色能力 | Chart.js + vue-chartjs（数据看板可视化） |

`main.ts` 仅做三件事：挂载 Pinia、注册 Router、引入全局样式 `main.css`，保持极轻量入口。

---

## 二、整体布局

应用主要呈现两种壳布局（Shell Layout），由 `App.vue` 根据路由 `meta.public` 切换：

### 2.1 应用主壳 `.app-shell`（已登录页面）

通过 CSS Grid 实现两列布局：

```css
.app-shell {
  grid-template-columns: 248px minmax(0, 1fr);
}
```

- **侧边栏 `.sidebar`**
  - `position: sticky; top: 0; height: 100vh`，滚动时固定
  - 颜色由 `--sidebar-*` CSS 变量驱动
  - 垂直三段式：品牌区 → 导航区 → 用户信息 + 退出按钮
  - 导航项根据 `session.user.role`（`student` / `teacher` / 其他）动态生成
  - 当前路由通过 `.nav a.router-link-active` 标识高亮
  - 在桌面端与移动端共用同一份 DOM，差异通过断点切换（详见 2.4）
- **主内容区 `.page`**
  - `padding: 28px`，`display: flex; flex-direction: column`
  - 内部统一包裹一层 `.page-inner`（详见 2.5）
  - 通用结构：
    ```
    .page-header         # 标题区（左侧标题、右侧操作按钮，flex-wrap 友好）
      .eyebrow            # 灰色小字
      h1
      .toolbar
    .grid .cols-2|3      # 卡片栅格
      .panel / .card     # 业务容器
    ```

### 2.2 鉴权壳 `.auth-layout`（登录 / 注册页）

```css
.auth-layout {
  grid-template-columns: minmax(320px, 460px) minmax(0, 1fr);
}
```

- **左侧 `.auth-panel`**：白底表单容器，垂直居中
- **右侧 `.auth-aside`**：Unsplash 校园风景图 + 半透明深色蒙层（`rgba(23, 32, 51, 0.58)`），用于品牌宣传文案

### 2.3 移动端布局（≤920px）

`≤920px` 时取消两列布局，引入 **顶部 App Bar + 抽屉式导航**：

- **`.app-bar`**（仅移动端可见）
  - `position: sticky; top: 0; z-index: 30`
  - 高度 56px，深色背景（复用侧边栏色板）
  - 左侧：菜单按钮（`Menu` ↔ `X` 图标切换）
  - 中部：品牌标 + 当前页面标题（从 `currentTitle` 计算）
  - 右侧：退出按钮
- **`.drawer-backdrop`**：打开抽屉时的全屏半透明遮罩，点击关闭
- **`.sidebar`** 在移动端改为：
  - `position: fixed; top:0; left:0; bottom:0; width: 280px; z-index: 50`
  - 默认 `transform: translateX(-100%)`，加 `.drawer-open` 时回到 `translateX(0)`
  - 路由切换时自动关闭（`watch(route.fullPath)`）
- **无障碍**：
  - 菜单按钮带 `aria-expanded`、`aria-controls`、`aria-label`
  - 抽屉关闭时使用 `inert` 属性禁用内部焦点

### 2.4 响应式策略

| 断点 | 行为 |
| --- | --- |
| `≤ 1200px` | `.grid.cols-3` 降为 2 列 |
| `≤ 920px` | `.app-shell` 单列；显示 `.app-bar`；侧边栏变抽屉；表单/网格/鉴权布局单列；`.auth-aside` 顺序前置 |
| `≤ 560px` | 页面/容器内边距压缩；按钮尺寸略小；表格工具栏改为垂直堆叠 |

### 2.5 内容宽度约束 `.page-inner`

```css
.page-inner {
  width: 100%;
  max-width: var(--page-max); /* 1440px */
  margin: 0 auto;
  display: grid;
  gap: 20px;
  min-width: 0;
}
```

在 `App.vue` 中包裹所有已登录路由的 `RouterView`，防止超宽屏内容散开；移动端会自动收缩到 100% 宽度。

---

## 三、视觉层级（Surface 体系）

为了让页面层级更清晰，引入三类 surface：

| 类 | 用途 | 关键样式 |
| --- | --- | --- |
| `.surface-panel` | 主业务区（替代或升级 `.panel`） | 白底 + 1px 边框 + `0 1px 2px rgba(15, 23, 42, 0.04)` 极轻阴影 |
| `.surface-card` | 重复列表项（替代或升级 `.card`） | 白底 + 1px 边框，8px 圆角 |
| `.surface-muted` | 浅灰信息区（说明、筛选、空状态、批量操作条） | 浅蓝灰底（`--surface-muted`）+ 1px 边框，8px 圆角 |

> 原 `.panel` / `.card` 保持现有行为不变（无阴影），确保既有视图零侵入。

---

## 四、核心组件与类

| 类名 | 用途 | 关键样式 |
| --- | --- | --- |
| `.panel` | 业务容器 | `padding: 18px`，白底 + 1px 边框 + 8px 圆角 |
| `.card` | 次级容器 | `padding: 16px`，同上面板 |
| `.metric strong` | 数据大数字 | `font-size: 30px` |
| `.toolbar` | 操作条 | `flex` + `gap: 10px`，自动换行 |
| `.button` | 主按钮 | 蓝色实心 + 白字 + 650 字重 |
| `.button.secondary` | 次按钮 | 浅灰底（`#eef2f8`） + 深字 |
| `.button.danger` | 危险按钮 | 主红实心 |
| `.button.accent` | 辅助色按钮 | 青绿色实心（学习/分析场景） |
| `.button.ghost` | 透明背景按钮 | 主色文字 + 主色弱底 hover |
| `.button.is-loading` | 加载态 | 透明度禁用 + 居中旋转 spinner |
| `.icon-button` | 图标按钮 | 38×38 方形，浅灰底 |
| `.form-grid` | 表单 | 两列等宽，`.field.full` 可跨列 |
| `.field` | 表单项 | label 在上、控件在下 |
| `.field.has-error` | 表单错误态 | 红色描边 + 浅红底 + 红色焦点环 |
| `.field-error` | 错误文案 | 12px 红字 |
| `.field-hint` | 辅助文案 | 12px 灰字 |
| `.table-wrap` | 表格外层 | 横向滚动 + 圆角边框 |
| `.table-scroll` | 可滚动表格 | `max-height: 520px`，表头 sticky |
| `.table-compact` | 紧凑密度 | 单元格内边距降到 `8px 14px` |
| `.table-toolbar` | 批量操作条 | 浅灰底 + 边框，左侧信息 + 右侧动作 |
| `.density-toggle` | 密度切换 | 三段切换器（已选高亮主色） |
| `.skeleton` / `.skeleton-row` | 加载骨架 | 渐变扫光动画 |
| `th` | 表头 | `#f8fafc` 灰底，13px |
| `tbody tr:hover` | 行 hover | `--row-hover` 浅蓝灰 |
| `tr.is-selected` | 行选中 | `--primary-weak` 浅蓝 |
| `.table-checkbox` | 复选列 | 固定 36px 宽 |
| `.tag` | 状态标签 | 胶囊形，12px / 700 字重，`min-width: 64px` |
| `.alert` / `.alert.danger` | 警告 / 错误反馈 | 暖黄底 / 浅红底 |
| `.success-message` | 成功反馈 | 浅绿底 + 绿边 |
| `.sr-only` | 屏幕阅读器专用 | 视觉隐藏，保留可读性 |
| `.auth-layout` / `.auth-panel` / `.auth-aside` / `.auth-copy` | 鉴权页布局 | 见 2.2 |

全局统一：

- 圆角 `--radius: 8px`（另有 `--radius-sm: 6px` / `--radius-lg: 12px`）
- 字体栈：`Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`
- 基础字号 `16px`，行高 `1.5`
- 全局 `color-scheme: light`（仅亮色模式，预留暗色扩展点）

---

## 五、交互状态体系

所有可交互元素统一以下状态集：

| 状态 | 触发 | 视觉表现 |
| --- | --- | --- |
| **default** | 初始 | 基础色 |
| **hover** | 鼠标悬停 | 颜色加深 / 浅色背景 |
| **active** | 鼠标按下 | 背景更深 + `translateY(1px)` |
| **focus-visible** | 键盘 Tab | 主色焦点环 `0 0 0 3px rgba(38, 99, 235, 0.28)` |
| **disabled** | `:disabled` | `opacity: 0.55; cursor: not-allowed` |
| **loading** | `.is-loading` | 文本透明 + 居中 spinner，禁用点击 |
| **error** | `.has-error` | 红色描边 + 浅红背景 + 红色焦点环 |
| **selected** | `.is-selected` | 主色弱底，行选中态 |

**应用范围**：

- 按钮：`.button` / `.icon-button`
- 导航：`.nav a`
- 表单控件：`.field input / select / textarea`
- 表格行：`tbody tr`
- 链接：所有 `a` 标签

> `:focus-visible` 仅在键盘导航时触发，避免鼠标点击出现多余描边，体验更专业。

---

## 六、色彩体系

### 6.1 基础色（CSS 变量，定义于 `:root`）

| 变量 | 值 | 角色 |
| --- | --- | --- |
| `--bg` | `#f5f7fb` | 页面底色（淡蓝灰） |
| `--text` | `#18202f` | 主文字 |
| `--muted` | `#657084` | 次级文字 |
| `--line` | `#dde3ed` | 边框、分隔线 |
| `--line-strong` | `#b8c2d3` | 强调边框（hover 时） |

### 6.2 Surface 色

| 变量 | 值 | 角色 |
| --- | --- | --- |
| `--panel` / `--card` / `--surface-panel` / `--surface-card` | `#ffffff` | 主面板 / 卡片 |
| `--surface-muted` | `#f3f6fc` | 浅灰信息区 |

### 6.3 品牌主色

| 变量 | 值 | 角色 |
| --- | --- | --- |
| `--primary` | `#2663eb` | 主品牌蓝（按钮、链接、激活态） |
| `--primary-strong` | `#1d4ed8` | hover 加深 |
| `--primary-weak` | `#e9efff` | 主色浅底 |

### 6.4 辅助色（教育 / 健康 / 学习场景）

| 变量 | 值 | 角色 |
| --- | --- | --- |
| `--accent` | `#0f766e` | 青绿辅助色 |
| `--accent-strong` | `#0b5e57` | hover 加深 |
| `--accent-weak` | `#e6f5f2` | 辅助色浅底 |

> 辅助色 **不用于主按钮**（避免抢夺 `--primary`），主要用在：
> - 进度条、学习状态、完成度
> - 分析模块、AI 助手结果
> - `.tag.accent` 状态标签
> - 图表与可视化

### 6.5 语义色

| 变量 | 值 | 角色 |
| --- | --- | --- |
| `--success` | `#16805a` | 成功 |
| `--warning` | `#a56704` | 警告 |
| `--danger` | `#bd2e2e` | 危险 / 错误 |

### 6.6 侧边栏色（已纳入 CSS 变量，支持主题切换）

| 变量 | 值 | 角色 |
| --- | --- | --- |
| `--sidebar-bg` | `#172033` | 深海军蓝底色 |
| `--sidebar-text` | `#d9e2f2` | 导航默认文字 |
| `--sidebar-text-strong` | `#ffffff` | 品牌 / hover / 激活文字 |
| `--sidebar-hover` | `#1f2c45` | 导航 hover |
| `--sidebar-active` | `#263957` | 导航激活 + 点击 |
| `--sidebar-border` | `rgba(255, 255, 255, 0.14)` | 侧边栏内部分割线 |
| `--sidebar-brand-bg` | `#ffffff` | 品牌标徽底色 |
| `--sidebar-brand-fg` | `#172033` | 品牌标徽文字 |

### 6.7 表单色

| 变量 | 值 | 角色 |
| --- | --- | --- |
| `--field-bg` | `#ffffff` | 输入框背景 |
| `--field-border` | `var(--line)` | 输入框默认边框 |
| `--field-border-hover` | `var(--line-strong)` | hover 边框 |
| `--field-border-focus` | `var(--primary)` | 焦点边框 |
| `--field-error` | `var(--danger)` | 错误边框 / 文字 |
| `--field-error-weak` | `#fdecec` | 错误背景 |

### 6.8 焦点环

| 变量 | 值 | 角色 |
| --- | --- | --- |
| `--focus-ring` | `0 0 0 3px rgba(38, 99, 235, 0.28)` | 默认焦点环（主色） |
| `--focus-ring-danger` | `0 0 0 3px rgba(189, 46, 46, 0.28)` | 错误态焦点环 |
| `--focus-ring-on-dark` | `0 0 0 3px rgba(255, 255, 255, 0.22)` | 深色背景上的焦点环 |

### 6.9 表格色

| 变量 | 值 | 角色 |
| --- | --- | --- |
| `--row-hover` | `#f4f7fd` | 行 hover |
| `--row-stripe` | `#fafbfd` | 斑马纹（备用） |
| `--header-bg` | `#f8fafc` | 表头默认 |
| `--header-bg-stuck` | `#eef2f8` | sticky 表头 |

### 6.10 状态标签 `.tag` 语义配色对

| 修饰 | 背景 | 文字 |
| --- | --- | --- |
| 默认 | `#eef2f8` | `#36445a` |
| `.success` | `#e7f6ef` | `--success` |
| `.warning` | `#fff3dc` | `--warning` |
| `.danger` | `#ffe7e7` | `--danger` |
| `.primary` | `--primary-weak` | `--primary` |
| `.accent` | `--accent-weak` | `--accent` |

> `.tag` 默认 `min-width: 64px; justify-content: center;`，避免在表格列中出现宽度抖动。

### 6.11 反馈条

| 类 | 背景 | 文字 | 边框 |
| --- | --- | --- | --- |
| `.alert` | `#fff3dc` | `#744800` | `#f3d18b` |
| `.alert.danger` | `#ffe7e7` | `#8b1f1f` | `#f1b6b6` |
| `.success-message` | `#e7f6ef` | `#0d6847` | `#a7dfc7` |

### 6.12 鉴权页右侧背景

```css
background:
  linear-gradient(rgba(23, 32, 51, 0.58), rgba(23, 32, 51, 0.52)),
  url('https://images.unsplash.com/photo-1498243691581-b145c3f54a5a?auto=format&fit=crop&w=1600&q=80')
    center / cover;
```

半透明深色蒙层 + 居中覆盖的校园图，保证前景文案可读性。

---

## 七、表格体验规范

业务系统里表格是高频界面，按以下规范使用：

| 场景 | 推荐类 |
| --- | --- |
| 普通列表 | `<div class="table-wrap"><table>...</table></div>` |
| 可滚动 + 固定表头 | 外层 `<div class="table-wrap table-scroll">` |
| 紧凑密度 | 表格加 `.table-compact` |
| 含批量操作 | 表格上方加 `.table-toolbar` |
| 密度切换 | 工具栏内加 `.density-toggle` |
| 加载中 | 用 `.skeleton` / `.skeleton-row` 渲染占位 |
| 行选中 | 选中的 `<tr>` 加 `.is-selected` |
| 复选列 | `<th class="table-checkbox">` / `<td class="table-checkbox">` |
| 状态展示 | 单元格内用 `.tag`，避免列抖动 |

---

## 八、暗色模式扩展点

虽然当前仅亮色（`color-scheme: light`），但所有颜色已通过 CSS 变量集中管理，未来要做暗色只需：

```css
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0b1220;
    --panel: #131a2b;
    --text: #e2e8f0;
    --muted: #94a3b8;
    --line: #1f2a40;
    /* ... */
  }
}
```

无需修改任何组件代码。

---

## 九、设计风格总结

- **风格定位**：轻量企业级 SaaS，弱装饰、重信息密度
- **信息层级**：通过 8px 圆角 + 1px 细边框 + 白底卡片 + 极轻阴影（仅 `.surface-panel`）建立层级
- **色彩基调**：白底 + 蓝色主调（`#2663eb`）+ 深色侧边栏（`#172033`）+ 青绿辅助色（`#0f766e`）
- **可读性**：正文 `--text`，次级文字 `--muted`，对比度满足 WCAG AA
- **一致性**：所有语义色成对出现（弱底 + 强字），按钮、tag、反馈条共享同一套语义对
- **无障碍**：所有交互元素支持 `:focus-visible` 焦点环；图标按钮带 `aria-label`；抽屉使用 `inert` 与 `aria-hidden`
- **可扩展性**：所有颜色通过 CSS 变量集中管理，新增视图时仅需复用已有 `.panel / .card / .tag / .button / .surface-*`，不引入新色值
