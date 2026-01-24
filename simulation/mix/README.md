# mix workspace

This folder stores simulation inputs and outputs in a clean layout.

## Layout

```
mix/
├── configs/      # Simulation configs (commented)
├── inputs/       # Auxiliary inputs (trace node lists)
├── flows/        # Flow definition files
├── topologies/   # Topology files
└── outputs/      # Simulation outputs
    ├── fct/      # FCT files
    ├── pfc/      # PFC files
    ├── qlen/     # Queue length files
    ├── trace/    # Packet trace files (.tr)
    ├── cwnd/     # Rate/window trace files
    └── anim/     # NetAnim XML
```

## Run

```
cd simulation
./waf --run 'scratch/third mix/configs/config_two_senders.txt'
```

## Plot

```
python3 results/scripts/plot_dashboard.py simulation/mix
python3 results/scripts/plot_fct.py simulation/mix/outputs/fct/fct_two_senders.txt
python3 results/scripts/plot_qlen.py simulation/mix/outputs/qlen/qlen_two_senders.txt
python3 results/scripts/plot_cwnd.py simulation/mix/outputs/cwnd/cwnd_two_senders.txt
```
