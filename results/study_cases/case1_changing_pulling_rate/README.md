# Study Case 1: Changing Pulling Rate (Dynamic Pull)

This directory contains a complete snapshot of the "Changing Pulling Rate" simulation study.

## Overview

In this experiment, we analyze the behavior of the High Precision Congestion Control (HPCC) algorithm under varying pulling rates. The simulation involves two senders and a dynamic pulling rate schedule.

## Contents

-   **`config/`**: Configuration files used for the simulation.
    -   `config_dynamic_pull.txt`: Main simulation parameters.
    -   `topology_two_senders.txt`: Network topology.
    -   `flow_two_senders_long.txt`: Flow traffic pattern.
-   **`data/`**: Raw simulation output data.
    -   `cwnd_dynamic_pull.txt`: Congestion Window and Rate logs.
    -   `fct_dynamic_pull.txt`: Flow Completion Times.
    -   `qlen_dynamic_pull.txt`: Queue length samples.
    -   `rxbuf_dynamic_pull.txt`: RX Buffer occupancy.
    -   `mix_dynamic_pull.tr`: Binary trace file for switch throughput.
    -   `queue_depth.csv`: INT queue depth data.
-   **`plots/`**: Static plots generated from the data.
    -   `dashboard_dynamic_pull.png`: Comprehensive summary dashboard.
    -   `fct_dynamic_pull.png`: Flow Completion Time analysis.
    -   `switch_throughput_mix_dynamic_pull.png`: Switch throughput over time.
    -   `rx_buffer_dynamic_pull.png`: RX Buffer occupancy.
    -   `switch_queue_depth_cdf.png`: Queue depth CDF.
-   **`interactive_plots/`**: Interactive HTML dashboards.
    -   `cwnd_rtt_analysis.html`: **Rate, Window, and RTT Analysis**. Features independent plotting, rangesliders, and a "Lock Time Scale" synchronization toggle.
    -   `rx_buffer.html`: Interactive RX Buffer plot.
    -   `switch_throughput.html`: Interactive Switch Throughput plot.
    -   `fct.html`: Interactive Flow Completion Time plot.
    -   `queue_depth.html`: Interactive Queue Depth plot.
-   **`scripts/`**: Copy of the Python plotting scripts used to generate these results.

## How to Run

To regenerate the plots using the included scripts and data:

```bash
# Navigate to the results directory
cd ../..

# Run the master plotting script (pointing to the original paths or modifying the script to point here)
python3 run_all_plots.py
```

## Key Findings

-   The **CWND/RTT Analysis** dashboard highlights the correlation between rate adjustments and RTT variations.
-   The **Lock Time Scale** feature allows for precise temporal correlation between the Rate, Window, and RTT metrics.
