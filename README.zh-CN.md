# MaiBot 本地模型优化插件

一个让本地 **Ollama** 模型"听话"的 MaiBot 插件：它会让模型常驻、不被
Ollama 在闲置几分钟后卸载，并在启动时检查你分配给 **planner** 和 **vlm**
的模型是否真的具备 MaiBot 需要的能力。

> English documentation: [README.md](README.md)

## 不写死任何模型名

每个人的本地模型都不一样，所以插件的默认配置是**空的**：

- `models` 留空 → 只保活当前已经加载的模型。
- `planner_model` / `vision_model` 留空 → 跳过对应检查，并打印本机所有模型
  及其能力，方便你按自己的模型名填写。

插件不会假设你用的是 `qwen`、`llama`、`deepseek` 或任何特定 tag。

## 为什么需要它

MaiBot 通过 OpenAI 兼容接口调用 Ollama，很容易遇到两个问题：

1. **冷启动。** Ollama 默认在 `OLLAMA_KEEP_ALIVE`（5 分钟）后卸载模型，下一
   条消息又要重新加载。
2. **能力不匹配。** MaiBot 的 planner 必须**调用工具**（`reply`、`wait`、
   `query_memory` 等）。如果模型没有 `tools` 能力，它只会输出一段纯文本推理，
   不产生 `tool_calls`，表现出来就是"它想了，但永远不回你"。vlm 任务同理，
   需要 `vision` 能力。

本插件用 `keep_alive = -1` 让配置的模型保持加载，并在模型缺少 `tools` 或
`vision` 时给出明确告警。

## 功能

- **保活循环**：每隔 N 秒读取 `GET /api/ps`，对未加载的模型发送 1-token
  预热请求。
- **能力检查**：对 planner / vision 模型调用 `POST /api/show`，日志会输出：
  - `✅ 模型支持 tools`
  - `⚠ 模型被用作 planner，但缺少 tools 能力（实际: completion,vision）`
- **能力表**：没有配置 planner/vision 模型时，列出本机所有模型及其能力。
- **启动预热**：插件加载后立即执行第一次检查。
- **配置热更新**：修改插件配置后会重新做一次能力检查。

## 安装

1. 把整个文件夹复制到 MaiBot 的插件目录：

   ```text
   MaiBot/plugins/maibot-local-model-optimizer/
   ```

2. 重启 MaiBot（或在 WebUI 里重载插件）。

3. 修改 `config.toml`，填**你自己的**模型名。

不需要额外安装 Python 包——插件只用到 MaiBot 自带的 `aiohttp`。

## 配置项

| 配置 | 默认值 | 说明 |
| --- | --- | --- |
| `enabled` | `true` | 是否启用 |
| `base_url` | `http://127.0.0.1:11434` | Ollama 地址（会自动去掉 `/v1`） |
| `models` | `""` | 需要保活的模型，英文逗号分隔；留空 = 只保活当前已加载的模型 |
| `planner_model` | `""` | 你的 planner 模型，检查 `tools`；留空跳过 |
| `vision_model` | `""` | 你的 vlm 模型，检查 `vision`；留空跳过 |
| `keep_alive` | `-1` | 预热请求携带的 `keep_alive`，`-1` 表示永久 |
| `check_interval_seconds` | `120` | 检查 `/api/ps` 的间隔秒数 |
| `warmup_prompt` | `hi` | 预热请求内容 |

示例（把名字换成你日志里打印出来的）：

```toml
[plugin]
enabled = true
base_url = "http://127.0.0.1:11434"
models = "你的聊天模型:latest,你的嵌入模型:latest"
planner_model = "你的聊天模型:latest"
vision_model = "你的视觉模型:latest"
keep_alive = -1
check_interval_seconds = 120
warmup_prompt = "hi"
```

## 日志示例

```text
[本地模型优化] 已加载，Ollama=http://127.0.0.1:11434，保活模型=...
[本地模型优化] 未配置 planner_model / vision_model，以下是本机模型及能力，请按自己的模型名填写：
  - your-chat-model:latest: completion,tools
  - your-vl-model:latest: completion,vision
[本地模型优化] 预热模型 / warming up: your-chat-model:latest
[本地模型优化] your-chat-model:latest 加载耗时 / load 16.2s
```

能力不匹配时：

```text
[本地模型优化] ⚠ your-model:latest 用作 planner(工具调用/tool calls)，但缺少 tools 能力（实际: completion,vision）。请换用支持该能力的模型。
```

## 说明

- 插件是按请求发送 `keep_alive`，**不会**修改 Ollama 的全局环境变量；如需
  双保险，可以在启动 Ollama 前设置 `OLLAMA_KEEP_ALIVE=-1`。
- 同时常驻多个大模型会占用显存，请按需调整 `OLLAMA_MAX_LOADED_MODELS`。
- embedding 模型重新加载很快，但保活可以省掉记忆检索第一次请求的延迟。

## 许可证

MIT
