# 无限画布

本地 AI 创作画布，支持电商图片、短剧分镜、图片与视频生成，以及素材编排。

- `frontend/`：React 与 Vite 画布界面、节点交互、素材与渠道配置。
- `backend/`：FastAPI 本地服务、模型代理、任务与文件保存。
- `VERSION`、`CHANGELOG.md`：界面展示的版本与发布记录。

## 启动后端

需要 Python 3.12。在仓库根目录执行：

```bash
cd backend
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

在本机填写 `backend/.env` 的模型服务配置。密钥只保存在后端环境中。启动服务：

```bash
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## 启动前端

在另一个终端，从仓库根目录执行：

```bash
cd frontend
npm ci --legacy-peer-deps
npm run dev
```

打开 `http://127.0.0.1:3000`。本地模型渠道地址使用 `http://127.0.0.1:8000`，真实模型密钥填写在 `backend/.env`。视频拼接功能需要本机安装 FFmpeg。

当前锁定版本同时使用 Ant Design 6 和 Pro Components 3 beta。后者的 peer dependency 声明仍为 Ant Design 5，安装时使用上面的参数保留项目现有依赖组合。

## 构建和测试

在 `frontend/` 运行：

```bash
npm run typecheck
npm test
npm run build
```

静态构建产物位于 `frontend/dist/`，可以通过 `npm start` 预览。运行数据、密钥、依赖及构建产物均不提交到仓库。上游无限画布的 MIT 许可保留在 `LICENSE`。
