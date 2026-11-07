@echo off
rem Windows shim for CodeScribe (cmd.exe): runs dev/bin/readiness with bash.
bash "%~dp0readiness" %*
