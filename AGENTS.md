# How to test this MaiBot plugin
## Steps
1. Clone host (MaiBot) or use the offline cache:
   - Preferred offline path: `host_cache/MaiBot`
   - Script fallback: `HOST_CACHE_DIR` env var
   - Remote fallback: `git clone --depth=1 --branch ${HOST_BRANCH:-main} ${HOST_REPO}`
2. Run setup & tests:
   bash scripts/setup-and-test.sh
## Environment (optional)
- HOST_BRANCH=main
- PYTHON=python3.11
