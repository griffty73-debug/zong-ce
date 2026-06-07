# 高校综测系统

一个按“总控调度官 + Worker Agent”拆分的高校综合测评系统。前端使用 Vue 3 + TypeScript + Vite，后端使用 Flask + PostgreSQL。

## 模块边界

- Auth Agent：注册、登录、学工号校验、角色识别，接口 `/api/auth/*`
- Audit Agent：材料上传、OCR 基础解析、五育评分、唯一加分限制，接口 `/api/materials/*`
- Counselor Agent：材料审核、打回、意见记录，一审报告数据，接口 `/api/review/*`
- Appeal Agent：学生申诉、复核处理，接口 `/api/appeal/*`
- Publicity Agent：公示发起、降序排名、匿名看榜、归档，接口 `/api/publicity/*`
- Risk Agent：重复证书、过期证书、未来日期拦截，接口 `/api/risk/*`
- DeepSeek Agent：接入 DeepSeek V4 Pro，提供综测智能问答与分析，接口 `/api/ai/*`
- Term Agent：学期/测评周期管理与过滤，接口 `/api/terms/*`
- Organization Agent：学院 / 专业 / 班级三级组织架构，接口 `/api/organization/*`
- Notification Agent：站内消息与提醒，接口 `/api/notifications/*`
- Export Agent：学生 / 班级综测成绩单 PDF 与 Excel 导出，接口 `/api/export/*`
- Master Agent：按角色并行汇总 Worker Agent 结果，供工作台使用

## 状态机

`草稿 -> 已提交 -> 审核中 -> 已通过 / 已打回 -> 公示中 -> 公示结束 / 申诉处理中`

已实现规则：

- 禁止跨阶段跳跃
- 公示中、公示结束、申诉处理中材料锁定
- 上传时拦截重复证书、过期证书和未来发证日期
- 审核打回必须填写原因
- 申诉仅在公示中生效

## 后端启动

```bash
cd /Users/yang/Dev/zong_ce/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python run.py
```

默认连接：

```text
postgresql+psycopg://postgres:123456@localhost:5432/zong_ce
```

如需覆盖配置，复制 `backend/.env.example` 为 `backend/.env` 后修改。本机已写入 `backend/.env`，使用当前 PostgreSQL 角色 `yang` 连接 `zong_ce`。

DeepSeek V4 Pro 由后端私有环境变量配置：

```text
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro
DEEPSEEK_TIMEOUT=30
```

接口：

- `GET /api/ai/status`：查看模型是否已配置
- `POST /api/ai/chat`：登录后调用 DeepSeek V4 Pro 进行综测智能问答

## 材料智能解析

学生端“材料上传”页面支持拖拽或点击上传图片/PDF，后端接口会读取文件内容并调用 DeepSeek V4 Pro 返回结构化建议，再由学生确认后填入原提交表单。

```http
POST /api/materials/upload-file
Authorization: Bearer <token>
Content-Type: multipart/form-data
```

限制：

- 支持 `JPG / PNG / GIF / WebP / PDF`
- 单文件最大 `5MB`
- PDF 使用 `PyPDF2` 提取文本后分析
- 图片按 OpenAI-compatible 多模态消息发送给 DeepSeek；若上游不支持图片输入，会返回明确错误

初始化演示数据：

```bash
cd /Users/yang/Dev/zong_ce/backend
.venv/bin/python scripts/seed_demo.py
```

演示账号：

- 学生：`2023001001 / 123456`
- 老师：`1001 / 123456`
- 辅导员：`123456 / 123456`

## 前端启动

```bash
cd /Users/yang/Dev/zong_ce
npm install
npm run dev
```

访问 [http://127.0.0.1:5173](http://127.0.0.1:5173)。

如果 `5173` 已被占用，可以使用固定备用端口：

```bash
npm run dev:5174
```

访问 [http://127.0.0.1:5174](http://127.0.0.1:5174)。

## 主要页面

- 学生端：登录、注册、材料上传、我的综测、申诉、公示查看
- 老师端：待审核列表、审核详情、统计总览
- 辅导员端：班级总览、公示发起、申诉处理、排行榜
