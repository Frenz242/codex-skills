#!/usr/bin/env sh

set -u

case $0 in
    */*) script_path=$0 ;;
    *) script_path=$(command -v -- "$0") ;;
esac
script_dir=${script_path%/*}
if [ "$script_dir" = "$script_path" ]; then
    script_dir=.
fi
script_dir=$(CDPATH= cd -- "$script_dir" && pwd)
feedback_store="$script_dir/feedback_store.py"

is_supported_python() {
    "$1" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1
}

run_if_supported() {
    candidate=$1
    if [ -n "$candidate" ] && is_supported_python "$candidate"; then
        shift
        exec "$candidate" "$feedback_store" "$@"
    fi
}

if [ -n "${CODEX_SKILL_PYTHON:-}" ]; then
    run_if_supported "$CODEX_SKILL_PYTHON" "$@"
fi

if [ -n "${HOME:-}" ]; then
    for bundled_python in \
        "$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3" \
        "$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python"
    do
        if [ -x "$bundled_python" ]; then
            run_if_supported "$bundled_python" "$@"
        fi
    done
fi

for candidate_name in python3 python
do
    candidate=$(command -v "$candidate_name" 2>/dev/null || true)
    run_if_supported "$candidate" "$@"
done

printf '%s\n' \
    'feedback-store launcher: no supported Python 3 interpreter found; set CODEX_SKILL_PYTHON to a Python 3 executable.' \
    >&2
exit 127
