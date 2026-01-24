# Results Organization Summary

## ✅ What Was Done

Created a comprehensive results management system for HPCC simulations with the following structure:

### Directory Organization

```
results/
├── README.md                 # Full documentation
├── QUICKSTART.sh             # Quick reference guide
├── organize_results.py       # Multi-run organization script
│
├── scripts/                  # Visualization scripts (current)
│   ├── plot_dashboard.py      # Comprehensive dashboard generator
│   ├── plot_fct.py            # FCT analysis plotter
│   ├── plot_qlen.py           # Queue length plotter
│   └── plot_cwnd.py           # Cwnd-like window plotter
│   └── legacy/                # Archived older scripts
│
└── plots/                    # Latest generated visualizations
```

## 📊 Available Visualizations

1. **[results/plots/dashboard.png](../results/plots/dashboard.png)**
   - 9-panel comprehensive overview
   - Configuration summary
   - Queue timeline
   - FCT analysis
   - Statistical summaries
   - Best for: Quick overall assessment

2. **[results/plots/fct.png](../results/plots/fct.png)**
   - 4-panel detailed FCT analysis
   - FCT vs flow size
   - Slowdown analysis
   - Distribution histograms
   - Best for: Understanding flow performance

3. **[results/plots/qlen.png](../results/plots/qlen.png)**
   - Queue length time-series
   - Shows congestion patterns
   - Best for: Network dynamics analysis

## 🚀 Quick Start

### View Current Results
```bash
# Just open the PNG files in results/plots/
open results/plots/dashboard.png
```

### Run Simulation and Organize Results
```bash
# 1. Run simulation
cd simulation
./waf --run 'scratch/third mix/configs/config.txt'
cd ..

# 2. Organize results (creates timestamped directory)
python3 results/organize_results.py

# 3. List all runs
python3 results/organize_results.py --list
```

### Regenerate Visualizations
```bash
cd results

# Generate individual plots
python3 scripts/plot_dashboard.py simulation/mix
python3 scripts/plot_fct.py simulation/mix/outputs/fct/fct.txt
python3 scripts/plot_qlen.py simulation/mix/outputs/qlen/qlen.txt
python3 scripts/plot_cwnd.py simulation/mix/outputs/cwnd/cwnd.txt
```

## 📁 File Locations

| File | Location | Purpose |
|------|----------|---------|
| Latest Dashboard | `results/plots/dashboard.png` | Full results overview |
| Latest FCT Analysis | `results/plots/fct.png` | Flow performance details |
| Latest Queue Data | `results/plots/qlen.png` | Network congestion patterns |
| FCT Raw Data | `simulation/mix/outputs/fct/fct.txt` | Flow completion times |
| Queue Raw Data | `simulation/mix/outputs/qlen/qlen.txt` | Queue length samples |
| Trace Files | `simulation/mix/outputs/trace/` | Packet-level traces |
| Visualization Scripts | `results/scripts/` | Python plotting tools |
| Documentation | `results/README.md` | Full documentation |

## 🔄 Organization Workflow

### Single Run (Quick)
```
simulation/mix/
   ├── configs/   (configs)
   ├── inputs/    (trace nodes)
   ├── flows/     (flow definitions)
   ├── topologies/(topology files)
   └── outputs/   (fct/qlen/pfc/trace/cwnd/anim)
```

### Multiple Runs (Timestamped)
```
Run 1 →  Run 2 →  Run 3
   ↓        ↓        ↓
results/runs/20240124_100000/
results/runs/20240124_110000/
results/runs/20240124_120000/
   ↓        ↓        ↓
View INDEX.md and plots/ in each
```

## 💡 Tips

1. **First Time?**
   - Run: `bash results/QUICKSTART.sh`
   - View current results in `results/plots/`

2. **Multiple Experiments?**
   - Use `organize_results.py` to create timestamped folders
   - Each run keeps separate data and visualizations
   - List all runs: `python3 results/organize_results.py --list`

3. **Comparing Runs?**
   - Store configs and results in separate timestamped folders
   - Compare PNG files side-by-side
   - Use FCT analysis script for statistical comparison

4. **Troubleshooting?**
   - Check `results/README.md` for detailed documentation
   - Ensure Python 3, matplotlib, numpy are installed
   - Verify simulation output files exist before visualizing

## 📈 Next Steps

1. **Run different configurations:**
   ```bash
   cd simulation
   ./waf --run 'scratch/third mix/fat.txt'  # Different topology
   ```

2. **Compare multiple runs:**
   - Use the `fct_analysis.py` in `analysis/` folder
   - Compare FCT statistics across different CC schemes

3. **Generate research plots:**
   - Modify scripts to match publication requirements
   - Use raw data for custom analysis

4. **Archive results:**
   - Save timestamped run directories for reproducibility
   - Include config.txt with each run

## 📝 File Descriptions

### plot_dashboard.py
- **Purpose**: Generate comprehensive results overview
- **Input**: `simulation/mix` directory
- **Output**: dashboard.png
- **Time**: ~5 seconds

### plot_fct.py
- **Purpose**: Detailed flow completion time analysis
- **Input**: fct.txt file
- **Output**: fct.png with 4 subplots (96 KB)
- **Time**: ~3 seconds

### plot_qlen.py
- **Purpose**: Queue length time-series visualization
- **Input**: qlen.txt file
- **Output**: qlen.png (33 KB)
- **Time**: ~2 seconds

### organize_results.py
- **Purpose**: Organize results with timestamps and auto-generate plots
- **Usage**: `python3 organize_results.py [sim_dir]`
- **Output**: `results/runs/YYYYMMDD_HHMMSS/` directory with plots and data
- **Features**: 
  - Automatic timestamping
  - Plot generation
  - Index file creation
  - Run listing

## 🎯 Best Practices

1. **Always include config:**
   - Simulation config.txt is saved with each run
   - Helps reproduce results later

2. **Keep trace files:**
   - Save mix.tr files for detailed analysis
   - Required for packet-level debugging

3. **Organize by date:**
   - Use organize_results.py for automatic timestamping
   - Easy to track simulation history

4. **Document parameters:**
   - Note which CC scheme (HPCC/DCQCN/TIMELY/DCTCP)
   - Record topology and traffic patterns
   - Include any modifications

## 📞 Support

For more information:
- Read `results/README.md` - Full documentation
- Check `analysis/README.md` - Advanced analysis tools
- Review `simulation/README.md` - Simulation configuration
