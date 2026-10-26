"""本地模型优化 / Local Model Optimizer for MaiBot.

Keeps the Ollama models used by MaiBot warm (``keep_alive``), and validates
that the configured planner / vision models actually advertise the
capabilities MaiBot needs (``tools`` / ``vision``).

The plugin is deliberately dependency-free apart from ``aiohttp`` which ships
with MaiBot's runtime.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any, Dict, List

import aiohttp

from maibot_sdk import Field, MaiBotPlugin, PluginConfigBase


class PluginSection(PluginConfigBase):
    """基础设置 / Basic settings."""

    __ui_label__ = "基础设置"
    __ui_icon__ = "cpu"
    __ui_order__ = 0

    enabled: bool = Field(
        default=True,
        description="启用本地模型保活与能力检查 / Enable keep-alive and capability checks",
    )
    base_url: str = Field(
        default="http://127.0.0.1:11434",
        description="Ollama 服务地址，可带 /v1 / Ollama base URL, /v1 is stripped",
    )
    models: str = Field(
        default="qwen2.5:14b,qwen3.5:9b,nomic-embed-text",
        description="需要保持加载的模型，英文逗号分隔 / Models to keep warm, comma separated",
    )
    planner_model: str = Field(
        default="qwen2.5:14b",
        description="MaiBot planner 使用的模型；缺少 tools 能力时会告警 / Planner model; warns when it lacks tools",
    )
    vision_model: str = Field(
        default="qwen3.5:9b",
        description="MaiBot vlm 使用的模型；缺少 vision 能力时会告警 / Vision model; warns when it lacks vision",
    )
    keep_alive: int = Field(
        default=-1,
        description="keep_alive 秒数，-1 表示永久 / keep_alive seconds, -1 means forever",
    )
    check_interval_seconds: int = Field(
        default=120,
        description="检查间隔秒数 / Check interval in seconds",
    )
    warmup_prompt: str = Field(
        default="hi",
        description="预热请求内容 / Prompt used for warm-up",
    )


class LocalModelOptimizerConfig(PluginConfigBase):
    """本地模型优化插件配置 / Plugin config."""

    plugin: PluginSection = Field(default_factory=PluginSection)


class LocalModelOptimizerPlugin(MaiBotPlugin):
    """Keep local Ollama models warm and validate capabilities."""

    config_model = LocalModelOptimizerConfig

    def __init__(self) -> None:
        super().__init__()
        self._task: asyncio.Task | None = None
        self._capabilities_checked = False

    # ------------------------------------------------------------------ lifecycle
    async def on_load(self) -> None:
        cfg = self.config.plugin
        if not cfg.enabled:
            self.ctx.logger.info("[本地模型优化] 插件已禁用 / plugin disabled")
            return
        self.ctx.logger.info(
            "[本地模型优化] 已加载，Ollama=%s，保活模型=%s",
            cfg.base_url,
            cfg.models,
        )
        self._task = asyncio.create_task(self._loop(), name="local-model-optimizer")

    async def on_unload(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        self.ctx.logger.info("[本地模型优化] 已卸载 / unloaded")

    async def on_config_update(self, scope: str, config_data: Dict[str, Any], version: str) -> None:
        self.ctx.logger.info("[本地模型优化] 配置已更新 / config updated: %s", scope)
        self._capabilities_checked = False

    # ------------------------------------------------------------------ main loop
    async def _loop(self) -> None:
        while True:
            try:
                await self._check_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                self.ctx.logger.warning("[本地模型优化] 检查失败 / check failed: %s", exc)
            await asyncio.sleep(max(15, int(self.config.plugin.check_interval_seconds)))

    async def _check_once(self) -> None:
        cfg = self.config.plugin
        base = cfg.base_url.rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]

        async with aiohttp.ClientSession() as session:
            loaded = await self._loaded_models(session, base)
            wanted = [m.strip() for m in cfg.models.split(",") if m.strip()]

            if not self._capabilities_checked:
                await self._check_capabilities(session, base)
                self._capabilities_checked = True

            for model in wanted:
                if self._is_loaded(model, loaded):
                    continue
                self.ctx.logger.info("[本地模型优化] 预热模型 / warming up: %s", model)
                ok = await self._warm(session, base, model)
                if ok:
                    self.ctx.logger.info("[本地模型优化] 预热完成 / warm: %s", model)
                else:
                    self.ctx.logger.warning("[本地模型优化] 预热失败 / warm failed: %s", model)

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _is_loaded(model: str, loaded: List[str]) -> bool:
        for item in loaded:
            if item == model:
                return True
            # Ollama may report "qwen2.5:14b-<digest>" style names.
            if item.startswith(model + "-") or model.startswith(item + ":"):
                return True
        return False

    async def _loaded_models(self, session: aiohttp.ClientSession, base: str) -> List[str]:
        async with session.get(f"{base}/api/ps", timeout=aiohttp.ClientTimeout(total=10)) as resp:
            resp.raise_for_status()
            data = await resp.json()
        names: List[str] = []
        for item in data.get("models", []):
            name = item.get("name") or item.get("model") or ""
            if name:
                names.append(str(name))
        return names

    async def _warm(self, session: aiohttp.ClientSession, base: str, model: str) -> bool:
        payload = {
            "model": model,
            "prompt": self.config.plugin.warmup_prompt,
            "stream": False,
            "keep_alive": int(self.config.plugin.keep_alive),
            "options": {"num_predict": 1},
        }
        try:
            async with session.post(
                f"{base}/api/generate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=300),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
            load_ns = int(data.get("load_duration") or 0)
            if load_ns:
                self.ctx.logger.info(
                    "[本地模型优化] %s 加载耗时 / load %.1fs",
                    model,
                    load_ns / 1e9,
                )
            return True
        except Exception as exc:  # noqa: BLE001
            self.ctx.logger.warning("[本地模型优化] %s 预热异常 / warm error: %s", model, exc)
            return False

    async def _check_capabilities(self, session: aiohttp.ClientSession, base: str) -> None:
        cfg = self.config.plugin
        for model, need, label in (
            (cfg.planner_model, "tools", "planner(工具调用/tool calls)"),
            (cfg.vision_model, "vision", "vlm(识图/vision)"),
        ):
            if not model:
                continue
            caps = await self._capabilities(session, base, model)
            if caps is None:
                self.ctx.logger.warning(
                    "[本地模型优化] 无法读取 %s 的能力 / cannot read capabilities", model
                )
                continue
            if need not in caps:
                self.ctx.logger.error(
                    "[本地模型优化] ⚠ %s 用作 %s，但缺少 %s 能力（实际: %s）。"
                    "请换用支持该能力的模型。",
                    model,
                    label,
                    need,
                    ",".join(caps) or "unknown",
                )
            else:
                self.ctx.logger.info(
                    "[本地模型优化] ✅ %s 支持 %s", model, need
                )

    async def _capabilities(
        self, session: aiohttp.ClientSession, base: str, model: str
    ) -> List[str] | None:
        try:
            async with session.post(
                f"{base}/api/show",
                json={"model": model},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
            caps = data.get("capabilities")
            if isinstance(caps, list):
                return [str(c) for c in caps]
            return []
        except Exception:  # noqa: BLE001
            return None
