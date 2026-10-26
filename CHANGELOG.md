# Changelog

## 1.0.0

- Initial release.
- Keep configured Ollama models loaded via `keep_alive`.
- Check `tools` capability for the planner model and `vision` for the vlm model.
- Warm up models on plugin load and on a configurable interval.
