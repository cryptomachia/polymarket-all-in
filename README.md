# Polymarket-All-In

## Overview

This script fetches all available YES/NO binary active markets with uncertain prediction outcomes on Polymarket. It calculates the average risk-reward ratio and cumulative expected value for betting in a single direction, based on the minimum order size allowed. The outcomes are considered uncertain if the price is greater than 0.001 and less than 1, meaning the probability of either the YES or NO bet (depending on the strategy chosen) is greater than 0.1% and less than 100%, ensuring non-trivial outcomes. create_order, post_order, get_price from the polymarket CLOB api require level two (API based) authentication, while other public endpoints can be retrieved through private key authentication like get_order_book_liquidity

### Trading Strategies

1. **Unlikely Strategy**: Places the minimum bet on the less probable choice for all binary YES/NO active non-trivial markets.
2. **Likely Strategy**: Places the minimum bet on the more probable choice for all binary YES/NO active non-trivial markets.

### September 2nd Run Summary

- **Number of Markets at Each Minimum Order Size**:
  - Minimum Order Size: 5 - Number of Markets: 1199
  - Minimum Order Size: 15 - Number of Markets: 16

#### Likely Side

- **Total Potential Profit if All Trades Succeed**: $662.35
- **Total Bet Size (Total Potential Loss if All Trades Fail)**: $6025.00
- **Average Risk-Reward Ratio**: 0.10
- **Cumulative Expected Value**: $-5182.52
- **Status**: Done placing orders.

#### Unlikely Side

- **Total Potential Profit if All Trades Succeed**: $72,911.83
- **Total Bet Size (Total Potential Loss if All Trades Fail)**: $74,216.52
- **Average Risk-Reward Ratio**: 0.89
- **Cumulative Expected Value**: $70,502.19
- **Status**: Done placing orders.

### Analysis

- At the time of the September 2nd run, the expected value was positive for both strategies, but the expected value per $1 was 0.1 for the likely strategy and 0.89 for the unlikely strategy. This indicates that while it is generally unprofitable on a dollar-for-dollar basis to place these bets ("ape"), the unlikely strategy surprisingly resulted in a positive cumulative expected value of $70,502.19 compared to a negative $-5182.52 for the likely strategy.
- However, the risk involved is significantly higher for the unlikely strategy, with a potential loss of $74,216.52 compared to $6,025.00 for the likely side.
- Probabilities were normalized to ensure that the sum of win probabilities for YES and NO equals 1. This adjustment was necessary because very small probabilities just above the 0.001 threshold initially skewed the expected value and risk-reward ratio.

### Conclusion

The script demonstrates that while the unlikely strategy appears to offer a higher cumulative expected value, it comes with significantly higher risk. The likely strategy, though less risky, shows a negative expected value, indicating potential losses over time. These insights can guide decision-making when betting on binary markets with uncertain outcomes.
