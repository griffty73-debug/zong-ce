# 部署说明

## 架构概览

```
Internet
  │
  ▼
Nginx (port 80)
├── /         → 静态文件 (Vue 前端构建产物)
└── /api/*    → 反向代理 → Gunicorn @ 127.0.0.1:5003
                              │
                              ▼
                         Flask 后端 (systemd 管理)
                              │
                              ▼
                         PostgreSQL @ 127.0.0.1:5432
```

- **Web Server**: Nginx — 反向代理 + 静态文件服务
- **WSGI Server**: Gunicorn — 运行 Flask 应用，2 workers，绑定 127.0.0.1:5003
- **进程管理**: systemd — 管理 Gunicorn 进程，异常自动重启
- **数据库**: PostgreSQL — 本地实例，数据库名 `zong_ce`

---

## 环境要求

| 软件 | 版本 |
|------|------|
| Ubuntu | 22.04+ |
| Python | 3.10+ |
| Node.js | 18+ |
| PostgreSQL | 14+ |
| Nginx | 1.24+ |
| Git | 2.x |

---

## 一、首次部署

### 1.1 克隆项目

```bash
git clone <repo-url> /home/ubuntu/zong_ce
cd /home/ubuntu/zong_ce
```

### 1.2 安装系统依赖

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx postgresql postgresql-client nodejs npm
```

### 1.3 配置 PostgreSQL

```bash
sudo -u postgres psql
```

```sql
CREATE USER postgres WITH PASSWORD 'your-password';
CREATE DATABASE zong_ce OWNER postgres;
GRANT ALL PRIVILEGES ON DATABASE zong_ce TO postgres;
\q
```

### 1.4 配置后端

```bash
cd /home/ubuntu/zong_ce/backend

# 创建虚拟环境并安装依赖
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install gunicorn

# 配置环境变量
cp .env.example .env
```

编辑 `.env` 文件，修改以下内容：

```env
DATABASE_URL=postgresql+psycopg://postgres:your-password@127.0.0.1:5432/zong_ce
SECRET_KEY=<生成一个随机密钥>
FLASK_ENV=production
DEEPSEEK_API_KEY=<你的 DeepSeek API Key>
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro
DEEPSEEK_TIMEOUT=30
```

生成随机密钥：
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 1.5 初始化数据库表

Gunicorn 启动时会自动调用 `create_app()` 创建表结构（Flask-SQLAlchemy `create_all`），无需手动建表。

如需导入演示数据：
```bash
cd /home/ubuntu/zong_ce/backend
.venv/bin/python scripts/seed_demo.py
```

### 1.6 配置 systemd 服务

创建 `/etc/systemd/system/zong-ce-backend.service`：

```ini
[Unit]
Description=Zong-ce Backend Flask App
After=network.target postgresql.service

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/zong_ce/backend
Environment="PATH=/home/ubuntu/zong_ce/backend/.venv/bin"
ExecStart=/home/ubuntu/zong_ce/backend/.venv/bin/gunicorn -w 2 -b 127.0.0.1:5003 --timeout 60 run:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启用并启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable zong-ce-backend
sudo systemctl start zong-ce-backend
```

验证：
```bash
sudo systemctl status zong-ce-backend
curl http://127.0.0.1:5003/api/auth/status
```

### 1.7 构建前端

```bash
cd /home/ubuntu/zong_ce
npm install
npm run build
```

构建产物位于 `frontend/dist/`。

### 1.8 配置 Nginx

创建 `/etc/nginx/sites-available/zong-ce`：

```nginx
client_max_body_size 10M;

server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    root /var/www/html/zong-ce;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:5003;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        client_max_body_size 10M;
    }
}
```

部署静态文件并启用站点：

```bash
sudo mkdir -p /var/www/html/zong-ce
sudo cp -r /home/ubuntu/zong_ce/frontend/dist/* /var/www/html/zong-ce/
sudo ln -sf /etc/nginx/sites-available/zong-ce /etc/nginx/sites-enabled/zong-ce

# 移除默认站点（如有冲突）
sudo rm -f /etc/nginx/sites-enabled/default

# 测试配置并重载
sudo nginx -t
sudo systemctl reload nginx
```

### 1.9 配置防火墙（可选）

```bash
sudo ufw allow 80/tcp
sudo ufw allow 22/tcp
sudo ufw enable
```

---

## 二、更新部署

### 2.1 拉取最新代码

```bash
cd /home/ubuntu/zong_ce
git pull origin main
```

### 2.2 更新后端

```bash
cd /home/ubuntu/zong_ce/backend
.venv/bin/pip install -r requirements.txt
sudo systemctl restart zong-ce-backend
```

### 2.3 更新前端

```bash
cd /home/ubuntu/zong_ce
npm install
npm run build
sudo cp -r frontend/dist/* /var/www/html/zong-ce/
```

---

## 三、常用运维命令

| 操作 | 命令 |
|------|------|
| 查看后端状态 | `sudo systemctl status zong-ce-backend` |
| 重启后端 | `sudo systemctl restart zong-ce-backend` |
| 查看后端日志 | `sudo journalctl -u zong-ce-backend -f` |
| 查看 Nginx 日志 | `sudo tail -f /var/log/nginx/access.log` |
| 查看 Nginx 错误 | `sudo tail -f /var/log/nginx/error.log` |
| 重载 Nginx | `sudo systemctl reload nginx` |
| 测试 Nginx 配置 | `sudo nginx -t` |

---

## 四、HTTPS 配置（可选）

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
sudo certbot renew --dry-run  # 测试自动续期
```

---

## 五、故障排查

### 后端无法启动

```bash
# 检查 systemd 日志
sudo journalctl -u zong-ce-backend -n 50

# 手动启动测试
cd /home/ubuntu/zong_ce/backend
.venv/bin/python run.py
```

### 数据库连接失败

```bash
# 确认 PostgreSQL 运行
sudo systemctl status postgresql

# 测试连接
psql -h 127.0.0.1 -U postgres -d zong_ce -c "\dt"
```

### 前端页面空白

```bash
# 确认构建产物存在
ls -la /var/www/html/zong-ce/

# 检查 Nginx 配置
sudo nginx -t

# 确认文件权限
sudo chown -R www-data:www-data /var/www/html/zong-ce
```
