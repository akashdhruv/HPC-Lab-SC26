@echo off
rem Windows shim for CodeScribe (cmd.exe): runs dev/bin/build with bash.
bash "%~dp0build" %*
