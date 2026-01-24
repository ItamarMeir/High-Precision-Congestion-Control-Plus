#!/bin/bash
# Quick start guide for HPCC Simulation Results Management

set -e

echo "========================================="
echo "HPCC Simulation Results Organization"
echo "========================================="
echo ""

# Navigate to workspace
WORKSPACE="/workspaces/High-Precision-Congestion-Control-Plus"
cd "$WORKSPACE"

echo "✓ Workspace: $WORKSPACE"
echo ""

# Show current results
echo "Current Results Structure:"
echo "---------------------------------------"
ls -lh results/ | grep -E '^d' | awk '{print "  " $NF}'
echo ""

echo "Quick Actions:"
echo "---------------------------------------"
echo ""
echo "1. View Latest Results:"
echo "   - Dashboard: results/plots/dashboard.png"
echo "   - FCT Analysis: results/plots/fct.png"
echo "   - Queue Length: results/plots/qlen.png"
echo ""

echo "2. Organize Multiple Runs (with timestamps):"
echo "   python3 results/organize_results.py"
echo ""

echo "3. List All Organized Runs:"
echo "   python3 results/organize_results.py --list"
echo ""

echo "4. Regenerate Plots:"
echo "   python3 results/scripts/plot_dashboard.py"
echo "   python3 results/scripts/plot_fct.py results/data/fct.txt"
echo "   python3 results/scripts/plot_qlen.py results/data/qlen.txt"
echo ""

echo "5. Run New Simulation:"
echo "   cd simulation"
echo "   ./waf --run 'scratch/third mix/config.txt'"
echo "   cd .."
echo "   python3 results/organize_results.py"
echo ""

echo "========================================="
