# Network Topology Visualization

This NS-3 simulator includes built-in visualization tools for analyzing network behavior.

## 🎨 Available Tools

### 1. NetAnim (Network Animator)
- **What it does**: Generates XML animation files showing node positions, links, and packet flows
- **Output**: `.xml` file that can be visualized in the NetAnim GUI tool
- **Best for**: Understanding topology layout and packet movement

### 2. Python Visualizer (Real-time)
- **What it does**: Live visualization of simulation as it runs
- **Output**: Interactive PyQt/Tkinter window
- **Best for**: Debugging and real-time monitoring

### 3. Trace Files
- **What it does**: Records all packet movements and events
- **Output**: `.tr` file with detailed packet traces
- **Best for**: Post-simulation analysis, understanding traffic patterns

## 📊 Current Output Files

After each simulation, you get:
- `simulation/mix/outputs/fct/*.txt` - Flow completion times
- `simulation/mix/outputs/qlen/*.txt` - Queue lengths per link per timestamp
- `simulation/mix/outputs/pfc/*.txt` - Priority Flow Control stats
- `simulation/mix/outputs/trace/*.tr` - Full packet trace
- `simulation/mix/outputs/cwnd/*.txt` - Cwnd-like rate/window traces
- `simulation/mix/outputs/anim/*.xml` - NetAnim outputs

## 🚀 How to Enable Visualization

### Option 1: Enable NetAnim (Recommended)
Modify `scratch/third.cc` to add:

```cpp
#include "ns3/netanim-module.h"

// ... in main() ...

AnimationInterface anim("topology-animation.xml");
anim.SetConstantPosition(node, x, y);  // Set node positions

Simulator::Run();
Simulator::Destroy();
```

Then visualize with NetAnim tool.

### Option 2: Enable Trace Visualization
The `simulation/mix/outputs/trace/*.tr` files contain full packet trace data. Tools to analyze:
- **PyViz** (Python-based): `./waf --pyrun=script.py`
- **Trace readers**: Custom C++ programs (see analysis/)

### Option 3: Custom Topology Plot
Create a Python visualization from the topology file:

```python
# Parse simulation/mix/topologies/*.txt for node positions
# Render with matplotlib/networkx
```

## 📁 Visualization Files in Repo

- **src/netanim/** - NetAnim module with animation support
- **src/visualizer/** - Python visualizer with PyQt integration
- **src/netanim/examples/** - Example animation scripts (dumbbell, grid, etc.)

## 🔍 What's Currently Captured

Current simulations record:
1. **Queue evolution** (outputs/qlen/*.txt) - Per-link queue length snapshots
2. **Flow completion** (outputs/fct/*.txt) - Start time, completion time, flow size for each flow
3. **Full trace** (outputs/trace/*.tr) - Packet-level events (tx/rx/drop at each device)
4. **Rate/window** (outputs/cwnd/*.txt) - Cwnd-like rate/window updates

## 💡 Next Steps

1. **To visualize topology**: Use results/scripts/plot_topology.py with a config
2. **To see packet flows**: Use the full trace file with analysis/trace_reader
3. **To enable NetAnim**: Set ENABLE_ANIM and ANIM_OUTPUT_FILE in a config

Would you like me to create a topology visualization script or enable NetAnim in the simulator?
