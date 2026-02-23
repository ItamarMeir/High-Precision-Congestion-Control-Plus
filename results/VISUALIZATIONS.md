# Network Visualization Suite

## 📊 Generated Visualizations

### 1. **dashboard.png** (156 KB) ⭐ START HERE
Comprehensive 9-panel overview of simulation results:
- **Configuration** - CC scheme and key parameters
- **Queue Timeline** - Real-time congestion evolution
- **FCT vs Size** - How flow size affects completion time  
- **Slowdown Analysis** - Performance degradation
- **Flow Timeline** - When each flow started/completed
- **Statistics Summary** - Min/Max/Mean metrics
- **FCT Distribution** - Histogram of flow completion times
- **Slowdown Distribution** - Histogram of slowdown ratios

**Best for:** Quick overview of overall simulation performance

---

### 2. **fct.png** (96 KB)
Four-panel detailed Flow Completion Time analysis:
- **FCT vs Flow Size** - Scatter plot (log scale)
- **Slowdown vs Flow Size** - How much did each flow suffer
- **FCT Distribution** - Histogram of all FCTs
- **Key Statistics** - Min/Max/Mean/Median values

**Best for:** Understanding per-flow performance and fairness

---

### 3. **qlen.png** (103 KB)
Queue length visualization across all network links:
- **65 individual link queues** - One line per switch port
- **Time-series plot** - Queue evolution during simulation
- **Shows congestion patterns** - When/where bottlenecks occur
- **Identifies hot spots** - Which links get congested

**Best for:** Understanding congestion patterns and switch behavior

---

### 4. **topology.png** (1.1 MB)
Network topology visualization:
- **Graph layout** - Shows all 257 nodes and 256 connections
- **Node types** - Hosts (65) vs Switches (1)
- **Link connectivity** - Star topology with central switch
- **Statistics panel** - Network summary information

**Best for:** Understanding network structure and connectivity

---

## 🎨 How to View Visualizations

All PNG files are located in `plots/` directory:

```bash
# View individual plots
open plots/dashboard.png
open plots/fct.png
open plots/qlen.png
open plots/topology.png

# View all plots at once (Linux/Mac)
ls -lh plots/*.png
```

## 📈 What Each Metric Means

### Flow Completion Time (FCT)
- **Definition**: Time from when flow starts to when last packet arrives
- **Units**: Milliseconds
- **Lower is better**: Indicates faster application response

### Slowdown
- **Definition**: FCT / optimal FCT (if no congestion)
- **Formula**: `slowdown = actual_fct / (flow_size / link_speed)`
- **Interpretation**: 2.0 = 2x slower than ideal
- **Lower is better**: Close to 1.0 means efficient operation

### Queue Length
- **Definition**: Number of bytes in buffer at each switch port
- **Units**: Bytes
- **Meaning**: Higher = more congestion, packet wait time
- **Lower is better**: Less queuing delay

## 🔬 Interpreting Results

### Good Performance Characteristics
- Slowdown < 2.0 for most flows
- Queue length mostly under 10% of buffer size  
- FCT increases linearly with flow size
- No sudden spikes in queue length

### Warning Signs  
- Slowdown > 5.0 for small flows (unfair)
- Queue overflow events (not shown in these plots)
- Non-linear FCT vs size relationship
- Sustained high queue lengths

## 🛠️ Regenerating Visualizations

If you modify the simulation output files, regenerate plots:

```bash
cd results

# Regenerate individual plots
python3 scripts/plot_dashboard.py ../simulation/mix/
python3 scripts/plot_fct.py ../simulation/mix/fct.txt
python3 scripts/plot_qlen.py ../simulation/mix/qlen.txt
python3 scripts/plot_topology.py ../simulation/mix/topology.txt

# Or regenerate all at once
for script in scripts/plot_*.py; do
  python3 "$script"
done
```

## 📊 Built-in NS-3 Visualization Tools

The simulator also supports:

### 1. **NetAnim** (XML Animation Format)
- Generates `.xml` animation files
- Visualized in NetAnim GUI (cross-platform)
- Shows packet flows in real-time replay
- Requires code modification to enable

### 2. **Trace Files** (`mix.tr`)
- Full packet-level event recording
- Can be analyzed with trace readers
- Supported by multiple analysis tools
- Includes transmit/receive/drop events

### 3. **PyViz** (Python Real-time Visualization)
- Live visualization during simulation
- PyQt/Tkinter based
- Shows network activity in real-time
- Useful for debugging

To enable: See `VISUALIZATION_GUIDE.md` in project root

## 📁 File Locations

```
results/
 plots/              ← All PNG visualizations
   ├── dashboard.png
   ├── fct.png
   ├── qlen.png
   └── topology.png
 data/               ← Raw simulation data
   ├── fct.txt
   ├── qlen.txt
   └── topology.txt
 scripts/            ← Visualization generators
    ├── plot_dashboard.py
    ├── plot_fct.py
    ├── plot_qlen.py
    └── plot_topology.py
```

---

**Last Generated**: 2024-01-24  
**Simulation**: HPCC (CC_MODE=3) with default configuration  
**Network**: 65 hosts, 1 switch topology, 100Gbps links
