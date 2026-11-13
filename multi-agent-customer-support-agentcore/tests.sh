#!/usr/bin/env bash
case "$1" in
  all) ARG=all ;;
  *)   ARG="task$1" ;;
esac
echo "\$ python tests/test_agent.py $ARG"
uv run python tests/test_agent.py "$ARG"