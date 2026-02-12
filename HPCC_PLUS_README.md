# HPCC_Plus: Enhanced High Precision Congestion Control

## Overview

HPCC_Plus is an extension of the High Precision Congestion Control (HPCC) algorithm, designed to improve performance in environments with significant host-side congestion or specific receiver constraints. It leverages In-band Network Telemetry (INT) to obtain precise link utilization feedback, similar to HPCC, but introduces a specialized mechanism for the last hop (Host INT) to better handle receiver-side limitations.

## Key Differences from HPCC

The standard HPCC algorithm treats all hops (switches and the final link to the host) uniformly, using the link utilization ($U$) and queue length ($q$) to calculate a congestion signal.

**HPCC_Plus** differentiates the **last hop** (the path from the ToR switch to the destination host) from the rest of the network fabric. It introduces a **Pulling Rate** based estimation for the host's capacity, which is useful when the bottleneck is at the receiver's processing capability or a specific "pull" mechanism (like in some RDMA implementations or storage systems).

## Algorithm Details

### 1. Host Capacity Estimation ($C_{host}$)
Instead of assuming a static link capacity for the receiver, HPCC_Plus estimates the effective "Pulling Rate" of the receiver using an Exponential Weighted Moving Average (EWMA) of the **delivered rate**.

$$ C_{host} = (1 - g) \times C_{host_{prev}} + g \times R_{delivered} $$

Where:
- $g$ is the EWMA gain (configured via `EWMA_GAIN`, default 0.99 in `config_hpcc_plus`).
- $R_{delivered}$ is the rate measured over the last RTT:
  $$ R_{delivered} = \frac{\Delta Bytes_{acked}}{BaseRTT} $$

*Note: This update only happens once per RTT (when `!fast_react`) to ensure stability.*

### 2. Enhanced Congestion Signal ($u_{host}$)
For the last hop (Host INT), the normalized congestion signal $u$ uses a **Dual-Capacity Approach**:

1.  **Throughput Term**: Uses **Line Rate** ($C_{max}$) as the capacity. This allows the sender to probe for available bandwidth up to the physical link speed.
2.  **Queue Term**: Uses **Estimated Capacity** ($C_{host}$) as the capacity. This makes the queue signal sensitive to the receiver's actual processing speed (e.g., if the receiver pulls slowly, a small queue builds up fast in relative terms).

$$ u_{host} = \frac{R_{delivered}}{C_{max}} + \frac{qlen}{C_{host} \times BaseRTT} $$

### 3. Fast React Mechanism
HPCC_Plus enables `FAST_REACT`, which allows the pacer to adjust its rate on **every ACK** to handle transient congestion immediately, while maintaining stable control state.

- **Per-Packet (Fast React)**:
    - Calculates $u$ and determines the target rate.
    - Immediately updates the hardware Pacing Rate.
    - **Does NOT** update the protocol's internal `m_curRate` anchor or `incStage`.
- **Per-RTT (Full Update)**:
    - Updates $C_{host}$ estimation.
    - Commit the new rate to `m_curRate`.
    - Updates `incStage` (Additive Increase counter).

This hybrid approach provides the responsiveness of per-packet reaction with the stability of RTT-based control loops.

For all other hops (switches), the standard HPCC formula is used:
$$ u_{switch} = \frac{R_{tx}}{C_{link}} + \frac{qlen}{C_{link} \times BaseRTT} $$

### 4. Rate Adjustment
The maximum $u$ ($U_{max}$) along the path is used to adjust the sending rate:
$$ R_{new} = \frac{R_{current}}{U_{max} / U_{target}} + R_{ai} $$

Where $U_{target}$ is the target utilization (e.g., 0.95).

## Implementation

The implementation is integrated into the ns-3 simulation framework, specifically within the `point-to-point` module's RDMA model.

### Files Modified
- **`rdma-queue-pair.h`**: Added `hpccPlus` struct to `RdmaQueuePair` to track `m_c_host`, `m_curRate`, and other HPCC-Plus state.
- **`rdma-hw.h`**: Added `HandleAckHpPlus`, `UpdateRateHpPlus`, and `FastReactHpPlus` method declarations.
- **`rdma-hw.cc`**: 
    - Implemented `UpdateRateHpPlus` which iterates through INT hops.
    - Differentiates the last hop (`i == nhop - 1`) to apply the HPCC_Plus logic.
    - Updates `C_host` and calculates `u_host`.
- **`switch-node.cc`**: Updated to ensure `CC_MODE 11` enables INT header insertion (same as standard HPCC).
- **`run.py` / Configs**: Added `CC_MODE 11` support.

## Running HPCC_Plus

To run a simulation with HPCC_Plus:

1.  **Configuration**: Use a config file with `CC_MODE 11`.
    ```
    CC_MODE 11
    ```
2.  **Parameters**:
    - `EWMA_GAIN`: Controls stability of host capacity estimation.
    - `RX_PULL_RATE`: Can be configured to simulate dynamic receiver throttling.

### Example Command
```bash
./build/scratch/third mix/configs/config_hpcc_plus_dynamic.txt
```
