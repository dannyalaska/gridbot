"""Pure-function market indicators: ATR, RSI, Bollinger Bands.

All functions take plain Python lists (oldest-first) and return floats.
No side effects, no external dependencies.
"""
import math
from typing import List, Tuple


def calc_sma(values: List[float], period: int) -> float:
    """Simple moving average of the last `period` values."""
    if len(values) < period:
        raise ValueError(f"Need {period} values for SMA, got {len(values)}")
    return sum(values[-period:]) / period


def calc_atr(candles: List[List[float]], period: int = 14) -> float:
    """Average True Range over `period` candles.

    candles: [[timestamp, open, high, low, close, volume], ...] (oldest first)

    True Range = max(high-low, |high-prev_close|, |low-prev_close|)
    ATR = average of the last `period` true ranges.
    """
    if len(candles) < period + 1:
        raise ValueError(
            f"Need at least {period + 1} candles for ATR({period}), got {len(candles)}"
        )
    true_ranges: List[float] = []
    for i in range(1, len(candles)):
        high = float(candles[i][2])
        low = float(candles[i][3])
        prev_close = float(candles[i - 1][4])
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)

    recent = true_ranges[-period:]
    return sum(recent) / len(recent)


def calc_rsi(closes: List[float], period: int = 14) -> float:
    """Relative Strength Index using Wilder's smoothed moving average.

    closes: list of closing prices, oldest first.
    Returns RSI value in range [0, 100].
    """
    if len(closes) < period + 1:
        raise ValueError(
            f"Need at least {period + 1} closes for RSI({period}), got {len(closes)}"
        )
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]

    # Seed with simple average of first `period` moves
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    # Wilder's EMA for remaining moves
    for g, l in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + l) / period

    if avg_loss == 0.0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def calc_bollinger(
    closes: List[float], period: int = 20, num_std: float = 2.0
) -> Tuple[float, float, float]:
    """Bollinger Bands.

    closes: list of closing prices, oldest first.
    Returns (lower, middle, upper).
    middle = SMA(period), bands = middle ± num_std * population_stdev.
    """
    if len(closes) < period:
        raise ValueError(
            f"Need at least {period} closes for Bollinger({period}), got {len(closes)}"
        )
    window = closes[-period:]
    middle = sum(window) / period
    variance = sum((x - middle) ** 2 for x in window) / period
    std = math.sqrt(variance)
    lower = middle - num_std * std
    upper = middle + num_std * std
    return lower, middle, upper
