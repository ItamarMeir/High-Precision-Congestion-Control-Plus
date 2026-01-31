# CWND/RTT Analysis Plot - Usage & Robustness Guide

## Updated Script: `plot_cwnd_rtt_analysis.py`

The plot generation has been completely rewritten to be **highly robust** for any topology and flow configuration.

### Key Improvements

#### 1. **Fixed Header Overlap** ✅
- Adjusted figure layout with proper spacing (top margin 0.94)
- Added dedicated gridspec for precise control
- Increased hspace (vertical spacing) from 0.25 to 0.35
- Title now positioned at y=0.98 with clearance

#### 2. **Both Flows Displayed** ✅
- Panel 1 (CWND over Time) now shows all flows
- Different line styles for each flow:
  - Flow 0: solid blue line (-)
  - Flow 1: dashed red line (--)
  - Additional flows: dash-dot, dotted, etc.
- FCT marker for all flows
- Legend with flow identifiers

#### 3. **Fully Dynamic & Robust** ✅
- **Topology-independent**: Extracts flows from trace file
- **Flow-count independent**: Automatically detects number of flows
- **Data-driven**: All statistics calculated from actual trace data
- **No hardcoded values**: Scales to any CWND range, RTT value, rate

### Automatic Adaptation

The script automatically adjusts to:
- **Different number of flows** (1 to N flows detected)
- **Different link speeds** (1 Gbps, 10 Gbps, 100 Gbps, etc.)
- **Different packet sizes** (affects serialization delay)
- **Different topologies** (any source/destination pairs)
- **Different CWND ranges** (small or large windows)
- **Different RTT values** (extracted from steady-state data)

### Usage

#### Basic Usage (Current Setup)
```bash
python3 scripts/plot_cwnd_rtt_analysis.py \
  data/cwnd_two_senders_heavy.txt \
  plots/cwnd_rtt_analysis.png
```

#### With Different Simulation
```bash
python3 scripts/plot_cwnd_rtt_analysis.py \
  data/cwnd_custom_flows.txt \
  plots/cwnd_custom_analysis.png
```

#### Default (if no arguments)
```bash
python3 scripts/plot_cwnd_rtt_analysis.py
# Uses: results/data/cwnd_two_senders_heavy.txt
# Output: results/plots/cwnd_rtt_analysis.png
```

### Integration with Plotting Pipeline

Add to `run_all_plots.py`:
```python
import subprocess

# Add to main() function:
subprocess.run([
    "python3", "scripts/plot_cwnd_rtt_analysis.py",
    "data/cwnd_two_senders_heavy.txt",
    "plots/cwnd_rtt_analysis.png"
], check=True)
```

### What Each Panel Shows (Dynamically)

**Panel 1: Window Size Over Time**
- All flows from trace file
- Different colors and line styles for each flow
- Solid line: Flow 0
- Dashed line: Flow 1
- Dash-dot: Flow 2 (if present)
- etc.
- FCT (Flow Completion Time) marked as green vertical line

**Panel 2: Rate vs CWND Mathematical Relationship**
- Blue line: Theoretical rate given RTT
- Colored dots: Actual observed operating points
- Each flow shown separately
- One dot per flow showing (CWND, Rate) pair

**Panel 3: Flow Throughput Distribution**
- Bar chart for each flow
- Total throughput bar
- Values labeled on each bar
- Adaptive scaling based on actual rates

**Panel 4: RTT Composition Breakdown**
- Pie chart showing components
- Percentages calculated from measured RTT
- Components scaled proportionally

### Robustness Features

1. **Error Handling**
   - Validates CWND file exists and is readable
   - Handles missing/malformed lines gracefully
   - Returns None for RTT if calculation fails
   - Shows placeholder text if data unavailable

2. **Dynamic Scaling**
   - Auto-detects max CWND to set y-axis limits
   - Adjusts window unit (B, KB, MB) based on max value
   - Scales rate calculations to any link speed
   - RTT extracted mathematically (not hardcoded)

3. **Flow Detection**
   - Reads all (src, dst, sport, dport) combinations from trace
   - Supports any number of flows
   - Sorts flows consistently for reproducibility
   - Assigns colors/styles dynamically

4. **Steady-State Detection**
   - Identifies transmission start/end automatically
   - Skips first 15-20% of data (ramp-up phase)
   - Uses middle 70% for statistics (steady state)
   - Ignores last 10% (cool-down phase)

### Current Results

```
✓ Analysis dashboard saved to: plots/cwnd_rtt_analysis.png
  RTT: 20.00 μs
  Flows: 2
    Flow 0→2: 0.480 Gbps, CWND: 1.17 KB
    Flow 1→2: 0.480 Gbps, CWND: 1.17 KB
```

### Testing with Different Configurations

To verify robustness with new simulations:

```bash
# After running new simulation:
cd results
python3 scripts/plot_cwnd_rtt_analysis.py \
  data/cwnd_my_new_config.txt \
  plots/cwnd_my_new_config_analysis.png

# Verify output
ls -lh plots/cwnd_*_analysis.png
file plots/cwnd_*_analysis.png
```

### Technical Details

**RTT Calculation**
- Formula: `RTT = CWND × 8 / Rate`
- Uses median of steady-state samples to avoid outliers
- Extracted from trace data (no manual entry needed)

**Steady-State Period**
- Identified as 15%-90% of transmission timeline
- Provides 75% of total flow duration
- Excludes initial ramp-up and final cool-down

**Flow Colors & Styles**
```
Flow 0: blue solid    (-)
Flow 1: red dashed    (--)
Flow 2: green dash-dot (-.
Flow 3: orange dotted (:)
Flow 4+: cycle through above
```

### Files

- **Script**: `results/scripts/plot_cwnd_rtt_analysis.py` (robust, dynamic)
- **Output**: `results/plots/cwnd_rtt_analysis.png` (current data)
- **Input**: `results/data/cwnd_*.txt` (any CWND trace file)

### Example with 4-Flow Scenario

If you run with 4 competing flows, the script will:
1. ✅ Detect all 4 flows from trace
2. ✅ Plot each with different line style
3. ✅ Calculate individual CWND/rate for each
4. ✅ Show all 4 in throughput bar chart
5. ✅ Extract RTT from aggregate data
6. ✅ Scale all plots appropriately

**No code changes needed** - it adapts automatically!

### Backward Compatibility

- Still works with single-flow scenarios
- Handles topology with any number of nodes
- Compatible with different link speeds
- Works with various packet sizes/flows
