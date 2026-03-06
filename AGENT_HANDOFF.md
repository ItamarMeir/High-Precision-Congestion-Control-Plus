# Agent Handoff — HPCC+ Study Cases Pipeline (Mar 5, 2026)

## What Is Being Done

We are running a full pipeline for **7 study cases (Case 0–6)** of the HPCC/HPCC+ simulation:

1. **Simulate** each case using the custom `./run.sh` script inside the Docker container
2. **Collect** all data files (`.txt`, `.tr`, `.csv`) and move them into the case's `data/` folder
3. **Clean** old data: each case `data/` folder should contain ONLY data from its most recent simulation run
4. **Plot** all visualizations using `python3 results/run_all_plots.py --base-dir <case_dir>/`

Each case produces:
- **Static PNGs** (in `case_dir/plots/`): topology, FCT, RX buffer, PFC, queue depth CDF, ACK analysis, CWND/RTT, switch throughput, comprehensive dashboard
- **Interactive HTMLs** (in `case_dir/interactive_plots/`): cwnd/rtt, int_queue_depth, rx_buffer, switch_throughput, fct, ack_analysis

---

## Current Progress

| Case | Description | Sim | Data Clean | Plots |
|:--|:--|:--|:--|:--|
| 0 | Full Rate Pull (HPCC+) | ✅ | ✅ | ✅ |
| 1 | Dynamic Pull Rate (HPCC) | ✅ | ✅ | ✅ |
| 2 | Dynamic Pull Rate (HPCC+) | ✅ | ✅ | ✅ |
| 3 | Pull 100-5-20-50-100 (HPCC) | ✅ | ✅ | ✅ |
| 4 | Pull 100-5-20-50-100 (HPCC+) | ✅ | ✅ | ✅ |
| 5 | Pull 100-90-70-50-10 (HPCC) | ✅ | ✅ | ✅ |
| 6 | Pull 100-90-70-50-10 (HPCC+) | ✅ | ✅ | ✅ |

---

## Plan For Remaining Cases

After Case 4 simulation completes:
1. Move `results/data/*` → `case4/data/`, then run `run_all_plots.py` for Case 4
2. Run Case 5 simulation → move data → plots
3. Run Case 6 simulation → move data → plots

**Important**: After each docker simulation completes, always run:
```bash
cp -r /home/itamar/WSL_Clones/High-Precision-Congestion-Control-Plus/results/data/* <case_dir>/data/
rm -f /home/itamar/WSL_Clones/High-Precision-Congestion-Control-Plus/results/data/*
```

---

## Key Commands

```bash
# Simulate a case (run from repo root)
docker compose exec -T hpcc bash -c "cd /workspace/simulation && rm -f queue_depth.csv && ./run.sh /workspace/results/study_cases/<case>/config/<config>.txt"

# Generate all plots for a case
python3 results/run_all_plots.py --base-dir results/study_cases/<case>/

# Check if simulation is done
ls results/data/
```

---

## Important Config Flags

All case configs must include `INT_PER_PACKET 1` to trigger `queue_depth.csv` output. This has already been added to cases 0–6.

Cases 5 and 6 had a **duplicate `INT_PER_PACKET 1` line** accidentally added — verify and remove the duplicate before running if needed.

---

## Bug Fixes Applied This Session

1. **`run_all_plots.py` file discovery** — fixed to include `.tr` and `.csv` files (not just `.txt`)
2. **`switch_throughput` timeout** — increased from 300s→900s (1.2GB trace files take longer)
3. **`INT_PER_PACKET 1`** — added to all case configs to enable `queue_depth.csv` output

---

## File Structure Reference

| Path | Purpose |
|:--|:--|
| `results/run_all_plots.py` | Master plotting script. Use `--base-dir` for case-specific run |
| `results/scripts/` | Individual plotting scripts |
| `results/study_cases/caseN_*/data/` | Data files for case N |
| `results/study_cases/caseN_*/plots/` | Static PNG plots |
| `results/study_cases/caseN_*/interactive_plots/` | Interactive HTML plots |
| `results/data/` | Staging area — data here after sim, then moved to case dir |
| `simulation/src/point-to-point/model/rdma-hw.cc` | Main CC algorithm |
| `HPCC_PLUS_README.md` | Algorithm documentation |
