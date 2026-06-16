# 高校综测系统 — 系统架构·技术栈·功能设计·API 参考

## 一、项目概述

**高校综测系统**是一个基于 AI 的高校综合测评管理平台，支持材料上传与智能解析、五育评分、多级审核、公示排名、申诉处理、数据导出等全流程管理。

---

## 二、技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| **后端框架** | Flask + Flask-SQLAlchemy | 3.1.x |
| **WSGI 服务器** | Gunicorn | 26.0 |
| **进程管理** | systemd | — |
| **Web 服务器** | Nginx | 1.24 |
| **数据库** | PostgreSQL (psycopg) | 3.2 |
| **前端框架** | Vue 3 + TypeScript | 3.5 |
| **构建工具** | Vite | 6.0 |
| **状态管理** | Pinia | 2.3 |
| **路由** | Vue Router | 4.5 |
| **图表** | Chart.js + vue-chartjs | 4.4 / 5.3 |
| **图标** | lucide-vue-next | 0.468 |
| **AI 服务** | DeepSeek V4 Pro + SiliconFlow Qwen3-VL | — |
| **认证** | JWT (itsdangerous URLSafeTimedSerializer) | — |
| **PDF 导出** | ReportLab | 4.2 |
| **Excel 导出** | openpyxl | 3.1 |
| **PDF 解析** | PyPDF2 | 3.0 |

---

## 三、系统架构

### 3.1 整体拓扑

```
┌──────────────────────────────────────────────────┐
│                     浏览器                         │
└────────────────────┬─────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────┐
│                 Nginx (Port 80)                    │
│  /          → 静态文件 (/var/www/html/zong-ce/)    │
│  /api/*     → proxy_pass → 127.0.0.1:5003         │
└────────────────────┬─────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────┐
│         Gunicorn (2 workers, systemd)              │
│         Flask App (create_app 工厂函数)             │
│         run:app @ 127.0.0.1:5003                  │
└────────┬───────────────────────┬──────────────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐   ┌─────────────────────────┐
│   PostgreSQL     │   │  外部 AI 服务              │
│   127.0.0.1:5432 │   │  DeepSeek V4 Pro         │
│   数据库: zong_ce │   │  SiliconFlow Qwen3-VL    │
└─────────────────┘   └─────────────────────────┘
```

### 3.2 后端分层架构

```
backend/
├── run.py                    # 入口 (create_app)
├── app/
│   ├── __init__.py           # App 工厂, 蓝图注册, DB 初始化
│   ├── config.py             # 配置 (环境变量)
│   ├── extensions.py         # SQLAlchemy 扩展
│   ├── models.py             # 11 个数据模型
│   ├── state_machine.py      # 材料状态机 (8 种状态)
│   ├── routes/
│   │   ├── helpers.py        # JWT 解析, 通用工具
│   │   ├── auth.py           # 认证接口
│   │   ├── materials.py      # 材料接口
│   │   ├── review.py         # 审核接口
│   │   ├── appeal.py         # 申诉接口
│   │   ├── publicity.py      # 公示接口
│   │   ├── risk.py           # 风险检测接口
│   │   ├── ai.py             # AI 接口
│   │   ├── terms.py          # 学期管理接口
│   │   ├── organization.py   # 组织架构接口
│   │   ├── notifications.py  # 通知接口
│   │   ├── export.py         # 导出接口
│   │   ├── stats.py          # 统计接口
│   │   └── external.py       # 外部 API 接口
│   └── agents/
│       ├── common.py         # 角色推断, 通用工具
│       ├── scoring_rules.py  # 五育评分规则引擎
│       ├── responses.py      # 统一响应格式
│       ├── deepseek_client.py    # DeepSeek HTTP 客户端
│       ├── siliconflow_client.py # SiliconFlow HTTP 客户端
│       ├── master_agent.py   # 总控调度官
│       ├── auth_agent.py     # 认证 Agent
│       ├── audit_agent.py    # 材料审计 Agent
│       ├── counselor_agent.py# 辅导员审核 Agent
│       ├── appeal_agent.py   # 申诉处理 Agent
│       ├── publicity_agent.py# 公示管理 Agent
│       ├── risk_agent.py     # 风险检测 Agent
│       ├── deepseek_agent.py # AI 对话 Agent
│       ├── material_parser.py# 材料智能解析
│       ├── stats_agent.py    # 统计 Agent
│       ├── export_agent.py   # 导出 Agent
│       ├── notification_agent.py # 通知 Agent
│       ├── organization_agent.py # 组织架构 Agent
│       └── term_agent.py     # 学期管理 Agent
```

### 3.3 Agent 架构 (总控调度官 + Worker Agent)

```
                    MasterAgent (总控调度官)
                    ThreadPoolExecutor(max_workers=3)
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
   AuthAgent           AuditAgent         CounselorAgent
        │                   │                   │
   AppealAgent        PublicityAgent       RiskAgent
        │                   │                   │
   DeepSeekAgent      StatsAgent          ExportAgent
        │                   │                   │
NotificationAgent   OrganizationAgent     TermAgent
                            │
                    MaterialParser
                    (DeepSeek + SiliconFlow)
```

---

## 四、功能设计

### 4.1 角色体系

| 角色 | 学号规则 | 核心功能 |
|------|----------|----------|
| **学生** | `20` 开头 + 10 位数字 | 材料上传、智能解析、申诉、查看公示排名 |
| **老师** | 任意 1-6 位字符 | 材料审核（单件/批量） |
| **辅导员** | `123456` | 材料审核、公示发起/归档、申诉处理、组织架构管理 |

### 4.2 材料状态机

```
┌──────┐   提交    ┌────────┐   审核    ┌────────┐
│ 草稿 │ ──────→ │ 已提交 │ ──────→ │ 审核中 │
└──┬───┘         └────────┘         └───┬────┘
   ▲                                    │
   │ 打回                                ├── 通过 → ┌────────┐
   │                                    │          │ 已通过 │
   └────────────────────────────────────┘          └───┬────┘
                                                       │
                                      ┌────────────────┼────────────────┐
                                      ▼                ▼                ▼
                                 ┌────────┐     ┌──────────┐    ┌──────────┐
                                 │ 公示中 │ ←── │申诉处理中│    │ 公示结束 │
                                 └───┬────┘     └──────────┘    └──────────┘
                                     │               │
                                     └── 归档 ───────┘
```

**锁定的状态** (不可修改材料): `公示中` `公示结束` `申诉处理中`

### 4.3 五育评分体系

| 类别 | 满分 | 评分依据 |
|------|------|----------|
| 德育 | 15.0 | 思政活动、志愿服务、荣誉称号 |
| 智育 | 20.0 | 学术竞赛、论文发表、英语四六级、SRP 项目 |
| 体育 | 8.0 | 体育竞赛、运动会 |
| 美育 | 6.0 | 文艺比赛、文艺活动 |
| 劳育 | 6.0 | 社会实践、劳动实践 |
| 能力 | 8.0 | 学生干部、社团职务 |

**评分规则:**
- 基于关键词匹配的规则引擎，按国家级/省级/市级/校级/院级等级打分
- 队长/负责人 得满分，普通成员 ×0.7
- 英语证书取最高分 (CET-4=2, CET-6=3)
- 同赛事取最高分，竞赛上限 5 项
- 无匹配规则时标记为"人工预估材料"

### 4.4 风险检测

| 检测项 | 说明 |
|--------|------|
| 重复证书 | 相同证书编号已存在于系统中 |
| 过期证书 | 证书有效期已过 |
| 未来日期 | 发证日期晚于当前日期 |

高风险材料在提交时被拦截并返回 422。

### 4.5 智能材料解析

```
上传图片/PDF → 提取内容 → AI 结构化解析 → 用户确认 → 提交
    │              │              │
    ▼              ▼              ▼
 图片: SiliconFlow  PDF: DeepSeek  JSON: title, category,
 Qwen3-VL 视觉识别 文本提取+分析    certificateNo, score...
```

- 支持格式: JPG / PNG / GIF / WebP / PDF
- 单文件最大 5MB
- 解析结果由用户确认后填入表单

### 4.6 公示与申诉

- **公示发起**: 辅导员选择班级，输入公示标题，系统自动生成降序排行榜
- **匿名看榜**: 公示排名对学生隐藏姓名，仅显示学号末位
- **申诉**: 仅在公示期间可发起，支持上传佐证材料
- **申诉处理**: 辅导员可接受(回到公示中)或驳回(进入公示结束)

### 4.7 数据导出

- 学生综测成绩单: PDF / Excel
- 班级排名: PDF / Excel
- 支持图表嵌入 (雷达图、柱状图等)

---

## 五、外部 API 调用

### 5.1 DeepSeek V4 Pro

| 项目 | 配置 |
|------|------|
| **端点** | `https://api.deepseek.com/chat/completions` |
| **模型** | `deepseek-v4-pro` (可配置) |
| **认证** | `Bearer <DEEPSEEK_API_KEY>` |
| **超时** | 30s (对话) / 60s (材料解析) |
| **用途** | AI 智能问答 (带综测规则 system prompt)、PDF 文本结构化提取 |

调用方式: `POST {base_url}/chat/completions`，标准 OpenAI-compatible 格式。

### 5.2 SiliconFlow (Qwen3-VL Vision)

| 项目 | 配置 |
|------|------|
| **端点** | `https://api.siliconflow.cn/v1/chat/completions` |
| **模型** | `Qwen/Qwen3-VL-8B-Instruct` (可配置) |
| **认证** | `Bearer <SILICONFLOW_API_KEY>` |
| **超时** | 60s |
| **用途** | 图片 OCR 识别，提取证书标题/编号/颁发单位，区域检测 |

图片以 base64 编码发送，未配置 SiliconFlow 时回退为纯文本模式。

---

## 六、数据库模型

### 6.1 表关系图

```
colleges ──┐
           │ 1:N
majors ────┤
           │ 1:N
class_groups ──┐
               │ 1:N
users ─────────┘
   │
   ├── 1:N → materials ── 1:N → review_records
   │              │
   │              └── 1:N → appeals
   │
   ├── 1:N → notifications
   │
   └── 1:N → publicity_batches (created_by)

terms ── 1:N → materials
terms ── 1:N → appeals

api_keys (独立)
```

### 6.2 表清单

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| `terms` | 学期/测评周期 | name, academic_year, is_current, status |
| `colleges` | 学院 | name, code |
| `majors` | 专业 | name, code, college_id |
| `class_groups` | 班级 | name, major_id, counselor_id |
| `users` | 用户 | student_no, name, password_hash, role, college_id, major_id, class_group_id |
| `materials` | 综测材料 | title, category, certificate_no, score, status, risk_level, term_id |
| `review_records` | 审核记录 | material_id, reviewer_id, action, opinion |
| `appeals` | 申诉 | material_id, student_id, reason, status, evidence_files |
| `notifications` | 站内通知 | user_id, type, title, content, is_read |
| `publicity_batches` | 公示批次 | title, class_name, status, starts_at, ends_at |
| `api_keys` | 外部 API 密钥 | name, key_hash, role, is_active |

---

## 七、API 接口参考

### 7.1 认证 `/api/auth`

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `POST` | `/api/auth/register` | 无 | 注册用户 (自动推断角色) |
| `POST` | `/api/auth/login` | 无 | 登录 (返回 JWT) |
| `GET` | `/api/auth/me` | JWT | 当前用户信息 + 仪表盘数据 |

### 7.2 材料 `/api/materials`

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `POST` | `/api/materials/upload` | 学生 | 提交材料 (手动填写) |
| `POST` | `/api/materials/upload-file` | 学生 | 上传文件并 AI 解析 |
| `GET` | `/api/materials/list?termId=` | JWT | 材料列表 (按角色过滤) |
| `GET` | `/api/materials/summary` | 学生 | 学生综测总览 |

### 7.3 审核 `/api/review`

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/api/review/list?termId=` | 教师/辅导员 | 待审材料列表 |
| `GET` | `/api/review/detail/<id>` | 教师/辅导员 | 材料详情 + 审核历史 |
| `POST` | `/api/review/action` | 教师/辅导员 | 单件审核 (通过/打回) |
| `POST` | `/api/review/batch-action` | 教师/辅导员 | 批量审核 |

### 7.4 申诉 `/api/appeal`

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `POST` | `/api/appeal/submit` | 学生 | 提交申诉 |
| `GET` | `/api/appeal/list?termId=` | JWT | 申诉列表 |
| `GET` | `/api/appeal/detail/<id>` | JWT | 申诉详情 |
| `POST` | `/api/appeal/resolve` | 教师/辅导员 | 处理申诉 |
| `POST` | `/api/appeal/confirm-review` | 学生 | 学生对复议结果确认 |
| `POST` | `/api/appeal/upload-file` | 学生 | 申诉证据上传 |

### 7.5 公示 `/api/publicity`

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/api/publicity/rank?termId=` | JWT | 公示排名 (匿名) |
| `POST` | `/api/publicity/start` | 辅导员 | 发起公示批次 |
| `POST` | `/api/publicity/archive` | 辅导员 | 归档公示批次 |

### 7.6 风险检测 `/api/risk`

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `POST` | `/api/risk/inspect` | JWT | 检测单件材料风险 |
| `GET` | `/api/risk/report` | JWT | 风险报告 (所有非低风险材料) |

### 7.7 AI `/api/ai`

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/api/ai/status` | JWT | AI 服务状态 |
| `POST` | `/api/ai/chat` | JWT | AI 对话 (含综测规则 system prompt) |

### 7.8 学期管理 `/api/terms`

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/api/terms/list` | JWT | 学期列表 |
| `GET` | `/api/terms/current` | JWT | 当前学期 |
| `POST` | `/api/terms/` | 教师/辅导员 | 创建学期 |
| `PATCH` | `/api/terms/<id>` | 教师/辅导员 | 更新学期 |
| `DELETE` | `/api/terms/<id>` | 辅导员 | 删除学期 |

### 7.9 组织架构 `/api/organization`

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/api/organization/colleges` | JWT | 学院列表 |
| `POST` | `/api/organization/colleges` | 辅导员 | 创建学院 |
| `GET` | `/api/organization/majors?collegeId=` | JWT | 专业列表 |
| `POST` | `/api/organization/majors` | 辅导员 | 创建专业 |
| `GET` | `/api/organization/classes?majorId=` | JWT | 班级列表 |
| `POST` | `/api/organization/classes` | 辅导员 | 创建班级 |
| `GET` | `/api/organization/tree` | JWT | 完整组织树 |

### 7.10 通知 `/api/notifications`

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/api/notifications/list` | JWT | 通知列表 (最多80条) |
| `GET` | `/api/notifications/unread-count` | JWT | 未读数量 |
| `POST` | `/api/notifications/<id>/read` | JWT | 标记已读 |
| `POST` | `/api/notifications/read-all` | JWT | 全部已读 |
| `DELETE` | `/api/notifications/<id>` | JWT | 删除通知 |

### 7.11 导出 `/api/export`

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/api/export/student-summary.pdf` | 学生 | 学生成绩单 PDF |
| `GET` | `/api/export/student-summary.xlsx` | 学生 | 学生成绩单 Excel |
| `GET` | `/api/export/ranking.pdf` | 教师/辅导员 | 排名 PDF |
| `GET` | `/api/export/ranking.xlsx` | 教师/辅导员 | 排名 Excel |

### 7.12 统计 `/api/stats`

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/api/stats/overview` | 教师/辅导员 | 仪表盘统计 |
| `GET` | `/api/stats/student` | 学生 | 个人统计 (雷达图) |

### 7.13 外部 API `/api/external`

外部 API 使用 `Bearer <api_key>` 认证 (非 JWT)。

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/external/api-keys` | 创建 API 密钥 |
| `GET` | `/api/external/api-keys` | 密钥列表 |
| `DELETE` | `/api/external/api-keys/<id>` | 删除密钥 |
| `GET` | `/api/external/users?role=` | 用户列表 |
| `GET` | `/api/external/users/<id>` | 用户详情 |
| `GET` | `/api/external/students/<no>/summary` | 学生成绩汇总 |
| `GET` | `/api/external/students/<no>/materials` | 学生材料列表 |
| `GET` | `/api/external/materials?status=&category=` | 材料列表 |
| `GET` | `/api/external/materials/<id>` | 材料详情 |
| `POST` | `/api/external/materials` | 创建材料 |
| `GET` | `/api/external/publicity/rankings` | 公示排名 |
| `GET` | `/api/external/publicity/batches` | 公示批次 |
| `GET` | `/api/external/stats/overview` | 快速统计 |
| `POST` | `/api/external/ai/chat` | AI 对话 |

### 7.14 其他

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/health` | 健康检查 |

---

## 八、认证机制

### 8.1 JWT 认证 (内部 API)

- **库**: `itsdangerous.URLSafeTimedSerializer`
- **过期**: 12 小时
- **载荷**: `{"id": user.id, "role": user.role}`
- **传递**: `Authorization: Bearer <token>`
- **密码**: `werkzeug.security` 哈希

### 8.2 API Key 认证 (外部 API)

- **格式**: `zce_` + 32 字节 url-safe 随机串
- **存储**: SHA-256 哈希
- **传递**: `Authorization: Bearer <api_key>`
- 记录 `last_used_at` 最后使用时间

---

## 九、前端架构

### 9.1 路由表

| 路径 | 页面 | 权限 |
|------|------|------|
| `/login/student` | 学生登录 | 公开 |
| `/login/teacher` | 教师/辅导员登录 | 公开 |
| `/register` | 注册 | 公开 |
| `/dashboard` | 工作台 | 需登录 |
| `/materials` | 材料上传 | 学生 |
| `/review` | 审核列表 | 教师/辅导员 |
| `/review/:id` | 审核详情 | 教师/辅导员 |
| `/appeals` | 申诉管理 | 需登录 |
| `/publicity` | 公示排名 | 需登录 |
| `/ai` | AI 助手 | 需登录 |

路由守卫: 未登录 → 跳转登录页；已登录访问公开页 → 跳转工作台。

### 9.2 导航菜单 (按角色)

| 学生 | 教师 | 辅导员 |
|------|------|--------|
| 总览 | 总览 | 总览 |
| 公示排名 | 公示排名 | 公示排名 |
| 智能助手 | 智能助手 | 智能助手 |
| 材料上传 | 材料审核 | 班级审核 |
| 我的申诉 | | 申诉处理 |
| | | 公示发起 |

### 9.3 状态管理

- **Session Store**: 登录态 (JWT / 用户信息)，持久化到 sessionStorage
- **Term Store**: 当前学期选择，跨组件通信
- **Notification Store**: 通知轮询 (30s 间隔)

---

## 十、数据统计

| 指标 | 数量 |
|------|------|
| API 端点 | 55+ |
| 数据库表 | 11 |
| Agent 类 | 14 |
| 前端路由 | 12 |
| 前端视图 | 11 |
| 外部 AI 集成 | 2 (DeepSeek, SiliconFlow) |
| 材料状态 | 8 |
| 评分类别 | 6 (五育 + 能力) |
