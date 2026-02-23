# Agent Handoff — HPCC+ Algorithm Fix (Feb 18, 2026)

## Summary of What Was Done

This session fixed the HPCC+ congestion control algorithm (CC_MODE 11) by implementing **receiver-side INT insertion**, a **conditional C_host estimation mechanism**, and fixing multiple bugs. CC_MODE 12 (TS-HPCC+) was removed as requested. All code changes are complete and the build compiles successfully. **Simulation was run but plot generation was interrupted** — plots need to be regenerated.

## What Changed and Where

### 1. Receiver-Side Host INT Insertion
**File**: `simulation/src/point-to-point/model/rdma-hw.cc` — `ReceiveUdp()` (~line 371)
**File**: `simulation/src/point-to-point/model/rdma-hw.h` — added `m_rxBytesTotal` member

The receiver now acts like a virtual switch. When a data packet arrives and an ACK is generated, the receiver pushes its own INT hop onto the packet's INT header:
```cpp
PushHop(timestamp, m_rxBytesTotal[nic], rxQueueLength, lineRate)
```
- `m_rxBytesTotal` is a per-NIC cumulative byte counter (analogous to switch `m_txBytes`), incremented each time a packet is pulled from the RX buffer.
- Initialized in `RdmaHw::Setup()`.

### 2. Fixed `HandleAckHpPlus` Logic
**File**: `rdma-hw.cc` — `HandleAckHpPlus()` (~line 1265)

**Fix**: Improved dispatch logic for CC_MODE 11 → `UpdateRateHpPlus`.

### 3. Rewrote `UpdateRateHpPlus` (CC_MODE 11) 
**File**: `rdma-hw.cc` — `UpdateRateHpPlus()` (~line 1386)

Complete rewrite. Key changes:
- **R_delivered** now computed from host INT deltas (`GetBytesDelta/GetTimeDelta`) — identical to switch txRate computation. Previously used `delta_bytes_acked / BaseRTT`.
- **Conditional C_host EWMA**: Only updates when `qlen > 0` (queue proves R_delivered ≈ capacity) OR when `R_delivered > C_host` (ratchet up). Previously updated unconditionally.
- **u_host formula**: `u_host = R_delivered / C_host + qlen / (C_host × BaseRTT)` — both terms use C_host. Previously throughput term used `C_max`.
- **Hop layout**: hops 0..nhop-2 are switches (standard HPCC), hop nhop-1 is the host hop.

### 5. Fixed `FastReactHpPlus`
**File**: `rdma-hw.cc` — `FastReactHpPlus()` (~line 1486)

Now correctly handles `UpdateRateHpPlus` for CC_MODE 11.

### 6. Updated README
**File**: `HPCC_PLUS_README.md`

Completely rewritten to reflect the new algorithm design with receiver-side INT and conditional C_host.

## Build & Run Status

| Step | Status |
|:--|:--|
| Build (`waf build`) | ✅ Compiled successfully |
| Simulation run | ✅ Completed (126.28s sim time) |
| Old plots deleted | ✅ Done |
| Plot regeneration | ⏳ **Interrupted** — needs to be re-run |

## What Needs to Be Done Next

1. **Regenerate plots for case2**:
   ```bash
   cd /workspace
   python3 results/run_all_plots.py --base-dir /workspace/results/study_cases/case2_dynamic_pulling_rate_HPCC_Plus
   ```
   This should produce 8 static PNGs in `plots/` and 5 interactive HTMLs in `interactive_plots/`.

2. **Verify simulation results** — check that:
   - RX buffer occupancy reflects the dynamic pulling rate schedule
   - CWND/RTT traces show proper congestion response
   - No PFC pauses (or minimal)

## Build Instructions (WSL)

```bash
# From WSL, navigate to the repo
cd /path/to/High-Precision-Congestion-Control-Plus

# Start container
docker compose up -d

# Enter container  
docker compose exec hpcc bash

# Build (inside container)
cd /workspace/simulation
# Fix waf if needed (copy waflib for Python 3):
cp -r .waf-1.7.11-edc6ccb516c5e3f9b892efc9f53a610f/waflib .waf3-1.7.11-edc6ccb516c5e3f9b892efc9f53a610f/waflib
python3 waf configure --build-profile=optimized --disable-python
python3 waf build

# Run case2 simulation
export LD_LIBRARY_PATH=/workspace/simulation/build:$LD_LIBRARY_PATH
./build/scratch/third /workspace/results/study_cases/case2_dynamic_pulling_rate_HPCC_Plus/config/config_hpcc_plus_dynamic.txt

# Generate plots
cd /workspace
python3 results/run_all_plots.py --base-dir /workspace/results/study_cases/case2_dynamic_pulling_rate_HPCC_Plus
```

## Key Files Reference

| File | Purpose |
|:--|:--|
| `simulation/src/point-to-point/model/rdma-hw.cc` | Main HPCC+ algorithm (sender + receiver) |
| `simulation/src/point-to-point/model/rdma-hw.h` | Added `m_rxBytesTotal` |
| `simulation/src/point-to-point/model/switch-node.cc` | Switch INT insertion |
| `simulation/src/point-to-point/model/rdma-queue-pair.h` | `hpccPlus` struct definition |
| `simulation/src/network/utils/int-header.h` | INT hop structure (`IntHop`, `IntHeader`) |
| `results/study_cases/case2_dynamic_pulling_rate_HPCC_Plus/` | Case2 config, data, plots |
| `results/run_all_plots.py` | Master plot script (use `--base-dir` for case-specific) |
| `HPCC_PLUS_README.md` | Algorithm documentation |

## Important Design Decisions

1. **Why conditional C_host?** Without it, when sender sends below receiver capacity, `R_delivered ≈ sending_rate < true_capacity`. Unconditionally updating `C_host = EWMA(R_delivered)` would cause `C_host` to track the sending rate, creating a deadlock where the sender can never increase rate.

2. **Why host hop is the LAST hop?** The receiver pushes its INT after all switch hops have been added during network traversal. The sender knows hop `nhop-1` is always the host.

3. **CC_MODE 11 vs 12**: MODE 11 always considers host utilization. MODE 12 only reacts to host congestion when the RX queue is non-empty (Q-only variant).
