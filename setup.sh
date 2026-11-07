#!/usr/bin/env bash
#
# One-time setup on Windows (Git Bash), macOS or Linux; safe to rerun.
#
# Native: pi (Node), git, docker, and Python for CodeScribe. Everything that builds or runs the
# apps lives in two docker images: sc26-translate and sc26-mxp (RAPTOR, MPI, OpenEvolve).

set -uo pipefail
cd "$(dirname "$0")"

require() {
    if ! command -v "$1" > /dev/null; then
        echo "missing: $1 ($2)"
        exit 1
    fi
}

require node "Node.js >= 20, for pi"
require npm "comes with Node.js"
require git "Git (on Windows: Git for Windows, which also provides Git Bash)"
require docker "Docker Desktop, or Docker Engine on Linux"

python=$(command -v python3 || command -v python || true)
if [ -z "$python" ]; then
    echo "missing: python3 (>= 3.10, for CodeScribe)"
    exit 1
fi

# pi
if ! command -v pi > /dev/null; then
    npm install -g @earendil-works/pi-coding-agent || exit 1
fi
echo "pi $(pi --version)"

# Submodules and images
git submodule update --init --recursive || exit 1
docker build -t sc26-translate code-translation || exit 1
docker build -t sc26-mxp mxp-optimization || exit 1
echo "images sc26-translate and sc26-mxp built"

# CodeScribe, natively
if [ ! -d .venv ]; then
    "$python" -m venv .venv || exit 1
fi
pip=.venv/bin/pip
if [ ! -x "$pip" ]; then
    pip=.venv/Scripts/pip.exe
fi
if ! command -v code-scribe > /dev/null && [ ! -e .venv/bin/code-scribe ] && [ ! -e .venv/Scripts/code-scribe.exe ]; then
    "$pip" install --quiet "git+https://github.com/akashdhruv/CodeScribe.git" || exit 1
fi
echo "CodeScribe ready"

# Endpoint
grep -q "<your key>" config.yaml && echo "edit config.yaml: OPENAI_COMP_APIKEY"

# Both apps, in their containers
code-translation/dev/bin/oracle > setup.log 2>&1 || {
    tail -n 5 setup.log
    exit 1
}
echo "code-translation oracle passes"

mxp-optimization/dev/bin/box make check > setup.log 2>&1 || {
    tail -n 5 setup.log
    exit 1
}
echo "mxp-optimization tests pass"
rm -f setup.log
