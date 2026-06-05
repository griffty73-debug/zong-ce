# 高校综测系统

一个按“总控调度官 + Worker Agent”拆分的高校综合测评系统。前端使用 Vue 3 + TypeScript + Vite，后端使用 Flask + PostgreSQL。

## 模块边界

- Auth Agent：注册、登录、学工号校验、角色识别，接口 `/api/auth/*`
- Audit Agent：材料上传、OCR 基础解析、五育评分、唯一加分限制，接口 `/api/materials/*`
- Counselor Agent：材料审核、打回、意见记录，一审报告数据，接口 `/api/review/*`
- Appeal Agent：学生申诉、复核处理，接口 `/api/appeal/*`
- Publicity Agent：公示发起、降序排名、匿名看榜、归档，接口 `/api/publicity/*`
- Risk Agent：重复证书、过期证书、未来日期拦截，接口 `/api/risk/*`
- Gesture Agent：手势识别结果解析、置信度过滤、防抖、二次确认、Agent 路由，接口 `/api/gesture/*`
- DeepSeek Agent：接入 DeepSeek V4 Pro，提供综测智能问答与分析，接口 `/api/ai/*`
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

## 手势调度接口

入口：

```http
POST /api/gesture/dispatch
Authorization: Bearer <token>
Content-Type: application/json
```

基础输入兼容前端摄像头动作捕捉输出：

```json
{
  "userId": "2023001001",
  "role": "student",
  "page": "publicity",
  "gesture": "SWIPE_RIGHT",
  "confidence": 0.9,
  "timestamp": 1710000000,
  "context": {
    "pageIndex": 1,
    "pageSize": 8
  }
}
```

已实现规则：

- 置信度阈值：`OPEN_PALM 0.85`、`FIST 0.8`、`OK_SIGN 0.9`、`POINT 0.8`、`SWIPE 0.75`
- 同一用户、同一页面、同一手势 2 秒内重复会被忽略
- 高风险操作 `REJECT_MATERIAL`、`SUBMIT_APPEAL` 会返回二次确认令牌
- 二次确认可保持原手势 3 秒后重发，或使用 `OK_SIGN + confirmToken`
- 公示中、公示结束、申诉处理中禁止审核写操作
- 学生端材料上传页不接入摄像头动作捕捉，材料提交仍通过上传表单完成
- 学生端公示榜、总览材料列表、申诉列表支持真实摄像头动作捕捉：左扇上一页，右扇下一页，上扇上划，下扇下划

前端动作捕捉基于浏览器摄像头权限，在业务列表页点击“启动动作捕捉”后，以 `96x72` 帧差、亮度阈值和低通滤波计算扇动方向，再调用 `/api/gesture/dispatch` 返回 Agent 调度结果。

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
