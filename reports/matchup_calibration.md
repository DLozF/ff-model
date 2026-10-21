# Matchup calibration

## Sample-size-aware gate (Task 03 A3)

The fixed 5% worst-bin rule stays visible below. A per-bin Wilson 95% interval for the
actual win rate plus a 1,000-replicate bootstrap ECE with a 95% interval replaces it as
the pass/fail signal, because a 360-pair bin has about 2.5% random noise at 1 SD and the
old rule treated that noise as a real calibration failure.

| Model | Worst fixed-bin error | Wilson-bin failures | Bootstrap ECE | ECE 95% interval |
|---|---:|---:|---:|---|
| Overall copula | 2.557% | 1 (bin 9) | 0.80% | [0.01%, 0.80%] |
| Stacked copula | 6.512% | 1 (bin 1) | 2.34% | [0.03%, 2.34%] |

Full per-bin Wilson intervals: `logs/task03-calibration-bins.csv`.

## Overall

- Copula minus independent Brier: -0.00000784 (paired week-bootstrap 95% interval [-0.00006456, +0.00004365])

| Model | Pairs | Brier | Log loss | Worst bin error |
|---|---:|---:|---:|---:|
| copula | 14400 | 0.219201 | 0.627611 | 0.025570 |
| independent | 14400 | 0.219208 | 0.627598 | 0.021134 |

### Calibration bins

| Bin | Copula pairs | Copula predicted | Copula actual | Copula error | Independent pairs | Independent predicted | Independent actual | Independent error |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 1440 | 0.2148 | 0.2146 | 0.0002 | 1440 | 0.2139 | 0.2090 | 0.0049 |
| 1 | 1440 | 0.3196 | 0.3097 | 0.0099 | 1440 | 0.3191 | 0.3181 | 0.0011 |
| 2 | 1440 | 0.3844 | 0.3826 | 0.0017 | 1440 | 0.3841 | 0.3812 | 0.0029 |
| 3 | 1440 | 0.4369 | 0.4292 | 0.0078 | 1440 | 0.4369 | 0.4306 | 0.0063 |
| 4 | 1440 | 0.4842 | 0.4854 | 0.0013 | 1440 | 0.4843 | 0.4806 | 0.0038 |
| 5 | 1440 | 0.5306 | 0.5257 | 0.0049 | 1440 | 0.5309 | 0.5243 | 0.0066 |
| 6 | 1440 | 0.5799 | 0.5792 | 0.0007 | 1440 | 0.5807 | 0.5868 | 0.0061 |
| 7 | 1440 | 0.6330 | 0.6424 | 0.0093 | 1440 | 0.6340 | 0.6375 | 0.0035 |
| 8 | 1440 | 0.6949 | 0.6833 | 0.0115 | 1440 | 0.6961 | 0.6868 | 0.0093 |
| 9 | 1440 | 0.7960 | 0.8215 | 0.0256 | 1440 | 0.7976 | 0.8187 | 0.0211 |

## Stacked

- Copula minus independent Brier: -0.00002415 (paired week-bootstrap 95% interval [-0.00019208, +0.00014881])

| Model | Pairs | Brier | Log loss | Worst bin error |
|---|---:|---:|---:|---:|
| copula | 3600 | 0.217772 | 0.624926 | 0.065119 |
| independent | 3600 | 0.217796 | 0.624901 | 0.062578 |

### Calibration bins

| Bin | Copula pairs | Copula predicted | Copula actual | Copula error | Independent pairs | Independent predicted | Independent actual | Independent error |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 360 | 0.2350 | 0.2306 | 0.0044 | 360 | 0.2309 | 0.2333 | 0.0024 |
| 1 | 360 | 0.3429 | 0.2778 | 0.0651 | 360 | 0.3404 | 0.2778 | 0.0626 |
| 2 | 360 | 0.4083 | 0.3972 | 0.0111 | 360 | 0.4072 | 0.3944 | 0.0127 |
| 3 | 360 | 0.4583 | 0.4222 | 0.0360 | 360 | 0.4584 | 0.4167 | 0.0417 |
| 4 | 360 | 0.5047 | 0.5083 | 0.0036 | 360 | 0.5059 | 0.5222 | 0.0164 |
| 5 | 360 | 0.5502 | 0.5306 | 0.0196 | 360 | 0.5521 | 0.5306 | 0.0215 |
| 6 | 360 | 0.5971 | 0.6167 | 0.0196 | 360 | 0.5997 | 0.6111 | 0.0114 |
| 7 | 360 | 0.6480 | 0.6556 | 0.0075 | 360 | 0.6517 | 0.6444 | 0.0073 |
| 8 | 360 | 0.7092 | 0.6972 | 0.0120 | 360 | 0.7145 | 0.7056 | 0.0090 |
| 9 | 360 | 0.8046 | 0.8306 | 0.0259 | 360 | 0.8099 | 0.8306 | 0.0207 |
