# 高校综测系统说明文档

> 适用版本：`zong-ce-backend` / `zong-ce-frontend@0.1.0`
> 技术栈：Vue 3 + Vite 6 + Pinia + TypeScript / Flask + PostgreSQL + DeepSeek V4 Pro
> 架构模式：**Master Agent + Worker Agent**（总控调度官 + 多角色智能体）

---

## 目录

1. [系统总览](#一系统总览)
2. [角色与端口划分](#二角色与端口划分)
3. [状态机与业务流程](#三状态机与业务流程)
4. [后端架构](#四后端架构)
5. [学生端](#五学生端)
6. [老师端](#六老师端)
7. [辅导员端](#七辅导员端)
8. [通用能力（智能助手、通知、导出、外部 API）](#八通用能力)
9. [数据模型](#九数据模型)
10. [接口约定](#十接口约定)
11. [前端实现要点](#十一前端实现要点)
12. [部署与演示账号](#十二部署与演示账号)

---

## 一、系统总览

### 1.1 业务目标

高校综测（综合素质测评）系统解决三件事：

- **学生**：上传证书材料、参与综测、查看分数、提交申诉。
- **老师/辅导员**：对材料进行审核、查看班级统计、发起公示、处理申诉、归档成绩。
- **系统**：用 AI 智能识别证书内容并按统一评分细则打分，用状态机约束材料流转，确保公示期数据不被篡改。

### 1.2 技术架构

```
┌────────────────────────────────────────────────────────────┐
│  Frontend (Vue 3 + Vite + Pinia)                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ 学生端口  │ │ 老师端口  │ │ 辅导员端口 │ │ 鉴权公共页 │       │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘       │
│       └────────────┴────────────┴────────────┘              │
│                  axios / fetch（Bearer token）               │
└──────────────────────────┬─────────────────────────────────┘
                           │  HTTP / JSON
┌──────────────────────────┴─────────────────────────────────┐
│  Flask Backend (Master Agent 调度)                          │
│  /api/auth    /api/materials   /api/review                  │
│  /api/appeal  /api/publicity   /api/risk                    │
│  /api/ai      /api/terms       /api/organization            │
│  /api/notifications /api/export /api/stats /api/external    │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Worker Agents: Auth / Audit / Counselor / Appeal /    │  │
│  │   Publicity / Risk / DeepSeek / Term / Organization / │  │
│  │   Notification / Export / Stats / MaterialParser      │  │
│  └───────────────────────────────────────────────────────┘  │
│         ↓                                                  │
│  PostgreSQL (SQLAlchemy ORM) + 本地 uploads 目录           │
└────────────────────────────────────────────────────────────┘
                           │
              DeepSeek V4 Pro（OpenAI 兼容）
```

### 1.3 角色识别规则

由 `backend/app/agents/common.py::infer_role` 统一判断：

| 学工号规则                | 角色         | 入口                |
| ------------------------- | ------------ | ------------------- |
| `20\d{9}`（20 开头 11 位）| `student`    | 学生端登录页         |
| 长度 ≤ 6 的纯数字         | `teacher`    | 教师端登录页         |
| 等于 `123456`             | `counselor`  | 教师端登录页         |

注册时强制要求 `20\d{9}`，否则拒绝。

---

## 二、角色与端口划分

系统通过**学工号格式 + 登录入口（portal）**共同决定用户角色，并在后端做强制校验。

### 2.1 入口差异

| 入口        | 路径                | 适用角色                  | 前端组件                  |
| ----------- | ------------------- | ------------------------- | ------------------------- |
| 学生登录    | `/login/student`    | 仅 `student`              | `StudentLoginView.vue`    |
| 教师/辅导员 | `/login/teacher`    | `teacher` / `counselor`   | `TeacherLoginView.vue`    |
| 公共注册    | `/register`         | 自动按学号识别            | `RegisterView.vue`        |

后端 `AuthAgent.login` 接收 `portal` 字段：

- `portal=student` 且账号不是学生 → 403
- `portal=staff` 且账号是学生 → 403

### 2.2 侧边栏菜单（前端按角色动态生成）

由 `frontend/src/App.vue:31-57` 集中控制：

| 菜单项         | 路径         | student | teacher | counselor |
| -------------- | ------------ | :-----: | :-----: | :-------: |
| 总览           | `/dashboard` |    ✓    |    ✓    |     ✓     |
| 公示排名       | `/publicity` |    ✓    |    ✓    |     ✓     |
| 智能助手       | `/ai`        |    ✓    |    ✓    |     ✓     |
| 材料上传       | `/materials` |    ✓    |         |           |
| 我的申诉       | `/appeals`   |    ✓    |         |           |
| 材料审核       | `/review`    |         |    ✓    |     ✓     |
| 班级审核       | `/review`    |         |         |     ✓     |
| 申诉处理       | `/appeals`   |         |         |     ✓     |
| 公示发起       | `/publicity` |         |         |     ✓     |

> 注：老师与辅导员均进入 `/review` 和 `/publicity`，但 `counselor_agent` 会按 `class_group_id` 自动限定范围。

---

## 三、状态机与业务流程

### 3.1 状态机

由 `backend/app/state_machine.py` 定义：

```
草稿 ──提交──> 已提交 ──领取──> 审核中 ──┬──通过──> 已通过 ──┬──发起──> 公示中 ──┬──申诉──> 申诉处理中
                                          │                   │                  │
                                          │                   │                  ├──归档──> 公示结束
                                          │                   └─ 申诉处理中 ←──────┘
                                          │
                                          └──打回──> 已打回 ──> 草稿（学生重新编辑）
```

`LOCKED_STATUSES = {公示中, 公示结束, 申诉处理中}`，处于这些状态时材料禁止修改。

### 3.2 业务规则

- 禁止跨阶段跳跃（`assert_transition`）
- 公示中、公示结束、申诉处理中 → 材料锁定
- 上传时拦截：重复证书编号、过期证书、未来发证日期（`RiskAgent`）
- 审核打回必须填写原因（`CounselorAgent.action`）
- 申诉仅在公示中生效（`AppealAgent.submit`）

---

## 四、后端架构

### 4.1 Master Agent

`backend/app/agents/master_agent.py`

唯一的“总控调度官”，在请求到来时按需实例化各 Worker Agent：

```python
self.term         = TermAgent()
self.notification = NotificationAgent()
self.organization = OrganizationAgent()
self.risk         = RiskAgent()
self.audit        = AuditAgent(self.risk)
self.counselor    = CounselorAgent()
self.appeal       = AppealAgent()
self.publicity    = PublicityAgent()
self.stats        = StatsAgent()
self.export       = ExportAgent()
self.material_parser = MaterialParser(deepseek_config, siliconflow_config)
```

**核心能力 — `dashboard(user)`**：用 `ThreadPoolExecutor` 并行调用 3 个子任务：

- 学生：`student_summary` + 匿名排行榜 + 我的申诉
- 老师/辅导员：待审核列表 + 完整排行榜 + 风险报告
- 公共：当前学期

### 4.2 Worker Agents 职责矩阵

| Agent              | 主要职责                           | 关键文件                       |
| ------------------ | ---------------------------------- | ------------------------------ |
| AuthAgent          | 注册/登录/Token                    | `agents/auth_agent.py`         |
| AuditAgent         | 材料上传、查询、汇总、评分         | `agents/audit_agent.py`        |
| CounselorAgent     | 老师/辅导员审核、打回、批量审核     | `agents/counselor_agent.py`    |
| AppealAgent        | 学生申诉、复核、一审报告确认       | `agents/appeal_agent.py`       |
| PublicityAgent     | 公示预览、发起、归档、排名         | `agents/publicity_agent.py`    |
| RiskAgent          | 重复/过期/未来日期拦截             | `agents/risk_agent.py`         |
| TermAgent          | 学期管理、自动创建默认学期         | `agents/term_agent.py`         |
| OrganizationAgent  | 学院/专业/班级三级架构             | `agents/organization_agent.py` |
| NotificationAgent  | 站内消息推送与已读管理             | `agents/notification_agent.py` |
| DeepSeekAgent      | 综测智能问答                       | `agents/deepseek_agent.py`     |
| MaterialParser     | 证书图片/PDF 解析                  | `agents/material_parser.py`    |
| ExportAgent        | PDF / Excel 导出                   | `agents/export_agent.py`       |
| StatsAgent         | 班级/学生统计、Top 榜、趋势        | `agents/stats_agent.py`        |

### 4.3 响应统一格式

`backend/app/agents/responses.py::agent_response`：

```json
{
  "agent": "Audit Agent",
  "status": "ok",
  "message": "材料已提交",
  "suggestions": ["查看审核进度", "..."],
  "data": { ... }
}
```

### 4.4 路由注册

`backend/app/__init__.py` 注册了 13 个蓝图，统一 `/api/*` 前缀，CORS 全开：

| 蓝图                | 前缀                |
| ------------------- | ------------------- |
| `auth_bp`           | `/api/auth`         |
| `materials_bp`      | `/api/materials`    |
| `review_bp`         | `/api/review`       |
| `appeal_bp`         | `/api/appeal`       |
| `publicity_bp`      | `/api/publicity`    |
| `risk_bp`           | `/api/risk`         |
| `ai_bp`             | `/api/ai`           |
| `terms_bp`          | `/api/terms`        |
| `organization_bp`   | `/api/organization` |
| `notifications_bp`  | `/api/notifications`|
| `export_bp`         | `/api/export`       |
| `stats_bp`          | `/api/stats`        |
| `external_bp`       | `/api/external`     |

---

## 五、学生端

### 5.1 入口

- 路由：`/login/student` → `StudentLoginView.vue`
- 注册：`/register` → `RegisterView.vue`
- Token：12 小时有效（`itsdangerous.URLSafeTimedSerializer`）

### 5.2 功能清单

| 模块           | 前端页面                | 后端 Agent          | 功能说明                                     |
| -------------- | ----------------------- | ------------------- | -------------------------------------------- |
| 注册           | `RegisterView.vue`      | `AuthAgent.register`| 学号校验、密码哈希、自动识别角色             |
| 登录           | `StudentLoginView.vue`  | `AuthAgent.login`   | 学号不存在时自动建账号（密码 123456）         |
| 总览           | `DashboardView.vue`     | `MasterAgent.dashboard` | 个人五育雷达、得分柱图、材料状态表       |
| 材料上传       | `MaterialsView.vue`     | `AuditAgent` / `MaterialParser` | 拖拽上传、AI 解析、风险检测、提交     |
| 我的申诉       | `AppealsView.vue`       | `AppealAgent`       | 对公示中材料提交申诉、附证据文件             |
| 一审报告确认   | `AppealsView.vue`       | `AppealAgent.confirm_review` | 对审核结果“正确/有问题”回复          |
| 公示排名       | `PublicityView.vue`     | `PublicityAgent`    | 匿名查看班级排名（学生名首字+`*`）          |
| 个人成绩单下载 | `DashboardView.vue`     | `ExportAgent`       | 导出 PDF / Excel                             |
| 智能助手       | `AiAssistantView.vue`   | `DeepSeekAgent`     | 调用 DeepSeek V4 Pro 综测问答                |
| 站内消息       | `NotificationBell.vue`  | `NotificationAgent` | 审核结果、公示发起、申诉处理等推送           |

### 5.3 关键实现细节

#### 5.3.1 材料上传与 AI 解析

`MaterialsView.vue:182-209` + `backend/app/routes/materials.py:48-59`

流程：
1. 学生拖拽或选择文件（JPG/PNG/GIF/WebP/PDF，最大 5MB）
2. 前端 `postForm('/api/materials/upload-file')` 上传文件
3. 后端 `_save_upload` 写入 `backend/app/uploads/materials/`
4. `MaterialParser.parse` 区分 PDF / 图片：
   - PDF：用 `PyPDF2` 提取文本
   - 图片：base64 编码后交给 `SiliconFlowClient`（Qwen3-VL-8B）或回退到 DeepSeek 多模态
5. `scoring_rules.score_material` 根据五育细则打分
6. 返回结构化建议 `{title, category, certificateNo, suggestedScore, level, role, reasoning, confidence, regions, scoreBasis}`
7. 前端在 `applyParsedResult` 中将结果填入表单，学生确认后再 `POST /api/materials/upload`

#### 5.3.2 风险检测

`backend/app/agents/risk_agent.py:9-32`

| 规则                  | 触发条件                              | 阻断 |
| --------------------- | ------------------------------------- | ---- |
| 重复证书编号          | `Material.certificate_no` 已存在      | 是   |
| 证书已过期            | `expires_at < today`                  | 是   |
| 发证日期晚于当前日期  | `issued_at > today`                   | 是   |

`/api/risk/inspect` 提供干跑（不阻断）；`/api/materials/upload` 内置 `assert_upload_allowed` 拦截。

#### 5.3.3 状态流转

`backend/app/agents/audit_agent.py:22-71`

`upload_material` 内部：
1. 校验 `category ∈ CATEGORY_SCORE_CAPS`（德智体美劳 + 能力）
2. 风险检测
3. `term_agent.resolve_term_id` 决定所属学期
4. `score_material` 计算分数（同赛事取最高、英语等级不累计、学科竞赛最多 5 项）
5. 写入 `Material`，状态 `DRAFT` → `SUBMITTED`（由 `assert_transition` 校验）
6. 触发站内通知（如有）

#### 5.3.4 学生一审报告

`/api/appeal/confirm-review`（`appeal_agent.py:124-163`）

学生对自己“已通过”的最新材料回复：
- **正确**：返回当前已通过总分，材料进入班级待公示库
- **有问题**：必填说明，状态跳到 `APPEALING`，自动创建 `Appeal` 记录并通知辅导员

#### 5.3.5 申诉与证据上传

`AppealsView.vue:54-72` + `backend/app/routes/appeal.py:35-43`

- 仅状态为 `公示中` 的材料可被申诉（后端 400 阻断）
- 证据文件走 `POST /api/appeal/upload-file`，落到 `uploads/appeals/`
- 申诉提交后材料状态 → `APPEALING`（自动加锁），通知对应辅导员

#### 5.3.6 学生导出

`/api/export/student-summary.<pdf|xlsx>?termId=...`

`ExportAgent.student_pdf / student_xlsx`（`agents/export_agent.py`）：

- PDF：`reportlab` 生成，分类小计 + 总分
- Excel：`openpyxl` 生成，包含五育分项、单条材料明细
- 入口按钮在 `DashboardView.vue:215-232`

---

## 六、老师端

### 6.1 入口

- 路由：`/login/teacher` → `TeacherLoginView.vue`
- 账号：长度 ≤ 6 的纯数字工号，或 `123456`（辅导员）
- 演示：`1001 / 123456`（老师）、`123456 / 123456`（辅导员）

### 6.2 功能清单

| 模块        | 前端页面               | 后端 Agent          | 功能说明                                  |
| ----------- | ---------------------- | ------------------- | ----------------------------------------- |
| 待审核列表  | `ReviewListView.vue`   | `CounselorAgent`    | 看到所有 `已提交/审核中` 材料，支持批量   |
| 审核详情    | `ReviewDetailView.vue` | `CounselorAgent`    | 查看材料、附件预览、打回/通过、调整分数   |
| 统计总览    | `DashboardView.vue`    | `StatsAgent`        | 待审、风险、Top 8、班级对比、近 14 天趋势 |
| 公示排名    | `PublicityView.vue`    | `PublicityAgent`    | 完整排行榜（实名）+ 导出                  |
| 智能助手    | `AiAssistantView.vue`  | `DeepSeekAgent`     | 与学生共用                                |
| 站内消息    | `NotificationBell.vue` | `NotificationAgent` | 审核结果回执                              |

### 6.3 关键实现细节

#### 6.3.1 待审核列表

`backend/app/agents/counselor_agent.py:16-24`

```python
def list_pending(self, user, term_id=None):
    ensure_role(user, {"teacher", "counselor"})
    query = Material.query.filter(Material.status.in_([SUBMITTED, REVIEWING]))
    if user.role == "counselor" and user.class_group_id:
        query = query.join(User, ...).filter(User.class_group_id == user.class_group_id)
    return query.order_by(updated_at.asc()).all()
```

老师看到全校/全院；辅导员自动按 `class_group_id` 过滤本班。

#### 6.3.2 审核动作

`CounselorAgent.action` 严格走状态机：

```
SUBMITTED ──领取──> REVIEWING ──┬──pass──> APPROVED   (score + scoreDelta)
                                │
                                └──reject──> REJECTED  (opinion 必填)
```

- 打回必须填意见（后端 400）
- 审核后通过 `NotificationAgent.push` 给学生发“审核通过/被打回”消息
- 写入 `ReviewRecord` 形成历史轨迹

#### 6.3.3 批量审核

`CounselorAgent.batch_action`（`counselor_agent.py:71-114`）：

- 前端 `ReviewListView.vue:57-80` 通过复选框 + 统一意见实现
- 跳过不在 SUBMITTED/REVIEWING 的材料
- 状态机不通过则跳过单条但继续处理其他
- 返回 `{count, ids}`，前端提示已处理数量

#### 6.3.4 附件在线预览

`ReviewDetailView.vue:130-173`

- 图片：`<img>` 渲染
- PDF：`<iframe>` 内嵌
- 其他：fallback 到“下载原件”

#### 6.3.5 统计总览

`StatsAgent.overview`（`agents/stats_agent.py:33-74`）：

| 维度               | SQL 聚合                                                |
| ------------------ | ------------------------------------------------------- |
| 待审/已通过/已打回 | `count(*) filter (where status=...)`                    |
| 五育分项           | `sum(score) group by category`                          |
| Top 8 学生         | `sum(score) group by user_id order by sum desc limit 8` |
| 班级对比           | `sum(score), count(distinct user) group by class_name`  |
| 近 14 天趋势       | `count(*) group by date(created_at)`                    |
| 待处理申诉         | `Appeal where status='待处理'`                          |

辅导员自动按 `class_group_id` 收窄范围；老师看全校。

---

## 七、辅导员端

### 7.1 入口

与老师共用教师登录页 `TeacherLoginView.vue`，但角色为 `counselor`：

- 账号 `123456` 演示账号（角色自动判为 counselor）
- 前端 `App.vue:51-56` 给 counselor 多出 “班级审核、申诉处理、公示发起” 菜单

### 7.2 功能清单（在老师能力基础上扩展）

| 模块        | 前端页面              | 后端 Agent          | 功能说明                                       |
| ----------- | --------------------- | ------------------- | ---------------------------------------------- |
| 班级审核    | `ReviewListView.vue`  | `CounselorAgent`    | 仅看到本班级学生提交的材料                     |
| 申诉处理    | `AppealsView.vue`     | `AppealAgent`       | 对本班学生的申诉做 accept / reject            |
| 公示发起    | `PublicityView.vue`   | `PublicityAgent`    | 预览匿名榜 → 二次确认 → 启动公示 + 3 天倒计时 |
| 公示归档    | `PublicityView.vue`   | `PublicityAgent`    | 3 天到期自动/手动归档，状态 → `公示结束`       |
| 申诉复核    | `AppealsView.vue`     | `AppealAgent.resolve` | 填写意见、accept/reject                     |
| 排名导出    | `PublicityView.vue`   | `ExportAgent`       | 导出 PDF / Excel 排行榜                        |
| 学期管理    | （隐藏 API）          | `TermAgent`         | `create/update/delete`（仅 counselor 可删）    |

### 7.3 关键实现细节

#### 7.3.1 公示发起的“双确认”机制

`PublicityAgent.start`（`publicity_agent.py:61-119`）：

1. 校验 `pending_appeals == 0`（还有未处理申诉就 400 拒绝）
2. 校验至少有 `APPROVED` 的材料（否则 400）
3. **首次调用**（`confirm != '确认公示'`）：返回 `pending_confirmation` 状态 + 匿名预览榜，前端提示“如正确请回复'确认公示'”
4. **二次调用**（`confirm == '确认公示'`）：把材料批量转为 `PUBLICIZING`、创建 `PublicityBatch`、给学生发通知

前端 `PublicityView.vue:56-76` 用 `confirmPending` ref 控制按钮文案“发起公示” → “确认公示”。

#### 7.3.2 公示倒计时

`PublicityAgent._countdown`（`publicity_agent.py:165-178`）计算剩余天/小时，`PublicityView.vue:151` 展示。

#### 7.3.3 归档

`PublicityAgent.archive`：

- 把所有 `PUBLICIZING` → `PUBLICITY_ENDED`
- `PublicityBatch.status = '已归档'`
- 给学生发“综测公示已归档”通知

#### 7.3.4 申诉处理

`AppealAgent.resolve`（`appeal_agent.py:92-122`）：

- 必填意见（前端 `AppealsView.vue:218-232` 的 textarea）
- `accept` → 申诉状态 `已通过`，材料回到 `PUBLICIZING`
- `reject` → 申诉状态 `已驳回`，材料 `PUBLICITY_ENDED`
- 给学生发“申诉已复核”通知

#### 7.3.5 申诉通知辅导员

`AppealAgent._notify_counselor`（`appeal_agent.py:165-179`）：

- 给所有 `counselor` 角色的用户发 `appeal_submitted` 通知
- 辅导员绑定 `class_group_id` 时按班级过滤

#### 7.3.6 学期管理

`TermAgent.create/update/delete`：

- 创建/更新：仅 `teacher` 或 `counselor`
- 删除：仅 `counselor`，且 `materials / appeals` 为空才允许
- `isCurrent=True` 时自动把其他学期置为非当前
- 启动时 `_ensure_default_term` 按月份自动建一个“2024-2025 学年上/下学期”

---

## 八、通用能力

### 8.1 智能助手（AI Assistant）

- 路由：`/ai`
- 后端：`/api/ai/status`、`/api/ai/chat`
- 模型：`DeepSeek V4 Pro`（OpenAI 兼容协议）
- 提示词：`agents/scoring_rules_prompt.md` 注入完整五育评分规则，保证答案与系统一致
- 上下文：仅保留最近 10 条（`MAX_MESSAGES=12`），单条 4000 字符
- 前端：`AiAssistantView.vue` 显示 token 消耗、模型名、状态

### 8.2 站内消息

- 路由：`/api/notifications/*`
- 前端：`NotificationBell.vue` 悬浮卡片 + 角标
- 推送点：审核通过/打回、申诉提交/复核、公示发起/归档
- API：列表、未读数、标记单条已读、全部已读、删除

### 8.3 数据导出

| 接口                                            | 角色限制           | 格式         | 内容                       |
| ----------------------------------------------- | ------------------ | ------------ | -------------------------- |
| `/api/export/student-summary.<pdf\|xlsx>`       | `student`          | PDF / Excel  | 个人五育分项 + 总分 + 明细 |
| `/api/export/ranking.<pdf\|xlsx>`               | `teacher` / `counselor` | PDF / Excel  | 班级/全校排行榜          |

实现：`openpyxl`（Excel）+ `reportlab`（PDF，含中文字体 `UnicodeCIDFont`）。

### 8.4 统计与图表

- `/api/stats/overview` → 老师/辅导员用
- `/api/stats/student` → 学生用
- 前端用 `Chart.js + vue-chartjs` 渲染：柱图、饼图、折线、雷达（`DashboardView.vue` + `components/ChartView.vue`）

### 8.5 外部 API（Open API）

`/api/external/*` 由 `backend/app/routes/external.py` 提供，用 API Key 鉴权（`Bearer zce_xxx`）：

| 端点                                        | 用途                          |
| ------------------------------------------- | ----------------------------- |
| `POST/GET/DELETE /api/external/api-keys`    | 创建/列出/删除 API Key        |
| `GET /api/external/users`                   | 用户列表                      |
| `GET /api/external/students/{no}/summary`    | 学生综测汇总                  |
| `GET /api/external/students/{no}/materials` | 学生材料列表                  |
| `GET/POST /api/external/materials`          | 列表/录入材料                 |
| `GET /api/external/publicity/rankings`      | 公开排行榜                    |
| `GET /api/external/publicity/batches`       | 公示批次                      |
| `GET /api/external/stats/overview`          | 概览统计                      |
| `POST /api/external/ai/chat`                | 透传 DeepSeek 调用            |

可对接第三方 BI、OA、教务系统。

---

## 九、数据模型

`backend/app/models.py` — SQLAlchemy ORM 全部表：

| 表                   | 模型            | 关键字段                                                                 |
| -------------------- | --------------- | ------------------------------------------------------------------------ |
| `terms`              | `Term`          | `id, name, academic_year, semester_type, starts_at, ends_at, is_current` |
| `colleges`           | `College`       | `id, name, code`                                                         |
| `majors`             | `Major`         | `id, college_id, name, code`                                             |
| `class_groups`       | `ClassGroup`    | `id, major_id, name, grade_year, counselor_id`                           |
| `users`              | `User`          | `id, student_no, name, password_hash, role, class_name, *_id`            |
| `materials`          | `Material`      | `id, student_id, term_id, title, category, certificate_no, score, status, risk_level, risk_reasons, ocr_text, file_url` |
| `review_records`     | `ReviewRecord`  | `id, material_id, reviewer_id, action, opinion, score_delta`             |
| `appeals`            | `Appeal`        | `id, material_id, student_id, term_id, reason, evidence_files, status, result_opinion` |
| `notifications`      | `Notification`  | `id, user_id, type, title, content, link, related_id, is_read`           |
| `publicity_batches`  | `PublicityBatch`| `id, title, class_name, status, starts_at, ends_at, created_by_id, archived_at` |
| `api_keys`           | `ApiKey`        | `id, name, key_hash, role, is_active, last_used_at`                      |

`User` 通过 `password_hash`（`werkzeug.security.generate_password_hash`）安全存储密码，登录时 `check_password`。

---

## 十、接口约定

### 10.1 鉴权

- `POST /api/auth/login` 成功后返回 `{token, user, menus}`
- Token 通过 `Authorization: Bearer <token>` 携带
- 12 小时有效期
- `helpers.py::current_user` 统一解析 + 抛 401

### 10.2 错误处理

`backend/app/__init__.py` 注册了 3 个错误处理器：

| 异常                  | HTTP | 响应                       |
| --------------------- | ---- | -------------------------- |
| `HTTPException`       | 原码 | `{message, status}`        |
| `StateMachineError`   | 400  | `{message, status: 400}`   |
| `ValueError`          | 400  | `{message, status: 400}`   |

前端 `apiFetch` 统一从 `payload.message` 取错误文案。

### 10.3 前端 API 封装

`frontend/src/api/client.ts`：

- `apiFetch<T>(url)` → `fetch` + `Authorization` + 401 自动跳登录
- `postJson<T>(url, body)` → 同上 + `Content-Type: application/json`
- `postForm<T>(url, FormData)` → 文件上传

---

## 十一、前端实现要点

### 11.1 路由

`frontend/src/router/index.ts`

- 7 条主路由 + 4 条公共路由
- `router.beforeEach` 统一鉴权：`meta.public` 标记的页面在已登录时自动跳 `/dashboard`

### 11.2 状态管理（Pinia）

| Store            | 文件                          | 职责                                  |
| ---------------- | ----------------------------- | ------------------------------------- |
| `useSessionStore`| `stores/session.ts`           | token、user、loginPath 持久化到 sessionStorage |
| `useTermStore`   | `stores/term.ts`              | 当前学期 ID，term 选择器持久化        |
| `useNotificationStore` | `stores/notification.ts` | 通知列表/未读数                       |

### 11.3 通用组件

| 组件                  | 用途                                                                 |
| --------------------- | -------------------------------------------------------------------- |
| `App.vue`             | 壳布局（侧边栏 + 移动端 App Bar + 抽屉）                             |
| `StatusTag.vue`       | 状态中文标签 + 颜色                                                  |
| `EmptyState.vue`      | 空数据占位                                                            |
| `TermSelector.vue`    | 学期切换器                                                            |
| `ChartView.vue`       | Chart.js 封装                                                         |
| `NotificationBell.vue`| 通知铃铛 + 下拉                                                       |

### 11.4 视觉与样式

详见 `docs/frontend-design.md`：

- CSS 变量集中管理（`--primary` `#2663eb` + `--accent` `#0f766e` + `--sidebar-bg` `#172033`）
- 三类 surface：`.surface-panel` / `.surface-card` / `.surface-muted`
- `:focus-visible` 焦点环（键盘友好）
- `prefers-color-scheme: dark` 已预留扩展点
- 三个断点：1200px / 920px / 560px

### 11.5 持久化

- `sessionStorage.zc_token` / `zc_user` / `zc_portal`
- 退出时统一清理

---

## 十二、部署与演示账号

### 12.1 后端启动

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python run.py
```

默认连接 `postgresql+psycopg://postgres:123456@localhost:5432/zong_ce`

### 12.2 前端启动

```bash
npm install
npm run dev          # 5173
npm run dev:5174     # 备用端口
```

### 12.3 演示数据

```bash
cd backend
.venv/bin/python scripts/seed_demo.py
```

### 12.4 演示账号

| 角色         | 学/工号      | 密码    |
| ------------ | ------------ | ------- |
| 学生         | `2023001001` | `123456` |
| 老师         | `1001`       | `123456` |
| 辅导员       | `123456`     | `123456` |

### 12.5 DeepSeek 接入

`.env` 中配置：

```text
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro
DEEPSEEK_TIMEOUT=30
```

未配置时 `GET /api/ai/status` 会返回 `configured: false`，前端禁用发送按钮。

### 12.6 文件上传

- 上传目录：`backend/app/uploads/{materials,appeals}/`
- 大小限制：5MB
- 允许类型：JPG / PNG / GIF / WebP / PDF
- 静态访问：`/api/materials/uploads/<sub>/<file>`

---

## 附录：模块边界一览（来源 README）

| Agent              | 接口前缀           |
| ------------------ | ------------------ |
| Auth Agent         | `/api/auth/*`      |
| Audit Agent        | `/api/materials/*` |
| Counselor Agent    | `/api/review/*`    |
| Appeal Agent       | `/api/appeal/*`    |
| Publicity Agent    | `/api/publicity/*` |
| Risk Agent         | `/api/risk/*`      |
| DeepSeek Agent     | `/api/ai/*`        |
| Term Agent         | `/api/terms/*`     |
| Organization Agent | `/api/organization/*` |
| Notification Agent | `/api/notifications/*` |
| Export Agent       | `/api/export/*`    |
| Master Agent       | （无独立接口，按角色聚合） |
