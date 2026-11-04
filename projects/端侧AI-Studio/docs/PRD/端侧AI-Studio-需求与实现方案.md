# 端侧 AI Studio：需求与实现方案

| 项 | 说明 |
| --- | --- |
| 产品名 | 端侧 AI Studio |
| 文档类型 | 需求还原 + 场景拆解 + 对应实现方案 |
| 目标读者 | 产品／工程／作业评审 |
| 实现定位 | **云端推理**的视觉创作工作台（画布 + 双场景包）；多 Provider 可切换 |
| 题目说明 | 题目背景来自端侧主机命题，本方案按云端 API 落地 |

---

## 1. 题目与需求还原

### 1.1 产品一句话

端侧 AI Studio 是面向视觉创作的**云端推理工作台**：用户在无限画布上生成、编辑、组合图片（及短视频素材），完成电商视觉与短视频自动化两类创作任务；生图／生视频经统一模型路由调用云端 API。

### 1.2 产品形态

| 层 | 含义 |
| --- | --- |
| 应用 | 画布式创作应用：资产、任务、场景工作流 |
| 推理 | 云端 API（可切换多家 Provider） |
| 协同 | 账号、授权、任务配额与排队 |

### 1.3 必须同时覆盖的双场景（非二选一）

- **场景 A · 电商视觉**：商品图、主图、场景图；批量改尺寸／风格；多 SKU 视觉一致性。
- **场景 B · 短视频自动化**：分镜脚本 → 文生图／视频 → 角色一致性 → 批量出片。

### 1.4 需求清单（从题目还原）

1. 画布工作台：节点式／无限画布上完成生成、编辑、组合。
2. 电商工作流：主图／场景图生成、批量尺寸与风格、多 SKU 一致性。
3. 短视频工作流：分镜脚本、镜头级生成、角色一致性、批量导出。
4. 统一资产与任务：跨场景复用素材、提示词、角色卡、任务队列。
5. 模型可路由：同一任务描述可指向不同云端 Provider（OpenAI 兼容、OpenRouter、远程 Comfy 云、各图／视频 API 等）。
6. 开源可组合：画布壳 + 电商／短视频参考项目 + 一致性能力参考 +（可选）远程／云托管 Comfy 工作流后端。

---

## 2. 用户是谁

### 2.1 画像

| 角色 | 典型背景 | 核心目标 |
| --- | --- | --- |
| 图文创作者／电商设计师 | 店铺运营、视觉设计、兼职美工 | 快速产出多规格商品主图与场景图，多 SKU 视觉统一 |
| 短视频创作者／剪辑向创作者 | 带货短视频、剧情口播、动画向内容 | 从脚本到分镜素材再到批量成片，降低重复手工 |
| 小团队主理人 | 1～3 人电商或内容工作室 | 用一套工作台跑通「出图 + 出片」，沉淀可复用场景包 |

### 2.2 典型任务

- 上传白底商品图 → 生成生活场景图 → 导出多平台尺寸包。
- 同一品牌多 SKU：固定构图／光影／人物气质，只换商品。
- 写好分镜表 → 按镜头批量出图／出视频片段 → 保持主角一致 → 导出剪辑素材包。
- 在画布上把「参考图、提示词、生成结果、改图节点」串成可复用流水线。

### 2.3 痛点

| 痛点 | 说明 |
| --- | --- |
| 工具碎片化 | 出图、改尺寸、一致性、分镜、出片分散在多个软件与网页 |
| 一致性难控 | 多 SKU、多镜头角色／商品漂移，返工成本高 |
| 批量成本高 | 规格多、镜头多，手工逐张不可规模化 |
| Provider 绑死 | 业务逻辑写死某一家 API 字段，换模型／换供应商成本高 |
| 工作流难沉淀 | 成功参数与节点图无法变成团队可复用「场景包」 |

---

## 3. 场景 A／场景 B

### 3.1 场景 A：电商视觉创作

#### 问题

- 主图、详情场景图、平台尺寸规格多，重复劳动大。
- 多 SKU 要求「像同一套视觉系统」，商品细节与品牌调性不能漂。
- 需要可批量、可参数化的改风格／改尺寸，而不是单张聊天式出图。

#### MVP 模块

| 模块 | 能力 |
| --- | --- |
| 商品资产入库 | 白底图／细节图上传、SKU 元数据、参考风格板 |
| 主图／场景图生成 | 文生图 + 图生图；场景模板（棚拍、生活、节日等） |
| 批量规格导出 | 平台尺寸预设（如方图、竖图、横图）；一键多尺寸 |
| 风格与一致性 | 参考图／人脸／IP 类约束（能力参考 PuLID、IP-Adapter）；SKU 间共享构图与人物／背景设定 |
| 画布编排 | 参考 → 生成 → 精修 → 导出节点可保存为电商场景包 |

#### 主流程（MVP）

1. 导入商品图与品牌参考，创建／选择 SKU。
2. 在画布选择「主图」或「场景图」模板，填写卖点与风格约束。
3. 提交任务（经模型路由调用云端 Provider）。
4. 预览、局部改图、锁定一致性参考。
5. 批量套用尺寸与轻度风格变体，导出资产包并回写资产库。

#### 可参考开源（电商向）

- https://github.com/clawnify/OpenStudio  
- https://github.com/shrimbly/comfy-commerce  
- https://github.com/xiaoqahax-ui/comfyui-ecommerce-workflows  

### 3.2 场景 B：短视频自动化

#### 问题

- 从文案／脚本到分镜、出图、出视频、导出剪辑素材链路长。
- 多镜头角色一致性差，系列内容难以「同一主角」。
- 需要批量出片与可重复执行的镜头流水线，而不是单次灵感生成。

#### MVP 模块

| 模块 | 能力 |
| --- | --- |
| 分镜脚本 | 文本／表格分镜：镜头号、景别、对白、画面描述、时长 |
| 镜头生成 | 文生图、图生视频／镜头片段；镜头级参数与种子管理 |
| 角色一致性 | 角色卡（参考脸／服装／风格约束）；全片绑定 |
| 批量出片 | 按分镜表队列生成；失败重试；成片／素材打包 |
| 画布编排 | 脚本节点 → 分镜板 → 生成节点 → 时间线式导出 |

#### 主流程（MVP）

1. 导入或撰写分镜脚本，解析为镜头列表。
2. 绑定角色卡与风格板（全局一致性约束）。
3. 按镜头批量提交生成任务（图或短视频片段，走云端 API）。
4. 抽检一致性，对漂移镜头锁定参考重跑。
5. 导出分镜板、素材序列与简易成片包，供外部剪辑或后续合成。

#### 可参考开源（短视频向）

- https://github.com/HBAI-Ltd/Toonflow-app  
- https://github.com/ArcReel/ArcReel  
- https://github.com/Forget-C/Jellyfish  
- https://github.com/NickPittas/DirectorsConsole  

### 3.3 两场景共性需求

- 无限画布作为统一交互壳。
- 资产库（图、视频片段、角色卡、提示词、工作流模板）。
- 任务队列与进度（批量是刚需）。
- 一致性能力可插拔（参数结构统一；实现侧对接各 Provider 的参考图／人脸／IP 能力）。
- 云端模型路由（见第 5 节）。

---

## 4. 双场景统一产品骨架

双场景共用一套「创作操作系统」，差异收进**场景包（Scene Pack）**，避免做成两个互不相干的 App。

```
┌─────────────────────────────────────────────────────────┐
│                    端侧 AI Studio 应用层                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐  │
│  │ 无限画布  │ │ 资产中心  │ │ 任务中心  │ │ 模型路由   │  │
│  │ Canvas   │ │ Assets   │ │ Jobs     │ │ Providers  │  │
│  └──────────┘ └──────────┘ └──────────┘ └────────────┘  │
│         ▲ 场景包 A（电商）     ▲ 场景包 B（短视频）        │
│         │ 模板／工作流／导出    │ 分镜／角色／出片          │
└─────────────────────────────────────────────────────────┘
                              │
                              ▼
                 云端 API 层（可切换多家 Provider）
         OpenAI 兼容 · OpenRouter · 远程 Comfy 云 · 图／视频 API
                              │
                              ▼
                 账号 · 授权 · 任务配额与排队（协同层）
```

### 4.1 共享能力

| 共享层 | 职责 |
| --- | --- |
| 画布壳 | 节点、连线、视口、多选、模板保存／加载 |
| 资产中心 | 上传、版本、标签、SKU／角色绑定、引用计数 |
| 任务中心 | 创建、排队、进度、取消、失败重试、批量分组 |
| 模型路由 | 统一 `GenerateImage`／`GenerateVideo`／`Refine` 接口；按配置选云端 Provider |
| 一致性插件位 | 参考图、人脸／IP、Control 类约束的统一参数结构 |
| 协同层 | 账号、授权、任务配额与队列策略接口 |

### 4.2 场景包（差异层）

| 场景包 | 内含 |
| --- | --- |
| 电商包 | 主图／场景模板、平台尺寸预设、SKU 工作流、电商向导出规范 |
| 短视频包 | 分镜表 schema、镜头工作流、角色卡、批量出片与素材包导出 |

场景包只依赖共享层 API，不直接绑死某一云厂商；换 Provider 时场景包无需重写业务语义。

---

## 5. 云端实现方案

### 5.1 开源组合怎么拼

| 位置 | 选用 | URL | 用法建议 |
| --- | --- | --- | --- |
| 画布壳 | infinite-canvas | https://github.com/basketikun/infinite-canvas | 作为前端交互与节点画布基础，承载场景包 UI |
| 电商参考 | OpenStudio | https://github.com/clawnify/OpenStudio | 吸收商品／工作室向信息架构与流程 |
| 电商参考 | comfy-commerce | https://github.com/shrimbly/comfy-commerce | 吸收电商向工作流与批量思路 |
| 电商参考 | comfyui-ecommerce-workflows | https://github.com/xiaoqahax-ui/comfyui-ecommerce-workflows | 沉淀可导入的电商节点图／工作流资产（可对接到远程 Comfy API） |
| 短视频参考 | Toonflow-app | https://github.com/HBAI-Ltd/Toonflow-app | 分镜／叙事向流程参考 |
| 短视频参考 | ArcReel | https://github.com/ArcReel/ArcReel | 卷轴／镜头序列向交互与管线参考 |
| 短视频参考 | Jellyfish | https://github.com/Forget-C/Jellyfish | 自动化出片向能力参考 |
| 短视频参考 | DirectorsConsole | https://github.com/NickPittas/DirectorsConsole | 导演台／镜头控制台信息架构参考 |
| 一致性参考 | PuLID_ComfyUI | https://github.com/cubiq/PuLID_ComfyUI | 人脸／身份锁定能力参考；参数映射到云端一致性接口或远程 Comfy |
| 一致性参考 | IP-Adapter | https://github.com/tencent-ailab/IP-Adapter | 风格／主体参考能力参考；电商场景与角色气质约束 |
| 可选后端 | ComfyUI | https://github.com/Comfy-Org/ComfyUI | **可远程／云托管的工作流 API 后端**选项；非本机必装模型 |

**拼装顺序建议**

1. 落画布壳 + 资产／任务最小 API。  
2. 接模型路由：先实现 1～2 个云端 Provider（如 OpenAI 兼容文生图 + 一家视频 API）。  
3. 导入电商场景包（模板 + 1～2 条可跑通工作流）。  
4. 导入短视频场景包（分镜表 → 批量任务）。  
5. 挂载一致性参数到插件位，并按所选 Provider 做字段适配。  
6. 按需增加 OpenRouter、远程 Comfy 云等 Provider，配置即可切换。

### 5.2 API 怎么换（模型路由）

统一对应用暴露稳定接口，例如：

- `createJob(type, payload, consistency, scenePackId)`
- `listJobs` / `getJob` / `cancelJob`
- `provider.generateImage(input)` / `provider.generateVideo(input)` / `provider.refine(input)`

**云端 Provider 适配（可扩展）**

| Provider | 说明 |
| --- | --- |
| `OpenAICompatibleProvider` | 对接 OpenAI 兼容的文生图／多模态 HTTP API |
| `OpenRouterProvider` | 经 OpenRouter 路由多家模型，便于对比与切换 |
| `RemoteComfyProvider` | 对接远程／云托管 Comfy 工作流 API（电商／一致性工作流可复用 JSON） |
| `ImageVideoVendorProvider` | 对接各家专用图／视频 API（按厂商适配层封装） |
| （可选）`DryRunProvider` | 开发用：不真正推理，返回占位图，便于画布与任务联调 |

切换方式：配置项（如 `MODEL_PROVIDER=openai_compatible|openrouter|remote_comfy|vendor_x`）或设置页选择；**场景包与画布不感知具体厂商**。密钥与端点走环境变量／密钥管理，不写入场景包。

### 5.3 实现要点

| 要点 | 做法 |
| --- | --- |
| 业务与厂商解耦 | 场景包只写统一 payload；各 Provider 负责字段翻译与轮询／回调 |
| 工作流可迁移 | 电商／短视频能力优先沉淀为中间表示或可导入工作流资产；需要时再编译为某家 API 或远程 Comfy JSON |
| 一致性可插拔 | 统一「参考图／人脸／IP／Control」参数结构；有能力的 Provider 启用，无能力则降级提示 |
| 批量与配额 | 任务中心负责排队、重试、分组；协同层管配额与鉴权，与具体推理厂商解耦 |
| 素材与结果 | 上传／回写走资产中心；可配置结果缓存与过期策略 |

### 5.4 实现边界（本文不展开的部分）

- 具体模型榜单、价格／时延对比 → 见后续《模型选型评测》文档。  
- 多任务排队、限流与失败重试全文 → 见后续《多任务并发策略》文档。  
- 双场景 demo 的里程碑与验收清单 → 见后续 demo 交付说明。

---

## 6. 后续交付（暂不展开）

以下三项**后续再做**，本文仅点到为止：

1. **双场景 demo**：基于统一骨架分别跑通电商主路径与短视频主路径的可演示版本（交互与任务闭环优先，不在此列验收细项）。  
2. **模型选型评测文档**：云端生图／生视频／一致性方案对比与推荐组合（指标、样例与结论另文）。  
3. **多任务并发策略文档**：批量出图／出片时的队列、限流与失败重试策略（与协同层配额接口对齐，另文）。

---

## 附录：开源链接汇总

| 类别 | 项目 | URL |
| --- | --- | --- |
| 画布壳 | infinite-canvas | https://github.com/basketikun/infinite-canvas |
| 电商 | OpenStudio | https://github.com/clawnify/OpenStudio |
| 电商 | comfy-commerce | https://github.com/shrimbly/comfy-commerce |
| 电商 | comfyui-ecommerce-workflows | https://github.com/xiaoqahax-ui/comfyui-ecommerce-workflows |
| 短视频 | Toonflow-app | https://github.com/HBAI-Ltd/Toonflow-app |
| 短视频 | ArcReel | https://github.com/ArcReel/ArcReel |
| 短视频 | Jellyfish | https://github.com/Forget-C/Jellyfish |
| 短视频 | DirectorsConsole | https://github.com/NickPittas/DirectorsConsole |
| 一致性 | PuLID_ComfyUI | https://github.com/cubiq/PuLID_ComfyUI |
| 一致性 | IP-Adapter | https://github.com/tencent-ailab/IP-Adapter |
| 可选后端 | ComfyUI | https://github.com/Comfy-Org/ComfyUI |

---

*本文覆盖：需求还原、用户、双场景、统一骨架与云端实现方案；demo、评测全文、并发策略全文明确留待后续交付。*
