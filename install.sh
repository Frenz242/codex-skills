#!/usr/bin/env sh
set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
for candidate in "${CODEX_SKILL_PYTHON:-}" \
    "$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3" \
    python3 python
do
    if [ -n "$candidate" ] && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 10))' >/dev/null 2>&1; then
        exec "$candidate" "$script_dir/scripts/install_skills.py" "$@"
    fi
done
printf '%s\n' 'Python 3.10+ is required. Install it or set CODEX_SKILL_PYTHON to its executable.' >&2
exit 127
