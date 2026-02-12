# TS-HPCC-Plus: Implementation Summary

This document summarizes the changes, logic, and configuration for the **HPCC-Plus** (Case 2) and **TS-HPCC-Plus** (Case 3) implementations. It is intended to guide future developers and agents working on this codebase.

## 1. Overview
The goal of this project was to extend the HPCC (High Precision Congestion Control) simulation to support **HPCC-Plus**, a variant that incorporates host-side congestion feedback (using `RX_PULL_RATE` as a proxy for host processing capacity).

We introduced two distinct modes:
1.  **HPCC-Plus (Case 2)**: The baseline implementation where the sender reacts to both switch congestion (INT) and host congestion (Packet delivery rate vs. Callibrated Host Capacity).
2.  **TS-HPCC-Plus (Case 3)**: A "Traffic-Sensitive" variant that only reacts to host congestion signals if a queue is actually building at the receiver. This prevents false positives when the link is underutilized due to application-limited traffic.

## 2. Implementation Details

### Shared Infrastructure
*   **Packet Header**: Modified `IntHeader` to carry queue length and timestamps for the destination (host) hop.
*   **Receiver Logic**: `RdmaHw::ReceiveAck` now dispatches to specific handlers based on `m_cc_mode`.
*   **Rate Shaper**: `RdmaHw` includes logic to pace packets based on `m_rxPullRate`.

### Case 2: HPCC-Plus (`CC_MODE 11`)
**Algorithm**:
The sender calculates utilzation $u$ as the maximum of the bottleneck switch utilization ($u_{switch}$) and the host utilization ($u_{host}$).
$$ u = \max(u_{switch}, u_{host}) $$

$u_{host}$ is calculated as:
$$ u_{host} = \frac{R}{C_{max}} + \frac{q_{host}}{C_{host} \times BaseRTT} $$
*   $R$: Current sending rate (or delivered rate).
*   $C_{max}$: Physical link bandwidth (used for the utilization term to allow probing).
*   $q_{host}$: Queue length at the receiver NIC.
*   $C_{host}$: Estimated host capacity (EWMA of delivered rate).

**Critical Fixes Applied**:
1.  **Probing Deadlock**: Originally, $u_{host}$ used $C_{host}$ in the denominator ($R/C_{host}$). If the receiver throttled traffic (e.g., `RxPullRate=0.1`), $C_{host}$ would converge to $0.1 \times LineRate$. Thus $u_{host} \approx 1.0$, preventing the sender from ever increasing its rate to probe for more bandwidth.
    *   **Fix**: We use physical Line Rate ($C_{max}$) for the utilization term ($R/C_{max}$), ensuring $u_{host} < 1.0$ when underutilized, allowing Additive Increase.
2.  **Fast React Double-Jeopardy**: `FastReact` updates rate on every ACK. If $u > 1$ (congestion), the rate would be divided by $u$ on *every packet*, causing exponential collapse.
    *   **Fix**: Capacity estimation and base rate updates happen only once per RTT. `FastReact` only adjusts the immediate pacing rate, not the state variables.

**Code Reference**: `RdmaHw::UpdateRateHpPlus` in `rdma-hw.cc`.

### Case 3: TS-HPCC-Plus (`CC_MODE 12`)
**Goal**: Solve the "Phantom Congestion" problem where low throughput (due to application limit or pacing) is misinterpreted as congestion because $R \approx C_{host}$.

**Algorithm (Q-Only)**:
We act similarly to Case 2, but we **gate the host congestion signal on queue length**.
1.  **Always Track Capacity**: $C_{host}$ is updated via EWMA on every RTT, keeping it accurate.
2.  **Conditional Reaction**:
    *   **If $q_{host} > 0$**:
        $$ u_{host} = 1.0 + \frac{q_{host}}{C_{host} \times BaseRTT} $$
        (We force $u_{host} \ge 1.0$ to signal immediate congestion).
    *   **If $q_{host} == 0$**:
        $$ u_{host} = 0 $$
        (Ignore host signal completely; rely only on switch feedback).

**Rationale**: If the queue is empty, any "slow" rate is just the receiver being slow, not network congestion. We shouldn't reduce our sending rate further. If the queue builds, we are sending faster than the receiver can consume, so we immediately signal congestion.

**Code Reference**: `RdmaHw::UpdateRateHpPlusQOnly` in `rdma-hw.cc`.

## 3. Configuration & Running

### Configuration Files
Located in `simulation/mix/configs/` (global) or `results/study_cases/<case>/config/` (local).

| Parameter | Value | Description |
| :--- | :--- | :--- |
| `CC_MODE` | `11` | Enable HPCC-Plus logic (Case 2) |
| `CC_MODE` | `12` | Enable TS-HPCC-Plus logic (Case 3) |
| `RX_PULL_RATE_SCHEDULE` | `<node> <cnt> <t1> <r1>...` | Defines dynamic pulling rate changes |
| `FAST_REACT` | `1` | Enable per-ACK reaction (Recommended) |
| `SAMPLE_FEEDBACK` | `0` | Disable sampling (React to all ACKs for precision) |

### Running Simulations
Use the `run_all_plots.py` script. It has been patched to support:
1.  `--base-dir`: Running from a specific study case folder.
2.  **Robust Path Finding**: Automatically locates `config` and `topology` files in `config/`, `configs/`, or the global `simulation` directory.
3.  **Vertical Lines**: Draws `RX_PULL_RATE` transitions on plots if defined in config.

**Example Commands**:
```bash
# Run Case 2 (HPCC-Plus)
python3 results/run_all_plots.py --base-dir results/study_cases/case2_dynamic_pulling_rate_HPCC_Plus

# Run Case 3 (TS-HPCC-Plus)
python3 results/run_all_plots.py --base-dir results/study_cases/case3_TS_HPCC_Plus
```

## 4. Plotting & Verification
The plotting suite (`results/scripts/`) generates:
*   `cwnd_rtt_analysis_*.png`: CWND, Rate, and RTT over time.
    *   *Look for*: Rate matching the `RX_PULL_RATE` steps (vertical lines).
*   `rx_buffer_*.png`: Receiver buffer occupancy.
    *   *Look for*: Buffer spikes corresponding to rate mismatches.
*   `switch_throughput_*.png`: Aggregate throughput at the switch.
*   `dashboard_*.png`: All-in-one view.

**Verification Checklist**:
1.  **Stable Rate**: Rate should converge to the target `RX_PULL_RATE` (e.g., 0.5, 1.0).
2.  **No Collapse**: Rate should not drop to zero during transitions.
3.  **Queue Draining**: Queues should drain when rate allowance increases.
4.  **Lines**: Vertical dashed lines should appear at schedule times ($t=1.0s, 1.2s, ...$).
