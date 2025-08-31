# Notices & Tips

Important notes when working with Cadence.

## Plugins

- Ensure plugin packages have `__init__.py`
- `create_agent()` must be `@staticmethod`
- Validate with SDK: errors during validation will block loading
- Keep tools small, deterministic, and well-documented

## Environment

- Prefer absolute or project-root-relative `CADENCE_PLUGINS_DIR`
- Never commit real API keys; use `.env` locally and secrets in CI/CD
- Set `CADENCE_DEBUG=false` in production

## LLMs

- Choose provider and model per plugin metadata
- Keep temperature low for tool-using agents
- Watch token limits in prompts and outputs

## Performance

- Cache expensive initializations in `initialize()`
- Bind tools once in `bind_model()`
- Avoid heavy imports at module top level

## Troubleshooting

- Check logs for: discovery, registration, bundle creation, health checks
- Use `reload plugins` endpoint to hot-reload without restart
- Verify `should_continue` logic to avoid infinite loops
