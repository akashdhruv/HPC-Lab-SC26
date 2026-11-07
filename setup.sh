#!/usr/bin/env bash
#
# One-time setup on Windows (Git Bash), macOS or Linux; safe to rerun.
#
# Native: git, docker, Python (the entry points and the CodeScribe loop) and your orchestrator.
# Everything that builds or runs the apps lives in two docker images: hpc-lab-translate and
# hpc-lab-mxp (RAPTOR, MPI, OpenEvolve).

set -uo pipefail
cd "$(dirname "$0")"

require() {
    if ! command -v "$1" > /dev/null; then
        echo "missing: $1 ($2)"
        exit 1
    fi
}

require git "Git (on Windows: Git for Windows, which also provides Git Bash)"
require docker "Docker Desktop, or Docker Engine on Linux"

python=$(command -v python3 || command -v python || true)
if [ -z "$python" ]; then
    echo "missing: python (>= 3.10)"
    exit 1
fi

# pi, if Node.js is here and no pi yet (any other orchestrator works too)
if command -v npm > /dev/null && ! command -v pi > /dev/null; then
    npm install -g @earendil-works/pi-coding-agent || exit 1
fi
command -v pi > /dev/null && echo "pi $(pi --version)"

# Submodules and images
git submodule update --init --recursive || exit 1
docker build -t hpc-lab-translate code-translation || exit 1
docker build -t hpc-lab-mxp mxp-optimization || exit 1
echo "images hpc-lab-translate and hpc-lab-mxp built"

# CodeScribe, natively
if [ ! -d .venv ]; then
    "$python" -m venv .venv || exit 1
fi
venv=.venv/bin/python
if [ ! -x "$venv" ]; then
    venv=.venv/Scripts/python.exe
fi
if ! "$venv" -c "import codescribe" 2> /dev/null; then
    "$venv" -m pip install --quiet "git+https://github.com/akashdhruv/CodeScribe.git" || exit 1
fi
echo "CodeScribe ready in .venv (dev/bin/loop uses it)"

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
