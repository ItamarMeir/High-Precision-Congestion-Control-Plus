# HPCC Algorithm: Implementation Analysis

## 1. Overview

**High Precision Congestion Control (HPCC)** is a rate-based congestion control algorithm that utilizes **In-band Network Telemetry (INT)** to obtain precise link utilization feedback. Unlike traditional algorithms (DCTCP, DCQCN) that rely on binary signals (ECN) or queue length thresholds, HPCC calculates an exact "load factor" to adjust sending rates, aiming for zero-queue and high-utilization operation.

This document analyzes the **Standard HPCC** and **HPCC-PINT** implementation as found in the `simulation/` directory.

> [!NOTE]
> This codebase references "HPCC-Plus" extensions (e.g., end-host congestion models, `ecwnd`). Code analysis confirms these features are **not yet implemented** in the active simulation path. The description below covers the active Standard HPCC logic.

---

## 2. Core Control Logic

The implementation relies on **Rate-Based Control** as the primary mechanism, with the Congestion Window (CWND) acting as a secondary constraint.

### 2.1. Primary Control Variable: Rate ($R$)
The sending rate $R$ is directly updated upon receiving feedback (ACKs). The hardware is assumed to support rate limiting (pacing) at the sender.

#### Pacer Implementation Details
The pacer ensures the sender adheres to the calculated rate $R$ by enforcing an **Inter-Packet Gap (IPG)** between transmissions.
**How is the delay calculated?**
The delay is dynamic and depends on the **size of the packet** being sent. For every packet, the pacer calculates the time required to transmit that specific packet at the target rate $R$.

**Formula (Inter-Packet Gap):**
$$
\Delta T_{gap} = \frac{\text{PacketSize (bits)}}{R \text{ (bits/sec)}}
$$

**Code Snippet (`RdmaHw::ChangeRate`):**
```cpp
// simulation/src/point-to-point/model/rdma-hw.cc
// CalculateTxTime(bytes) = (bytes * 8) / BitRate
Time new_sendintTime = Seconds(new_rate.CalculateTxTime(qp->lastPktSize));
```
This ensures that even if packet sizes vary (e.g., MTU-sized data vs. small control packets), the *effective throughput* matches the target rate exactly.

### 2.2. Secondary Constraint: Window ($W$)
The window limits the number of bytes in flight. It acts as a safety net ($W \propto R$).

$$
W_{eff}(t) = W_{base} \times \frac{R(t)}{R_{max}}
$$

**Code Snippet (`RdmaQueuePair::GetWin`):**
```cpp
// simulation/src/point-to-point/model/rdma-queue-pair.cc
// GetWin() is what the utilization formula actually calls.
if (m_var_win){
    // Scale window by *current pacing rate* ratio
    w = m_win * m_rate.GetBitRate() / m_max_rate.GetBitRate();
} else {
    // Fixed window (BDP) — default when VarWin=false
    w = m_win;
}
```
> [!NOTE]
> `HpGetCurWin()` (uses `hp.m_curRate`) also exists and is used for window-bound checking during HPCC updates, but the utilization formula on line 930 calls `GetWin()` (uses `m_rate`).

---

## 3. Mathematical Model & Implementation

### 3.1. Feedback Signal: Link Utilization ($U$)

The INT header provides telemetry. The sender estimates utilization via two components: Throughput and Queue Size.

**Formula (Per-Hop Utilization $u_h$):**
$$
u_h = \frac{TxRate_h}{C_h} + \frac{qlen_h}{C_h \times T_{ramp}}
$$

**What is $T_{ramp}$?**
In this implementation, $T_{ramp}$ corresponds to the **Base RTT** ($RTT_{base}$).
*   Physically, $\frac{qlen_h}{C_h}$ is the queuing delay.
*   Dividing by $T_{ramp}$ normalizes this delay against the path's propagation delay.

**Code Snippet (`RdmaHw::UpdateRateHp`):**
```cpp
// simulation/src/point-to-point/model/rdma-hw.cc (line 929-930)

double txRate = (ih.hop[i].GetBytesDelta(qp->hp.hop[i])) * 8 / duration;

// Term 1: Throughput Utilization (TxRate / LineRate)
// Term 2: Queue Utilization. Uses std::min(current_qlen, prev_qlen) to reduce noise.
//         GetWin() = m_win when VarWin=false (default) = BDP = C * RTT_base
//         => term2 = min(Q_curr, Q_prev) / (C/MaxRate * Win) ≈ Q / (C * RTT_base)
double u = txRate / ih.hop[i].GetLineRate()
         + (double)std::min(ih.hop[i].GetQlen(), qp->hp.hop[i].GetQlen())
           * qp->m_max_rate.GetBitRate() / ih.hop[i].GetLineRate() / qp->GetWin();
```
> [!NOTE]
> The queue term uses `std::min(qlen_current, qlen_previous)` — a noise-reduction measure not explicitly stated in the original HPCC paper. It prevents overreacting to transient queue spikes.

### 3.1.1. TxRate Calculation
The `TxRate` is calculated by the receiver (or sender, based on INT data) using the delta of cumulative transmitted bytes and timestamps found in the INT header.

**Formula:**
$$
TxRate = \frac{(Bytes_1 - Bytes_0) \times 8}{Time_1 - Time_0}
$$
Where $1$ is the current packet and $0$ is the previous packet from the same flow. The implementation handles field wrap-around (20 bits for bytes, 24 bits for time).

### 3.1.2. INT Header Structure
The INT header contains per-hop telemetry data. Each hop inserts an `IntHop` structure:
*   **lineRate** (encoded): The link capacity.
*   **time** (24 bits): Timestamp.
*   **bytes** (20 bits): Cumulative transmitted bytes (scaled by `byteUnit=128`).
*   **qlen** (17 bits): Queue length (scaled by `qlenUnit=80`).

**Code Snippet (`IntHop` struct):**
```cpp
// simulation/src/network/utils/int-header.h
struct IntHop {
    uint64_t lineRate: 3;  // 3-bit INDEX into lineRateValues[8] lookup table
    uint64_t time:     24; // bits
    uint64_t bytes:    20; // bits (stores bytes / byteUnit)
    uint64_t qlen:     17; // bits (stores qlen / qlenUnit)
    // ...
    uint64_t GetLineRate() { return lineRateValues[lineRate]; } // Lookup actual bps
    uint64_t GetBytesDelta(IntHop &b) { ... } // Handles 20-bit wrap-around
    uint64_t GetTimeDelta(IntHop &b) { ... }  // Handles 24-bit wrap-around
};
```
> [!NOTE]
> `lineRate` is a **3-bit index** (0–7) into a fixed lookup table (`lineRateValues`), supporting rates: 1G, 10G, 25G, 50G, 100G, 200G, 400G bps. Call `GetLineRate()` to get the actual bits-per-second value.

### 3.2. Order of Operations: Max vs. Smooth

The user asked: *Is $U_{path}$ the max over $U_h$? And is smoothing applied per hop?*

**Answer:** It depends on the mode (**Aggregate** vs **Per-Hop**).

#### Mode A: Aggregate Rate (Default, `m_multipleRate = 0`)
1.  **Find Max Instantaneous Utilization**: The algorithm iterates over all hops and finds the single maximum utilization value among them.
    $$U_{inst\_max} = \max_{h \in Path} \{ u_h \}$$
2.  **Smooth the Bottleneck**: This *single maximum value* is then fed into the EWMA filter.
    $$U_{next} = (1 - w) \cdot U_{curr} + w \cdot U_{inst\_max}$$
    *The smoothing logic applies to the aggregate bottleneck value, not each hop individually.*

#### Mode B: Per-Hop Rate (`m_multipleRate = 1`)
1.  **Smooth Per Hop**: Each hop maintains its own smoothed utilization state.
    $$U_{next, h} = (1 - w) \cdot U_{curr, h} + w \cdot u_h$$
2.  **Per-Hop Reaction**: The rate update logic runs for each hop independently.

**Code Snippet (`RdmaHw::UpdateRateHp`, Aggregate Mode):**
```cpp
// 1. Loop to find Max Instantaneous Utilization
for (uint32_t i = 0; i < ih.nhop; i++){
    // ... calculate u ...
    if (!m_multipleRate){
        if (u > U){ // U keeps track of the maximum u across hops
            U = u;
            dt = tau;
        }
    }
}

// 2. Smooth the Max Value
if (!m_multipleRate){
    if (updated_any){
        // qp->hp.u is the single state variable for the flow
        qp->hp.u = (qp->hp.u * (qp->m_baseRtt - dt) + U * dt) / double(qp->m_baseRtt);
        
        // 3. Calculate Congestion Factor
        max_c = qp->hp.u / m_targetUtil;
    }
}
```

### 3.3. Utilization Smoothing (EWMA)

**Formula:**
$$
U_{next} = (1 - w) \cdot U_{curr} + w \cdot U_{measured}
$$
Where weight $w = \frac{\Delta t}{RTT_{base}}$.

**What is $\Delta t$?**
$\Delta t$ is the **time elapsed** between the current INT feedback sample and the previous sample **for the same flow at the specific hop**.
*   **Small $\Delta t$**: High-frequency feedback $\rightarrow$ Small weight (Stable).
*   **Large $\Delta t$**: Sparse feedback $\rightarrow$ Large weight (Responsive).

### 3.4. Rate Update Law

$$
max\_c = \frac{U_{path}}{T_u} \quad \text{(where } U_{path} = qp->hp.u \text{)}
$$

$T_u$ (`m_targetUtil`, default `0.95`) is the **target link utilization** — the desired steady-state fraction of link capacity. It sets the operating point: $max\_c < 1$ means the link is below target (safe to increase), $max\_c \ge 1$ means at or above target (must decrease). Setting $T_u < 1$ provides a stability margin so the algorithm begins to back off *before* the link is fully saturated.

$$
R_{new} = \begin{cases} 
\frac{R_{curr}}{max\_c} + R_{AI} & \text{if } max\_c \ge 1 \text{ or } \eta \ge \theta_{MI} \\
R_{curr} + R_{AI} & \text{otherwise}
\end{cases}
$$

---

## 4. Operational Mechanics

### 4.1. Fast Reaction vs. Full Update
*   **Full Update** (Start of new RTT): Commits changes to state (`m_curRate`).
*   **Fast Reaction** (Intra-RTT): Updates only pacing rate (`m_rate`), not state.

**Code Snippet (`RdmaHw::HandleAckHp`):**
```cpp
if (ack_seq > qp->hp.m_lastUpdateSeq){ 
    // New RTT -> Full Update
    UpdateRateHp(qp, p, ch, false);
} else { 
    // Same RTT -> Fast React
    FastReactHp(qp, p, ch); 
}
```

### 4.2. HPCC-PINT (Mode 10)
Uses probabilistic sampling.

**Code Snippet (`RdmaHw::HandleAckHpPint`):**
```cpp
// Decode global utilization from probabilistic sample
double U = Pint::decode_u(ih.GetPower());
// ... subsequent rate logic is identical to Standard HPCC
```

---

## 5. Parameters and Configuration

The following parameters (defined in `rdma-hw.cc`) control the behavior of the HPCC and HPCC-PINT algorithms. These can be set via command-line arguments or config files.

| Parameter Name | Default | Class Variable | Description |
| :--- | :--- | :--- | :--- |
| **CcMode** | `0` | `m_cc_mode` | Selects CC algorithm. `3` = HPCC, `10` = HPCC-PINT, `1` = DCQCN, `0` = None/Base. |
| **TargetUtil** | `0.95` | `m_targetUtil` | Target link utilization ($T_u$). Determining the steady-state load level. |
| **RateAI** | `5Mb/s` | `m_rai` | Additive Increase step size ($R_{AI}$). Amount of rate added per update during stability phase. |
| **MiThresh** | `5` | `m_miThresh` | Multiplicative Increase Threshold ($\theta_{MI}$). Number of consecutive AI steps before switching to Multiplicative Increase. |
| **MultiRate** | `true` | `m_multipleRate` | Enable **Per-Hop Rate Control**. If true, tracks rate candidates for every hop. If false, tracks single aggregate rate. |
| **FastReact** | `true` | `m_fast_react` | Enable **Fast Reaction**. If true, sender adjusts pacing rate immediately on every ACK with fresh INT data. |
| **VarWin** | `false` | `m_var_win` | Enable **Variable Window**. If true, window scales with rate ($W \propto R$). If false, window is fixed ($W = BDP$). |
| **MinRate** | `1Kbps` | `m_minRate` | Minimum flow rate floor. Prevents the rate from dropping to zero during severe congestion. Note: the attribute declaration shows `100Mb/s` but the constructor overrides it to `1Kbps`. |
| **RateBound** | `true` | `m_rateBound` | Enforces rate pacing. If false, packets are pushed as fast as the window allows (window-based only). |
| **PintSmplThresh** | `65536` | `pint_smpl_thresh` | PINT sampling threshold. Controls probability of INT header insertion by switches (Mode 10 only). |
| **RateHAI** | `50Mb/s` | `m_rhai` | Hyper-Additive Increase step. (Used primarily in DCQCN, but available in param list). |

---

## 7. Complete Sender Algorithm

### 1. Variables and Constants

| Symbol | Definition |
|:---|:---|
| $R(t)$ | Current sending rate |
| $W(t)$ | Current congestion window |
| $RTT_{base}$ | Minimum Round Trip Time (Base RTT) |
| $C$ | Link Capacity (Bottleneck Capacity) |
| $\eta$ | Multiplicative Increase Stage Counter |
| $\theta_{MI}$ | Multiplicative Increase Threshold |
| $T_u$ | Target Link Utilization (e.g., 0.95) |
| $R_{AI}$ | Additive Increase Rate Step (e.g., 5 Mbps) |

### 2. Initialization

$$
R(0) = C
$$
$$
W_{base} = C \times RTT_{base}
$$
$$
\eta = 0
$$

### 3. Transmission (Pacing)

For each packet $P$ of size $L_P$ bits:

$$
\Delta T_{gap} = \frac{L_P}{R(t)}
$$
Wait $\Delta T_{gap}$ before transmitting next packet.

### 4. Feedback Processing (Per ACK)

**Step A: Calculate Per-Hop Utilization**
For each hop $h \in \text{Path}$:
$$
u_h = \frac{\text{TxRate}_h}{C_h} + \frac{Q_h}{C_h \times RTT_{base}}
$$

**Step B: Determine Bottleneck Utilization**
$$
U_{max} = \max_{h \in \text{Path}} \{ u_h \}
$$

**Step C: Smooth Utilization Estimate**
Let $\Delta t$ be the time since the last update for this flow.
$$
w = \min \left( \frac{\Delta t}{RTT_{base}}, 1 \right)
$$
$$
U(t) = (1 - w) \cdot U(t-1) + w \cdot U_{max}
$$

**Step D: Compute Normailzed Congestion Factor**
$$
\max\_c = \frac{U(t)}{T_u}
$$

### 5. Rate Adaptation Law

Update rate $R(t)$ based on $\max\_c$:

$$
R_{target} = \begin{cases} 
\frac{R(t)}{\max\_c} + R_{AI} & \text{if } \max\_c \ge 1 \quad \text{(Congestion: Multiplicative Decrease)} \\
\frac{R(t)}{\max\_c} + R_{AI} & \text{if } \max\_c < 1 \text{ and } \eta \ge \theta_{MI} \quad \text{(Free Pipe: Multiplicative Increase)} \\
R(t) + R_{AI} & \text{otherwise} \quad \text{(Stability: Additive Increase)}
\end{cases}
$$

**Update Stage Counter $\eta$:**
$$
\eta \leftarrow \begin{cases} 
0 & \text{if } \max\_c \ge 1 \text{ or } \eta \ge \theta_{MI} \\
\eta + 1 & \text{otherwise}
\end{cases}
$$

**Clamp Rate:**
$$
R(t+1) = \max( \min(R_{target}, C), R_{min} )
$$

**Window Adjustment (Optional Safety Net):**
$$
W(t+1) = W_{base} \times \frac{R(t+1)}{C}
$$
