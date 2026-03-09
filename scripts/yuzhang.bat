@echo off
setlocal enabledelayedexpansion

set CIRCUITS=c432 c880 c3540 c7552

set TARGET_SCRIPT=random_sim.py

echo ===================================================
echo Batch script: %TARGET_SCRIPT%
echo ===================================================

for %%C in (%CIRCUITS%) do (
    echo.
    echo [*] Processing Circuit: %%C
    python %TARGET_SCRIPT% %%C
)

echo.
echo ===================================================
echo All simulations completed.
echo ===================================================
pause