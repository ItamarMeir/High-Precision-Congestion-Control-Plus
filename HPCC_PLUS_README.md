# HPCC_Plus: Enhanced High Precision Congestion Control

## Overview

HPCC_Plus extends the HPCC algorithm to handle **host-side congestion** by treating the receiver as a virtual switch hop. The receiver inserts its own INT telemetry (timestamp, cumulative RxBytes, RX queue length, line rate) into each packet, which the sender processes alongside switch INT hops.

## Key Differences from HPCC

| | Standard HPCC | HPCC+ (CC_MODE 11) | TS-HPCC+ (CC_MODE 12) |
|:--|:--|:--|:--|
| **INT Hops** | Switch hops only | Switch hops + Host hop | Switch hops + Host hop |
| **Host Capacity** | N/A | Conditional EWMA ($C_{host}$) | Conditional EWMA ($C_{host}$) |
| **Host Utilization** | N/A | Always computed | Only when RX queue > 0 |

## Algorithm Details

### 1. Receiver-Side: Host INT Insertion

When a data packet arrives at the receiver NIC and an ACK is generated (in `ReceiveUdp`), the receiver pushes a **host INT hop** onto the packet's INT header before copying it to the ACK:

```
PushHop(timestamp, m_rxBytesTotal[nic], rxQueueLength, lineRate)
```

- **`m_rxBytesTotal`**: Cumulative bytes pulled from the RX buffer (analogous to switch `m_txBytes`)
- **`rxQueueLength`**: Current RX ingress buffer occupancy
- **`lineRate`**: Physical NIC rate

This makes the receiver behave identically to a switch from the INT perspective.

### 2. Sender-Side: R_delivered from INT Deltas

The sender computes `R_delivered` from the host hop using the standard INT delta mechanism — identical to how it computes switch throughput:

$$ R_{delivered} = \frac{\Delta RxBytes \times 8}{\Delta Timestamp} $$

Where $\Delta RxBytes$ and $\Delta Timestamp$ are computed from two adjacent ACKs using `GetBytesDelta()` and `GetTimeDelta()` with wrap-around handling.

### 3. Conditional C_host Estimation

$C_{host}$ is estimated via EWMA, but **only updated when evidence is reliable**:

```
if (rxQlen > 0):
    C_host = (1 - g) × C_host + g × R_delivered    // Queue → R_delivered ≈ true capacity
else if (R_delivered > C_host):
    C_host = (1 - g) × C_host + g × R_delivered    // Higher rate observed
else:
    C_host unchanged                                 // Don't underestimate
```

**Why conditional?** When the sender sends below receiver capacity, `R_delivered` is limited by the sender, not the receiver. Unconditionally updating `C_host` would create a probing deadlock where `R_delivered ≈ C_host ≈ 1.0`, preventing rate increase.

**Initialization**: $C_{host}$ starts at the physical line rate and converges down as measurements arrive.

### 4. Host Utilization

**HPCC+ (CC_MODE 11)** — always considers the host hop:

$$ u_{host} = \frac{R_{delivered}}{C_{host}} + \frac{qlen}{C_{host} \times BaseRTT} $$

**TS-HPCC+ (CC_MODE 12)** — only reacts to host congestion when queue builds:

$$ u_{host} = \frac{R_{delivered}}{C_{host}} + \frac{qlen}{C_{host} \times BaseRTT} \quad \text{(only if } qlen > 0\text{)} $$

Both terms use $C_{host}$ as the capacity reference.

### 5. Rate Adjustment

The maximum utilization across all hops determines the new rate:

$$ U_{max} = \max(u_{switch\_ewma}, u_{host}) $$
$$ R_{new} = \frac{R_{current}}{U_{max} / \eta} + R_{AI} $$

Where $\eta$ is the target utilization (e.g., 0.95).

### 6. Fast React

When `FAST_REACT` is enabled, the sender adjusts its pacing rate on **every ACK** (intermediate packets) but only commits state changes (C_host, incStage, curRate, lastUpdateSeq) during **full RTT updates**.

## Implementation

### Files Modified
- **`rdma-hw.h`**: Added `m_rxBytesTotal` (per-NIC cumulative RX bytes for host INT)
- **`rdma-hw.cc`**:
  - `ReceiveUdp`: Pushes host INT hop before ACK generation
  - `HandleAckHpPlus`: Fixed dead-code bug, dispatches CC_MODE 12 → `UpdateRateHpPlusQOnly`
  - `UpdateRateHpPlus`: INT-based R_delivered + conditional C_host
  - `UpdateRateHpPlusQOnly`: Same, but host hop ignored when qlen == 0
  - `FastReactHpPlus`: Dispatches to correct function per CC_MODE
  - `AddQueuePair` / `ReceiveCnp`: Init CC_MODE 12 state
- **`switch-node.cc`**: CC_MODE 12 added to INT insertion condition

## Running

**CC_MODE 11** (HPCC+):
```
CC_MODE 11
```

**CC_MODE 12** (TS-HPCC+):
```
CC_MODE 12
```

**Key Parameters**:
- `EWMA_GAIN`: Controls C_host convergence speed
- `RX_PULL_RATE` / `RX_PULL_RATE_SCHEDULE`: Simulates dynamic receiver throttling
- `MI_THRESH`: Multiplicative increase threshold
- `FAST_REACT`: Enable per-ACK fast reaction
