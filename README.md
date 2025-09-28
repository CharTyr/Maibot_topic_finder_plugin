# MaiBot Topic Finder Plugin

This repository contains the MaiBot topic finder plugin and an offline testing harness.

## Offline testing

The plugin depends on the MaiBot host project. Because the evaluation environment cannot reach GitHub, this repository now ships a trimmed MaiBot stub inside `host_cache/MaiBot`. The `scripts/setup-and-test.sh` script will prefer this offline cache and only fall back to cloning the real repository when network access is available. When the offline cache is used, the script initialises a lightweight Git repository on the `offline-test-host` branch to mirror the workflow requested for hosting the stub.

### Quick start

```bash
bash scripts/setup-and-test.sh
```

The script will:

1. Copy the offline MaiBot stub (or clone the real repository if accessible) into `host-maibot/`.
2. Create a virtual environment inside the host directory.
3. Link the plugin into the host's `plugins/` directory.
4. Run `pytest` to execute the smoke tests located in `tests/`.

If you prefer to manage the host checkout manually, set the following environment variables before running the script:

- `HOST_DIR`: Target directory for the host application.
- `HOST_CACHE_DIR`: Path to a pre-populated MaiBot checkout.
- `HOST_REPO`: Remote URL for Git cloning when network access is available.
- `HOST_BRANCH`: Branch to checkout from the remote repository.

## Tests

Smoke tests live in `tests/test_offline_smoke.py`. They exercise the plugin against the offline host stub to ensure the generation pipeline produces a non-empty topic and that persona data is loaded correctly.
