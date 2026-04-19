# Ubuntu Docker 部署操作稿

## 目的
- 产出一份可直接照着执行的 Markdown 操作稿。
- 适用于 Ubuntu 服务器，使用 Docker 快速部署当前项目。
- 先以“快速启动”版本为主，直接暴露 `8000` 端口，不包含反向代理。

## 已核实的项目基础
- 项目自带 Compose 文件，默认将宿主机 `8000` 映射到容器 `8000`：

```7:8:docker-compose.yml
    ports:
      - "8000:8000"
```

- Docker 镜像基于 Python 3.11：

```1:3:Dockerfile
FROM python:3.11-slim

WORKDIR /app
```

- 容器启动命令是运行 `wfxl_openai_regst.py`：

```17:20:Dockerfile
EXPOSE 8000
ENV PYTHONUNBUFFERED=1

CMD ["python", "wfxl_openai_regst.py"]
```

- 应用运行时监听 `0.0.0.0:8000`，适合容器内直接对外提供服务：

```196:200:wfxl_openai_regst.py
    sys.__stdout__.write(f"[{core_engine.ts()}] [系统] 控制台地址：http://127.0.0.1:8000 \n")
    sys.__stdout__.write(f"[{core_engine.ts()}] [系统] 控制台初始密码：admin \n")
    sys.__stdout__.write(f"[{core_engine.ts()}] [系统] 结束请猛猛重复按CTRL+C \n")
    sys.__stdout__.flush()
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning", access_log=False, timeout_graceful_shutdown=1)
```

## 部署前提
- 服务器系统为 Ubuntu。
- 服务器可以联网拉取 Docker 与镜像。
- 你将把项目放到 `/opt/wenfxl-codex`。
- 当前以“快速部署”为目标，暂不加 Nginx/Caddy 反向代理。

## 方案 A：服务器直接 `git clone`
适合服务器可以直接访问你的 Git 仓库。

### 1. 安装基础环境

```bash
sudo apt update
sudo apt install -y git curl ca-certificates
```

### 2. 安装 Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo systemctl enable docker
sudo systemctl start docker
```

### 3. 验证 Docker

```bash
docker --version
sudo docker compose version
```

### 4. 拉取项目到固定目录
把下面的仓库地址替换成你自己的：

```bash
sudo mkdir -p /opt
cd /opt
sudo git clone <你的仓库地址> wenfxl-codex
cd /opt/wenfxl-codex
```

### 5. 准备数据目录

```bash
sudo mkdir -p /opt/wenfxl-codex/data
```

### 6. 启动项目

```bash
cd /opt/wenfxl-codex
sudo docker compose up -d
```

## 方案 B：你把项目手动上传到服务器
适合你本地打包后上传到 Ubuntu。

### 1. 安装基础环境

```bash
sudo apt update
sudo apt install -y curl ca-certificates unzip
```

### 2. 安装 Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo systemctl enable docker
sudo systemctl start docker
```

### 3. 创建项目目录

```bash
sudo mkdir -p /opt/wenfxl-codex
cd /opt/wenfxl-codex
```

### 4. 上传项目文件
把你的整个项目上传到 `/opt/wenfxl-codex`。
上传完成后，确保这里至少能看到：
- `docker-compose.yml`
- `Dockerfile`
- `wfxl_openai_regst.py`
- `requirements.txt`

### 5. 准备数据目录

```bash
sudo mkdir -p /opt/wenfxl-codex/data
```

### 6. 启动项目

```bash
cd /opt/wenfxl-codex
sudo docker compose up -d
```

## 启动后验证

### 查看容器状态

```bash
cd /opt/wenfxl-codex
sudo docker compose ps
```

### 查看启动日志

```bash
cd /opt/wenfxl-codex
sudo docker compose logs -f
```

### 访问地址
浏览器打开：

```text
http://服务器IP:8000
```

默认密码：

```text
admin
```

## 防火墙与云安全组
如果服务器启用了 `ufw`，执行：

```bash
sudo ufw allow 8000/tcp
sudo ufw reload
```

如果你使用的是云服务器，还需要到云厂商控制台放行：
- 入站 TCP `8000`

## 常用运维命令

### 启动

```bash
cd /opt/wenfxl-codex
sudo docker compose up -d
```

### 停止

```bash
cd /opt/wenfxl-codex
sudo docker compose down
```

### 重启

```bash
cd /opt/wenfxl-codex
sudo docker compose restart
```

### 查看日志

```bash
cd /opt/wenfxl-codex
sudo docker compose logs -f
```

### 拉取新镜像并更新

```bash
cd /opt/wenfxl-codex
sudo docker compose pull
sudo docker compose up -d
```

## 数据与备份
当前 Compose 把宿主机目录 `./data` 挂载到容器内 `/app/data`：

```14:16:docker-compose.yml
    volumes:
      - ./data:/app/data
      - /var/run/docker.sock:/var/run/docker.sock
```

因此建议重点备份：

```text
/opt/wenfxl-codex/data
```

## 风险提醒
- 默认密码 `admin` 不要长期使用，登录后尽快修改。
- 当前方案是直接暴露 `8000`，适合测试或临时部署。
- 如果后续要公网长期运行，建议改成反向代理 + HTTPS。
- 现有 Compose 还包含 `watchtower` 自动更新容器；如果你不想自动更新镜像，部署前可以先审视这部分配置：

```17:23:docker-compose.yml
  watchtower:
    image: containrrr/watchtower
    container_name: watchtower
    restart: always
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    command: --interval 86400 --cleanup
```

## 你连上服务器后怎么和我继续配合
你连上服务器后，直接把下面三类信息发给我任意一种即可：
1. 你准备用 `git clone` 还是 `手动上传`
2. 你执行某一步后的终端输出
3. 你当前卡住的报错信息

我会严格按照这份操作稿，继续一步一步带你执行。
