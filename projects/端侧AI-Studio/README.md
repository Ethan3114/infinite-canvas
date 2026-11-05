# 端侧 AI Studio

本地画布。这一版只做一条电商路径：上传商品图，看生成卡，确认后出一张主图或场景图。

## 启动

打开两个终端，都先进入工具包文件夹。

```bash
cd "/Users/ethan/Documents/测试题（中等难度）/projects/端侧AI-Studio/backend"
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

另一个终端：

```bash
cd "/Users/ethan/Documents/测试题（中等难度）/projects/端侧AI-Studio/frontend"
npm install
npm run dev
```

浏览器打开 http://127.0.0.1:8000 。这是 infinite-canvas 的界面。进入「画布」，点「新建画布」，先选「电商素材」或「批量短剧」。两种画布的文字生成分开：电商写成生图提示词，短剧写成角色和分镜。

出图会发到本机后端，再由后端调用商汤。画布配置里的地址应是 `http://127.0.0.1:8000`，钥匙填 `local` 即可，这不是真钥匙。真钥匙只放在 `backend/.env`。

两张以上商品图连到同一次图片生成时，每张商品各出一张，并附带方图、竖图、横图。改尺寸不调用商汤。改提示词再生成，才会重新出图。文本生成用 `deepseek-flash`。

## 钥匙

真实出图前，把钥匙填进 `backend/.env`，不要贴到对话里。

- `DEEPSEEK_API_KEY`：DeepSeek 的钥匙
- `DEEPSEEK_MODEL`：能看图的模型名
- `SENSETIME_API_KEYS`：三把商汤钥匙，用英文逗号隔开

改完后重新启动后端。没有钥匙时，页面能打开，但生成会停在「还没有配置钥匙」，不会出现假图。

商汤默认地址是 `https://token.sensenova.cn/v1`，模型是 `sensenova-u1.5-fast`（比 Lite 快很多，一张图几秒）。如果控制台不是这个，只改 `.env` 里的地址和模型名。

## 验证

```bash
cd "/Users/ethan/Documents/测试题（中等难度）/projects/端侧AI-Studio/backend"
.venv/bin/python -m pytest -q
```

有钥匙之后，在产品文件夹运行：

```bash
../backend/.venv/bin/python scripts/smoke.py
```

脚本会自己把结果写进 `docs/evidence/阶段2-1/冒烟记录.md`。
