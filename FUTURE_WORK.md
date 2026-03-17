# Future Work

Here is how to mathematically adapt the fairness and oscillation solutions to be 100% compatible with the current HPCC+ implementation.

## 1. Dynamic Additive Increase ($R_{AI}^{dyn}$)

The current implementation uses a fixed step $R_{AI}$ (from `RATE_AI`) in two critical places:

1. Probing the sender rate update ($R_{new}$).
2. Probing $C_{host}$ when uncongested.

To preserve proportional behavior across different host-capacity regimes, scale this step based on the estimated host capacity $C_{host}$, using the physical NIC line rate $C_{link,host}$ as the baseline.

First, define baseline aggressiveness:

$$
\alpha = \frac{RATE\_AI}{C_{link,host}}
$$

Then define dynamic additive increase with a minimum floor:

$$
R_{AI}^{dyn} = \max(\alpha \cdot C_{host}, \ R_{AI}^{min})
$$

Inject this into the HPCC+ formulas by replacing static $R_{AI}$ with $R_{AI}^{dyn}$.

For the uncongested host-capacity probe:

$$
C_{host} \leftarrow (1 - g) \cdot C_{host} + g \cdot \min(C_{host} + R_{AI}^{dyn}, \ C_{link,host})
$$

For sender rate adjustment:

$$
R_{new} = \frac{R_{current}}{U_{norm}} + R_{AI}^{dyn}
$$

Why this works: if $C_{host}$ drops to 10% of $C_{link,host}$, upward probes also drop to about 10% of their nominal magnitude, preventing synchronized overshoot by multiple senders.

## 2. Tuning the Dual-EWMA Architecture

The current architecture already has two smoothing stages:

1. `R_DELIVERED_GAIN` ($g_R$): pre-smoothing of raw delivered-rate samples.
2. `EWMA_GAIN` ($g$): tracking of estimated host capacity $C_{host}$.

To reduce oscillation, make the $C_{host}$ tracking asymmetric.

Goal:

1. React quickly when capacity is dropping (protect RX buffer).
2. Recover slowly when capacity appears to rise (avoid burst-induced overestimation).

Use two gains:

1. $g_{down}$ (for example, $1/4$) when $\hat{R}_{delivered} < C_{host}$.
2. $g_{up}$ (for example, $1/32$) when $\hat{R}_{delivered} \ge C_{host}$.

Update rule:

$$
C_{host} \leftarrow
\begin{cases}
(1 - g_{down}) \cdot C_{host} + g_{down} \cdot \hat{R}_{delivered} & \text{if } \hat{R}_{delivered} < C_{host} \\
(1 - g_{up}) \cdot C_{host} + g_{up} \cdot \hat{R}_{delivered} & \text{if } \hat{R}_{delivered} \ge C_{host}
\end{cases}
$$

This keeps the estimator conservative during recovery while still being protective under active congestion.

## 3. Hysteresis Deadband on $U_{norm}$

Current rate adjustment triggers multiplicative behavior when $U_{norm} \ge 1$, where:

$$
U_{norm} = \frac{U_{max}}{\eta}
$$

With $\eta = 0.95$, small telemetry noise near equilibrium can cause repeated crossing around 1.0, leading to unnecessary rate toggling and fairness instability.

Introduce a deadband tolerance $\epsilon$ around the target. Inside this band, freeze the sender rate:

$$
	ext{If } |U_{norm} - 1| \le \epsilon, \text{ then } R_{new} = R_{current}
$$

Example: with $\epsilon = 0.02$, any $U_{norm} \in [0.98, 1.02]$ produces no rate change. This acts as a shock absorber against jitter in $\hat{R}_{delivered}$ and host-hop utilization estimates.
