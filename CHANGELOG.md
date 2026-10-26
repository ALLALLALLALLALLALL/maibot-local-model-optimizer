# Changelog

## 1.2.0

- Add `create_plugin()` factory required by the MaiBot plugin center.
- Align `host_application` / `sdk` upper bounds with tested versions.
- Declare the `config.get` capability and drop the unused i18n block.

## 1.1.0

- Remove hardcoded model names: every local setup is different.
- `models` defaults to empty and then keeps whatever Ollama already has loaded warm.
- `planner_model` / `vision_model` default to empty and then print a table of
  installed models and their capabilities instead of checking one fixed model.

## 1.0.0

- Initial release.
- Keep configured Ollama models loaded via `keep_alive`.
- Check `tools` capability for the planner model and `vision` for the vlm model.
- Warm up models on plugin load and on a configurable interval.
