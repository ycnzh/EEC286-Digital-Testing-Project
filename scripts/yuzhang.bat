#!/bin/bash

# Define your circuits and target script
CIRCUITS="c432 c880 c3540 c7552"
TARGET_SCRIPT="random_sim.py"

echo "==================================================="
echo "Batch script: $TARGET_SCRIPT"
echo "==================================================="

# Loop through each circuit and run the script
for C in $CIRCUITS; do
    echo ""
    echo "[*] Processing Circuit: $C"
    python3 "$TARGET_SCRIPT" "$C"
done

echo ""
echo "==================================================="
echo "All simulations completed."
echo "==================================================="

# Equivalent to the Windows 'pause' command
read -n 1 -s -r -p "Press any key to continue..."
echo ""