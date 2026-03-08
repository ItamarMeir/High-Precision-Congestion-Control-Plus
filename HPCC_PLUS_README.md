# HPCC+ (CC_MODE 11): Enhanced High Precision Congestion Control

## Overview

HPCC+ extends the original [HPCC algorithm](https://dl.acm.org/doi/10.1145/3341302.3342085) by adding **receiver-side congestion awareness**. In standard HPCC, only switches insert telemetry (INT hops) into packets. HPCC+ additionally treats the **receiver NIC's ingress queue** as a virtual switch hop, allowing the sender to detect and react to congestion at the receiver — not just at intermediate switches.

This is important in scenarios where the **receiver's pulling rate** is throttled (e.g., CPU-limited, software processing backpressure), causing a queue to build at the receiver NIC even while the network path is idle.

---

## Background: Standard HPCC

In HPCC, each switch stamps a packet with an **INT hop** containing:
- **Timestamp** (`ts`): when the packet was forwarded
- **Tx bytes** (`txBytes`): cumulative bytes sent out this port
- **Queue length** (`qlen`): current egress queue depth in bytes
- **Line rate** (`lineRate`): link capacity in bps

The sender uses deltas between two consecutive INT hops (from subsequent ACKs) to compute the **link utilization** at each switch:

$$u_{switch} = \underbrace{\frac{\Delta txBytes \times 8}{\Delta ts \times C_{link}}}_{\text{throughput term}} + \underbrace{\frac{\min(qlen_{t}, qlen_{t-1}) \times 8}{C_{link} \times BaseRTT}}_{\text{queue term}}$$

Where:
- $\Delta txBytes$ = bytes forwarded between the two ACK instants (bytes)
- $\Delta ts$ = time between the two ACK instants (nanoseconds)
- $C_{link}$ = switch port line rate (bps)
- $qlen$ = egress queue depth at the switch (bytes)
- $BaseRTT$ = estimated base round-trip time (nanoseconds)

The sender takes the **maximum** utilization across all switch hops, and applies an EWMA (exponentially weighted moving average) to smooth it. The target utilization $\eta$ (default 0.95) is used as the pacing goal.

---

## HPCC+: What Is Added

HPCC+ adds a **host INT hop** — inserted by the **receiver** — as the last element in the INT hop list. This allows the sender to detect congestion at the receiver's NIC ingress buffer using the same framework as switch hops.

### Key differences from standard HPCC

| Feature | Standard HPCC | HPCC+ (CC_MODE 11) |
|:--|:--|:--|
| **INT insertion** | Switches only | Switches + Receiver NIC |
| **Bottleneck detection** | Switch queues / links | Switch queues + Receiver ingress queue |
| **Receiver capacity** | Not modelled | Receiver's physical line rate (from INT hop) |
| **Host utilization** | Not computed | $u_{host}$: conditional on receiver queue depth (see Step 5) |
| **Fairness mechanism** | Shared switch line rate denominator | Same — shared NIC line rate denominator |

---

## Algorithm: Step-by-Step

### Step 1 — Receiver Inserts a Host INT Hop

When a data packet arrives at the receiver and triggers an ACK (`ReceiveUdp()`), before the ACK is created, the receiver calls:

```cpp
ih.PushHop(
    Simulator::Now().GetTimeStep(),   // timestamp (ns)
    m_rxBytesTotal[nic_idx],          // cumulative bytes dequeued from RX buffer
    rxQlen,                           // current RX ingress queue depth (bytes)
    dev->GetDataRate().GetBitRate()   // NIC line rate (bps)
);
```

This mirrors exactly what a switch does, using the receiver's own NIC as the "port":
- **`m_rxBytesTotal`** accumulates every byte dequeued from the NIC RX ingress queue by the receiver pull path. This is an **aggregate counter shared across all flows** on that NIC.
- **`rxQlen`** reflects how many bytes are currently sitting in the RX ingress buffer waiting to be processed.

The INT hop list now has: `[switch_0, switch_1, ..., switch_N−1, host]`

---

### Step 2 — Sender Bootstraps on First RTT

On the **first ACK** received for a flow (`m_lastUpdateSeq == 0`), the sender simply stores the INT hops as a baseline and returns without computing rates. The deltas are only meaningful between two consecutive measurements.

---

### Step 3 — Sender Processes Switch Hops (Standard HPCC)

For hops `0` to `nhop - 2` (all except the last), the sender computes per-hop utilization using the standard HPCC INT delta mechanism:

$$\tau_i = ts_i^{new} - ts_i^{old} \quad \text{(time since last measurement at hop } i \text{, ns)}$$

$$txRate_i = \frac{(txBytes_i^{new} - txBytes_i^{old}) \times 8}{\tau_i \times 10^{-9}} \quad \text{(bps)}$$

$$u_i = \frac{txRate_i}{C_{link,i}} + \frac{\min(qlen_i^{new}, qlen_i^{old}) \times 8}{C_{link,i} \times BaseRTT \times 10^{-9}}$$

The **bottleneck utilization** $U$ is the maximum across all switch hops, and the EWMA-smoothed aggregate $\hat{u}_{switch}$ is updated:

$$\hat{u}_{switch} \leftarrow \frac{\hat{u}_{switch} \cdot (BaseRTT - \tau_{max}) + U \cdot \tau_{max}}{BaseRTT}$$

Where $\tau_{max}$ is the time interval at the bottleneck hop (capped at $BaseRTT$).

---

### Step 4 — Sender Processes the Host Hop

The last INT hop (index `nhop - 1`) is the **receiver's host hop**. Processing mirrors switch hops but uses receiver-specific notation:

$$\tau_{host} = ts_{host}^{new} - ts_{host}^{old}$$

$$R_{delivered} = \frac{(rxBytes^{new} - rxBytes^{old}) \times 8}{\tau_{host} \times 10^{-9}} \quad \text{(bps)}$$

> **Term: $R_{delivered}$** — The rate at which the receiver is actually *pulling* data from its ingress buffer. This represents how fast the host (CPU/application) is consuming arriving data. If the application is slow, $R_{delivered}$ will be low even on an uncongested network.

$$qlen_{rx} = \min(qlen_{host}^{new}, qlen_{host}^{old}) \times 8 \quad \text{(bits)}$$

---

### Step 5 — Compute Host Utilization

For the host hop, HPCC+ uses an **estimated host capacity ($C_{host}$)** instead of the raw physical line rate. $C_{host}$ is dynamically tracked using an Exponentially Weighted Moving Average (EWMA) of the actual delivered rate ($R_{delivered}$).

The $C_{host}$ update logic is conditional:
1. If the receiver queue is non-empty (`rxQlen > 0`), the receiver is actively bottlenecked, so $C_{host}$ tracks $R_{delivered}$ via EWMA.
2. If there is no queue (`rxQlen == 0`), the receiver is completely keeping up with the arrival rate (uncongested). 
   - If $R_{delivered} > C_{host}$, $C_{host}$ rapidly jumps up via EWMA.
   - Otherwise, the sender **Additively Increases** **$C_{host}$** by reusing the rate flow's AI step ($R_{AI}$) up to a strict maximum of the physical line rate.

$$C_{host} \leftarrow \begin{cases}
(1 - g) \cdot C_{host} + g \cdot R_{delivered} & \text{if } qlen_{rx} > 0 \text{ or } R_{delivered} > C_{host} \\
\min(C_{host} + R_{AI}, \ C_{link,host}) & \text{otherwise}
\end{cases}$$

Once $C_{host}$ is estimating the bottleneck, the host utilization $u_{host}$ is computed:

$$u_{host} = \begin{cases}
1 + \dfrac{qlen_{rx}}{C_{host} \times BaseRTT \times 10^{-9}} & \text{if } qlen_{rx} > 0 \\
\dfrac{R_{delivered}}{C_{host}} & \text{if } qlen_{rx} = 0
\end{cases}$$

**Why use an estimated $C_{host}$ instead of Line Rate?**

If a receiver is bottlenecked by software/CPU, its *effective* pull rate can be much lower than the physical NIC line rate (e.g., pulling at 1 Gbps on a 10 Gbps link). By tracking the actual delivered rate, multiple senders share the same aggregate $C_{host}$ estimate and divide their rates by it. This ensures fair competitive pressure: $u_{host}$ will increase for all flows when data arrives faster than it is consumed, naturally forcing flows to converge to equal shares of the actual pull rate.

When the application speeds back up (e.g., recovers to 10 Gbps capability), the queue instantly drains to 0. Because there is no queue, the Additive Increase rules kick in: $C_{host}$ gracefully climbs back towards line capacity. This causes $u_{host}$ to drop, safely signaling the senders to probe upwards and automatically fill the restored bandwidth without causing a Multiplicative Increase queue spike.

---

### Step 6 — Rate Adjustment

The final utilization is the maximum across all hops (switches + host):

$$U_{max} = \max(\hat{u}_{switch}, \ u_{host})$$

The normalized congestion factor is:

$$U_{norm} = \frac{U_{max}}{\eta}$$

Where $\eta$ = `U_TARGET` (default 0.95, the target utilization).

The new sending rate is then computed using the HPCC formula:

$$R_{new} = \frac{R_{current}}{U_{norm}} + R_{AI}$$

Where $R_{AI}$ = `RATE_AI` is the additive increase step (e.g., 5 Mb/s).

**Multiplicative vs. Additive Increase**:
- If $U_{norm} \geq 1$ (congested) OR `incStage` ≥ `MI_THRESH`: use the above formula (multiplicative decrease + AI).
- Otherwise (light load, early stages): pure additive increase: $R_{new} = R_{current} + R_{AI}$.

**The `incStage` counter** increments on each AI update and resets on any multiplicative update. Once it exceeds `MI_THRESH`, it switches to multiplicative mode — this accelerates convergence in the low-utilization regime.

Finally, $R_{new}$ is clamped to $[R_{min}, R_{max}]$.

---

### Step 7 — Fast React

When `FAST_REACT = 1` (enabled), the sender calls `UpdateRateHpPlus()` on **every ACK** rather than only once per RTT. However:

- **Fast react ACKs** (`fast_react = true`): rate is updated but `m_curRate`, `m_lastUpdateSeq`, and `m_incStage` are **not committed**. The sender paces faster/slower temporarily without permanently changing its reference state.
- **Full RTT ACKs** (`fast_react = false`): all state is permanently updated.

This allows sub-RTT responsiveness while keeping full-RTT state stable.

---

## INT Hop Layout

```
[ switch_0 | switch_1 | ... | switch_N-1 | host ]
      ↑                                      ↑
  standard HPCC INT hops             added by HPCC+
  (inserted by switches)          (inserted by receiver)
```

The host hop is always the **last** element (`index nhop - 1`). The sender detects it by position, not by type — all hops use the same `IntHop` structure.

---

## Smoothing Modes

HPCC+ applies **three distinct smoothing mechanisms** to reduce estimation noise and improve rate stability. Understanding these is important for tuning behavior.

### 1 — Per-Hop baseRTT Rolling Average (Switch Hops)

For each switch hop, the instantaneous utilization $u_i$ is not used directly. Instead it is blended into a running estimate proportional to how much of the baseRTT the measurement window represents:

$$\hat{u}_i \leftarrow \frac{\hat{u}_i \cdot (BaseRTT - \tau_i) + u_i \cdot \tau_i}{BaseRTT}$$

Where $\tau_i$ is the measurement window (capped at $BaseRTT$). This is **self-normalizing**: a larger measurement window gets more weight, so timing jitter in ACK arrival does not distort the utilization estimate.

**In MULTI_RATE=0 (aggregate mode):** This rolling average is applied **once globally** using the bottleneck hop's tau. All switch hops compete for the global maximum, and only the winner feeds into the single global $\hat{u}_{switch}$.

**In MULTI_RATE=1 (per-hop mode):** Each hop maintains its **own independent** rolling-average $\hat{u}_i$, updated with its own $\tau_i$. The minimum across per-hop rates becomes the final rate.

This smoothing is **fixed and not configurable**.

---

### 2 — R_delivered Pre-Smoothing EWMA (Host Hop, Configurable)

The host hop's raw $R_{delivered}$ measurement is highly sensitive to timing jitter because it is computed as a byte-delta over a variable time window — the same Taylor-series sensitivity as switch hops, but **without** the baseRTT rolling average applied automatically.

A configurable pre-smoothing EWMA is applied before $R_{delivered}$ reaches any other calculation:

$$\hat{R}_{delivered} \leftarrow (1 - g_R) \cdot \hat{R}_{delivered} + g_R \cdot R_{delivered}^{raw}$$

The smoothed $\hat{R}_{delivered}$ is then used in place of the raw value for all downstream calculations (Step 5 above).

| Config Key | Parameter | Default | Meaning |
|:--|:--|:--|:--|
| `R_DELIVERED_GAIN` | $g_R$ | `1.0` | `1.0` = no smoothing (instantaneous); lower = stronger smoothing |

**Effect:** Reduces the frame-to-frame noise in the $R_{delivered}$ metric, which in turn reduces noise propagated into $C_{host}$ and $u_{host}$.

---

### 3 — C_host Tracking EWMA (Host Hop, Configurable)

The estimated host capacity $C_{host}$ is updated each full RTT using an EWMA of $\hat{R}_{delivered}$ (or applying additive increase when uncongested — see Step 5):

$$C_{host} \leftarrow (1 - g) \cdot C_{host} + g \cdot \hat{R}_{delivered}$$

This controls how quickly $C_{host}$ tracks changes in the receiver's actual pull rate.

| Config Key | Parameter | Default | Meaning |
|:--|:--|:--|:--|
| `EWMA_GAIN` | $g$ | `1.0/16` | Higher = faster tracking, more noisy; lower = smoother, slower reaction |

---

### Smoothing Interaction by Mode

| Smoothing | Switch Hops | Host Hop (`MULTI_RATE=0`) | Host Hop (`MULTI_RATE=1`) |
|:--|:--|:--|:--|
| baseRTT rolling avg | ✓ (per-hop) | ✓ (global, after max selection) | ✓ (per-hop, before rate computation) |
| R_delivered pre-EWMA | — | ✓ (`R_DELIVERED_GAIN`) | ✓ (`R_DELIVERED_GAIN`) |
| C_host EWMA | — | ✓ (`EWMA_GAIN`) | ✓ (`EWMA_GAIN`) |

> **Note:** In `MULTI_RATE=0`, the host hop competes directly against switch hops for the global maximum **after** the R_delivered pre-EWMA is applied but **before** the global baseRTT rolling average. This means the host hop effectively gets two smoothing passes (pre-EWMA + global rolling avg) while switch hops only get one. For symmetric smoothing behavior, prefer `MULTI_RATE=1`.

---

## Configuration Parameters

| Parameter | Config Key | Default | Description |
|:--|:--|:--|:--|
| CC mode | `CC_MODE` | — | Set to `11` for HPCC+ |
| INT hops | `INT_MULTI` | `1` | Number of **switch** hops. In HPCC+ mode, the simulator automatically adds 1 extra slot for the host hop. |
| Target utilization | `U_TARGET` | `0.95` | $\eta$: pacing target, fraction of link capacity |
| Additive increase | `RATE_AI` | `5Mb/s` | $R_{AI}$: rate increase step per RTT |
| Hyper AI | `RATE_HAI` | `10Mb/s` | Rate step during hyper-AI phase |
| MI threshold | `MI_THRESH` | `5` | AI stages before switching to multiplicative mode |
| Fast react | `FAST_REACT` | `1` | `1` = react per ACK, `0` = react per RTT only |
| Sample feedback | `SAMPLE_FEEDBACK` | `0` | `1` = skip hops with zero queue during fast react |
| Multiple rates | `MULTI_RATE` | `1` | `1` = per-hop rates (recommended), `0` = aggregate single rate |
| RX pull mode | `RX_PULL_MODE` | `1` | `0` = immediate drain, `1` = fixed-rate drain |
| RX pull rate | `RX_PULL_RATE` | `1.0` | Fraction of line rate for RX pull (in mode 1) |
| C_host tracking gain | `EWMA_GAIN` | `1/16` | EWMA gain $g$ for $C_{host}$ updates (higher = faster, nosier) |
| R_delivered smoothing | `R_DELIVERED_GAIN` | `1.0` | Pre-smoothing EWMA gain $g_R$ on raw $R_{delivered}$ (`1.0` = off) |



## Files Modified

| File | Change |
|:--|:--|
| `rdma-hw.h` | Added `m_rxBytesTotal` vector (per-NIC cumulative RX-buffer dequeued bytes) |
| `rdma-hw.cc` — `ReceiveUdp()` | Pushes host INT hop before generating ACK |
| `rdma-hw.cc` — `UpdateRateHpPlus()` | Implements Steps 3–7 above; computes $R_{delivered}$ from host INT deltas and maintains an estimated $C_{host}$ |
| `rdma-hw.cc` — `HandleAckHpPlus()` | Dispatches to full-RTT or fast-react update |
| `rdma-hw.cc` — `FastReactHpPlus()` | Calls `UpdateRateHpPlus()` with `fast_react=true` |
| `rdma-hw.cc` — `AddQueuePair()` | Initializes `hpccPlus.m_curRate` to line rate |
| `scratch/third.cc` — setup | For CC_MODE 11: auto-increments `int_multi` by 1 (host hop slot) and sets `IntHeader::mode = NORMAL` |
| `switch-node.cc` — `SwitchNotifyDequeue()` | Includes CC_MODE 11 in INT insertion condition |
