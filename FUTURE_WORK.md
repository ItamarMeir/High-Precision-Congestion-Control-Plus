# Future Work

## 1. Eliminating C_host Oscillations

Under sub-100% receiver pull rates, HPCC+ senders exhibit CWND and rate oscillations around the target pull rate. These stem from the `C_host` estimation dynamics. Several ideas to dampen them:

### 1.1 Proportional Additive Probe

**Status:** Implemented except for the proportional $R_{AI}/2$ step (we kept it just $R_{AI}$, see `HPCC_PLUS_README.md`).

> **Note:** The rest of the items in section 1 are optional for the future, but we don't focus on them right now.


### 1.2 RTT-Granularity C_host Updates

Currently `C_host` is updated on every ACK. At high packet rates this means many small adjustments per RTT, which can amplify oscillations. Instead, accumulate `rxBytes` and `rxQLen` samples over one RTT and update `C_host` once per RTT, similar to how some TCP variants update their rate estimate.

### 1.3 Host-Specific Target Utilization

HPCC uses `U_target = 0.95` for switch hops. For the host virtual hop, a slightly higher target (e.g., `U_host_target = 1.05`) could allow the sender to tolerate a small standing RX queue without backing off aggressively. This creates a deadband around the equilibrium point, reducing oscillation amplitude at the cost of a small amount of buffering.

---

## 2. Simulation Experiments (CURRENT FOCUS)

**We focus now on setting up experiments 2.1 and 2.2.**

### 2.1 Mice Flows Alongside Elephants

Inject short, latency-sensitive mice flows in bursts while two elephant flows are active. Measure mice-flow FCT under both HPCC and HPCC+. The hypothesis is that HPCC+'s lower RX buffer occupancy translates directly into lower queueing delay for mice flows.

### 2.2 RX Buffer vs. Number of Elephant Senders

Using the same topology and dynamic pull rate schedule, increase the number of elephant senders (2, 4, 8, 16, ...) targeting the same receiver. Plot peak and average RX buffer occupancy as a function of sender count for both HPCC and HPCC+. This characterizes the scalability advantage of receiver-aware congestion control—under HPCC the buffer should grow linearly with senders, while HPCC+ should keep it bounded.

### 2.3 Multiple Receiver Applications with Different Pull Rates

Two senders, one receiver, but two application-level consumers pulling from the RX buffer at different rates. This requires extending the receiver INT to maintain per-application `rxBytes` counters so the sender can distinguish which application's queue is backing up. This tests whether HPCC+ can handle heterogeneous receiver workloads on a single NIC.
