# HPCC Simulation Results Center

Welcome to the organized results management system for HPCC simulations.

## 📂 Quick Navigation

### Latest Results
- 🖼️ **[Full Dashboard](plots/dashboard.png)** - Comprehensive 9-panel overview
- 📈 **[FCT Analysis](plots/fct.png)** - Flow completion time detailed analysis
- 📊 **[Queue Length](plots/qlen.png)** - Congestion pattern time-series

### Documentation
- 📖 **[Full README](README.md)** - Complete usage guide and data format reference
- ⚡ **[Quick Start](QUICKSTART.sh)** - Fast commands reference
- 🔧 **[Organization Info](../RESULTS_ORGANIZATION.md)** - Detailed organization guide

### Tools
- 🛠️ **[organize_results.py](organize_results.py)** - Multi-run organizer with timestamping
- 📊 **[scripts/plot_dashboard.py](scripts/plot_dashboard.py)** - Comprehensive dashboard generator
- 📈 **[scripts/plot_fct.py](scripts/plot_fct.py)** - FCT analysis plotter
- 📉 **[scripts/plot_qlen.py](scripts/plot_qlen.py)** - Queue length plotter

### Data
- 📄 **[data/fct.txt](data/fct.txt)** - Flow completion time records
- 📄 **[data/qlen.txt](data/qlen.txt)** - Queue length samples

## 🚀 Common Tasks

### 1. View Current Results (30 seconds)
```bash
# Just open the PNG files
open results/plots/dashboard.png
```

### 2. Run Simulation & Get Results (2-5 minutes)
```bash
cd simulation
./waf --run 'scratch/third mix/config.txt'
cd ..
python3 results/organize_results.py
# Results saved with timestamp!
```

### 3. Regenerate Plots (10 seconds)
```bash
python3 results/scripts/plot_dashboard.py
```

### 4. Compare Multiple Runs (See all experiments)
```bash
python3 results/organize_results.py --list
# View results/runs/TIMESTAMP_HHMMSS/ directories
```

## 📊 What's Included

| Component | Files | Purpose |
|-----------|-------|---------|
| **Visualizations** | 3 PNG files | View results with charts and stats |
| **Scripts** | 3 Python files | Generate custom plots anytime |
| **Data** | 2 TXT files | Raw simulation output for analysis |
| **Documentation** | 4 MD files | Complete reference information |
| **Organization** | 1 Python script | Manage multiple runs with timestamps |

## 💡 Key Features

 **Organized Structure** - Everything in one place
 **Multiple Run Support** - Timestamped directories for tracking
 **Auto-Generation** - Plots generated automatically
 **Reusable Scripts** - Use same tools for all experiments
 **Well Documented** - Guides and references included
 **Data Preserved** - Raw data kept with each run

## 📈 Current Results

**Latest Simulation Run:**
- Flows Completed: 2
- CC Scheme: HPCC (CC_MODE=3)
- Average Slowdown: ~2.13x
- FCT Range: 35.67 - 36.69 ms

**Available Visualizations:**
- Dashboard with 9 analysis panels
- FCT analysis with 4 subplots
- Queue length time-series

## 🎯 Workflow Examples

### Single Run Analysis
```
1. cd simulation && ./waf --run 'scratch/third mix/config.txt'
2. cd .. && python3 results/organize_results.py
3. View results/plots/dashboard.png
```

### Comparing Different CC Schemes
```
1. Run with HPCC (CC_MODE=3)
   → organize_results.py creates results/runs/timestamp1/
2. Run with DCQCN (CC_MODE=1)
   → organize_results.py creates results/runs/timestamp2/
3. Compare PNG files side-by-side
```

### Advanced Analysis
```
1. For statistical comparison: use analysis/fct_analysis.py
2. For packet-level debugging: use analysis/trace_reader
3. See analysis/README.md for details
```

## 🔍 Data Interpretation

### Dashboard Metrics
- **Configuration**: CC scheme and simulation parameters
- **Queue Timeline**: Real-time congestion patterns
- **FCT vs Size**: How flow size affects completion time
- **Slowdown**: Performance degradation due to congestion
- **Statistics**: Min/Max/Mean FCT and slowdown values

### Typical Values
- **Good**: Slowdown < 2.0, queue length < 10% of buffer
- **Acceptable**: Slowdown < 5.0, queue length < 50% of buffer
- **Poor**: Slowdown > 5.0 or queue overflow

## 📚 Documentation Hierarchy

```
START HERE:
 This file (INDEX.md)
  └─ Quick overview and navigation

FOR QUICK START:
 QUICKSTART.sh
  └─ Common commands

FOR DETAILED INFO:
 README.md
  └─ Complete usage guide

FOR ORGANIZATION DETAILS:
 ../RESULTS_ORGANIZATION.md
   └─ Folder structure and workflow
```

## 🤝 Getting Help

1. **Can't find results?**
   - Check `plots/` for PNG files
   - Check `data/` for raw data
   - Check `runs/` for timestamped results

2. **Want to regenerate plots?**
   - Use `python3 scripts/plot_dashboard.py`
   - See README.md for script details

3. **Need to organize multiple runs?**
   - Use `python3 organize_results.py`
   - Or `python3 organize_results.py --list` to see existing runs

4. **Want advanced analysis?**
   - See `analysis/README.md`
   - Use `analysis/fct_analysis.py` for statistical comparison

## 📝 File Descriptions

### plot_dashboard.py
Generates a comprehensive 9-panel dashboard showing:
- Configuration parameters
- Queue evolution over time
- FCT vs flow size correlation
- Slowdown analysis
- Flow timeline
- Statistical summaries
- Distribution histograms

### plot_fct.py  
Detailed FCT analysis with:
- FCT vs flow size (log scale)
- Slowdown vs flow size
- FCT distribution
- Statistical summary

### plot_qlen.py
Time-series visualization of:
- Queue length over simulation time
- Shows congestion patterns and recovery

### organize_results.py
Multi-run management:
- Creates timestamped result directories
- Copies data files
- Auto-generates plots
- Creates INDEX.md for each run
- Lists all organized runs

## 🎓 Learning Resources

- HPCC Paper: [SIGCOMM 2019](https://rmiao.github.io/publications/hpcc-li.pdf)
- PINT Paper: [SIGCOMM 2020](https://liyuliang001.github.io/publications/pint.pdf)
- NS-3 Documentation: Check `simulation/README.md`
- Simulation Configuration: See `simulation/mix/config_doc.txt`

---

**Last Updated**: 2024-01-24  
**Organization Version**: 1.0  
**Status**: ✅ Ready for use
