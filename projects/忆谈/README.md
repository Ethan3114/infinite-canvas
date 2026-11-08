# 忆谈

给一位老人建档，并在浏览器里打通一通短的连续通话。这一段先留在你自己的电脑上。

## 启动

1. 打开终端，进入 `projects/忆谈/backend`。
2. 第一次先执行：`python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt`。
3. 如果还没有 `.env`，复制 `.env.example` 为 `.env`。邀请码默认是 `yitan-local`。豆包语音钥匙填在 `DOUBAO_API_KEY`，不要发到对话里。
4. 启动后端：`.venv/bin/python -m uvicorn app.main:app_factory --factory --host 127.0.0.1 --port 8011`。
5. 另开一个终端，进入 `projects/忆谈/frontend`，执行 `npm install` 然后 `npm run dev`。
6. 浏览器打开 http://127.0.0.1:3011 。

## 验证

后端测试：

```bash
cd projects/忆谈/backend && .venv/bin/python -m pytest -q
```

当前阶段在工具包根目录执行 `bash verify.sh 忆谈 阶段2-3`。

第二次通话会在开场提起上一章。不勾选老人同意，就不会开始，也不会留下录音。文字里的银行卡号不会写进章节和记忆。

写章节需要在 `backend/.env` 填写 `DEEPSEEK_API_KEY`。没有这把钥匙时，页面会说明还不能整理，不会编一章出来。有钥匙时执行 `cd projects/忆谈/backend && .venv/bin/python ../scripts/smoke_chapter.py`。
