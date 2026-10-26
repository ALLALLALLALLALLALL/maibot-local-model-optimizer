# MaiBot Local Model Optimizer

A small MaiBot plugin that makes local **Ollama** models behave: it keeps them
loaded instead of letting Ollama unload them after a few idle minutes, and it
checks that the models you assigned to the **planner** and **vlm** actually
support the capabilities MaiBot needs.

> 中文说明见 [README.zh-CN.md](README.zh-CN.md)。

## No hardcoded model names

Every local setup uses different models, so this plugin ships with **empty**
defaults:

- `models` empty → only models that are already loaded are kept warm.
- `planner_model` / `vision_model` empty → the matching check is skipped and the
  plugin prints a table of your installed models and their capabilities, so you
  can copy the right names into the config.

Nothing assumes `qwen`, `llama`, `deepseek` or any specific tag.

## Why

MaiBot talks to Ollama through the OpenAI-compatible endpoint. Two problems are
easy to hit:

1. **Cold starts.** Ollama unloads a model after `OLLAMA_KEEP_ALIVE` (5 minutes
   by default). The next message pays the full load time again.
2. **Capability mismatch.** MaiBot's planner must *call tools* (`reply`, `wait`,
   `query_memory`, …). A model without the `tools` capability will just print a
   paragraph of reasoning, produce no `tool_calls`, and the bot will look like
   it "thinks but never replies". The same applies to `vision` for the vlm task.

This plugin keeps the configured models warm with `keep_alive = -1`, and logs a
clear warning when a model is missing `tools` or `vision`.

## Features

- **Keep-alive loop** — every N seconds it reads `GET /api/ps` and sends a
  1-token warm-up request for any model that is not loaded.
- **Capability audit** — calls `POST /api/show` for the planner and vision
  models and logs:
  - `✅ model supports tools`
  - `⚠ model is used as planner but lacks tools (actual: completion,vision)`
- **Capability table** — when no planner/vision model is configured, it lists
  every installed model and its capabilities.
- **Startup warm-up** — the first check runs immediately on load.
- **Config live-reload** — changing the plugin config resets the audit.

## Install

1. Copy this folder into MaiBot's plugin directory:

   ```text
   MaiBot/plugins/maibot-local-model-optimizer/
   ```

2. Restart MaiBot (or reload plugins from the WebUI).

3. Edit `config.toml` and fill in **your own** model names.

No extra Python packages are required — the plugin only uses `aiohttp`, which
MaiBot already ships.

## Configuration

| Key | Default | Meaning |
| --- | --- | --- |
| `enabled` | `true` | Turn the plugin on/off |
| `base_url` | `http://127.0.0.1:11434` | Ollama base URL (`/v1` is stripped) |
| `models` | `""` | Models to keep loaded, comma separated. Empty = keep currently loaded models warm |
| `planner_model` | `""` | Your planner model; checked for `tools`. Empty = skip check |
| `vision_model` | `""` | Your vision model; checked for `vision`. Empty = skip check |
| `keep_alive` | `-1` | `keep_alive` sent with warm-up requests, `-1` = forever |
| `check_interval_seconds` | `120` | How often to check `/api/ps` |
| `warmup_prompt` | `hi` | Prompt used by the warm-up request |

Example (replace with the names printed in your log):

```toml
[plugin]
enabled = true
base_url = "http://127.0.0.1:11434"
models = "your-chat-model:latest,your-embed-model:latest"
planner_model = "your-chat-model:latest"
vision_model = "your-vl-model:latest"
keep_alive = -1
check_interval_seconds = 120
warmup_prompt = "hi"
```

## Example log

```text
[本地模型优化] 已加载，Ollama=http://127.0.0.1:11434，保活模型=...
[本地模型优化] 未配置 planner_model / vision_model，以下是本机模型及能力，请按自己的模型名填写：
  - your-chat-model:latest: completion,tools
  - your-vl-model:latest: completion,vision
[本地模型优化] 预热模型 / warming up: your-chat-model:latest
[本地模型优化] your-chat-model:latest 加载耗时 / load 16.2s
```

A mismatch looks like this:

```text
[本地模型优化] ⚠ your-model:latest 用作 planner(工具调用/tool calls)，但缺少 tools 能力（实际: completion,vision）。请换用支持该能力的模型。
```

## Notes

- The plugin sends `keep_alive` per request; it does **not** modify Ollama's
  global environment. For extra safety you can still set
  `OLLAMA_KEEP_ALIVE=-1` before starting Ollama.
- Keeping several large models loaded costs VRAM. Set
  `OLLAMA_MAX_LOADED_MODELS` accordingly.
- Embedding models are cheap to reload, but keeping them warm removes the
  first-request latency from memory retrieval.

## License

MIT
