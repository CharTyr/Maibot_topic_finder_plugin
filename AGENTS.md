# How to test this MaiBot plugin

## Steps
1. Clone host (MaiBot):
   git clone --depth=1 --branch ${HOST_BRANCH:-main} https://github.com/MaiM-with-u/MaiBot.git host-maibot
2. Run setup & tests:
   bash scripts/setup-and-test.sh

## Environment (optional)
- HOST_BRANCH=main
- PYTHON=python3.11
