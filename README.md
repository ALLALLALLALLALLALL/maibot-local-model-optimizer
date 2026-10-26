# MaiBot Local Model Optimizer

A small MaiBot plugin that makes local **Ollama** models behave: it keeps them
loaded instead of letting Ollama unload them after a few idle minutes, and it
checks that the models you assigned to the **planner** and **vlm** actually
support the capabilities MaiBot needs.

> 中文说明见 [README.zh-CN.md](README.zh-CN.md)。

## Why

MaiBot talks to Ollama through the OpenAI-compatible endpoint. Two problems are
easy to hit:

1. **Cold starts.** Ollama unloads a model after `OLLAMA_KEEP_ALIVE` (5 minutes
   by default). The next message pays the full load time again — on a 15 GB RAM
   machine a 14B model can take over a minute.
2. **Capability mismatch.** MaiBot's planner must *call tools* (`reply`, `wait`,
   `query_memory`, …). A model without the `tools` capability will just print a
   paragraph of reasoning, produce no `tool_calls`, and the bot will look like
   it "thinks but never replies". The same applies to `vision` for the vlm task.

This plugin keeps the configured models warm with `keep_alive = -1`, and logs a
clear warning at startup when a model is missing `tools` or `vision`.

## Features

- **Keep-alive loop** — every N seconds it reads `GET /api/ps` and sends a
  1-token warm-up request for any configured model that is not loaded.
- **Capability audit** — calls `POST /api/show` for the planner and vision
  models and logs:
  - `✅ model supports tools`
  - `⚠ model is used as planner but lacks tools (actual: completion,vision)`
- **Startup warm-up** — the first check runs immediately on load, so the model
  is loading while you are still typing.
- **Config live-reload** — changing the plugin config resets the audit.

## Install

1. Copy this folder into MaiBot's plugin directory:

   ```text
   MaiBot/plugins/maibot-local-model-optimizer/
   ```

2. Restart MaiBot (or reload plugins from the WebUI).

3. Edit `config.toml` if your models or Ollama address differ.

No extra Python packages are required — the plugin only uses `aiohttp`, which
MaiBot already ships.

## Configuration

| Key | Default | Meaning |
| --- | --- | --- |
| `enabled` | `true` | Turn the plugin on/off |
| `base_url` | `http://127.0.0.1:11434` | Ollama base URL (`/v1` is stripped) |
| `models` | `qwen2.5:14b,qwen3.5:9b,nomic-embed-text` | Models to keep loaded, comma separated |
| `planner_model` | `qwen2.5:14b` | Checked for the `tools` capability |
| `vision_model` | `qwen3.5:9b` | Checked for the `vision` capability |
| `keep_alive` | `-1` | `keep_alive` sent with warm-up requests, `-1` = forever |
| `check_interval_seconds` | `120` | How often to check `/api/ps` |
| `warmup_prompt` | `hi` | Prompt used by the warm-up request |

## Example log

```text
[本地模型优化] 已加载，Ollama=http://127.0.0.1:11434，保活模型=qwen2.5:14b,qwen3.5:9b,nomic-embed-text
[本地模型优化] ✅ qwen2.5:14b 支持 tools
[本地模型优化] ✅ qwen3.5:9b 支持 vision
[本地模型优化] 预热模型 / warming up: qwen2.5:14b
[本地模型优化] qwen2.5:14b 加载耗时 / load 16.2s
```

A mismatch looks like this:

```text
[本地模型优化] ⚠ qwen3.5:9b 用作 planner(工具调用/tool calls)，但缺少 tools 能力（实际: completion,vision）。请换用支持该能力的模型。
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
