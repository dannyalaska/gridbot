from dataclasses import dataclass
from typing import Optional  # noqa: F401 (used in type hints)

from .config import AppConfig
from .risk_guard import RiskGuard, RiskState
from .sentiment_scout import SentimentSnapshot


@dataclass
class AgentDecision:
    allow_new_buys: bool
    pause_trading: bool
    reason: Optional[str]
    agent: str
    order_size_multiplier: float = 1.0


class LLMRiskAgent:
    """
    Heuristic stand-in for an LLM risk agent. When enabled it can veto new buys.
    """

    def __init__(self, cfg: AppConfig):
        self.cfg = cfg

    def decide(
        self,
        risk_state: RiskState,
        sentiment: SentimentSnapshot,
        rsi: Optional[float] = None,
    ) -> AgentDecision:
        # RSI-derived order size multiplier (applied regardless of llm_risk.enabled)
        order_size_multiplier = self._rsi_multiplier(rsi)

        if not self.cfg.llm_risk.enabled:
            return AgentDecision(
                allow_new_buys=True,
                pause_trading=False,
                reason=None,
                agent="llm_risk",
                order_size_multiplier=order_size_multiplier,
            )

        reasons = []
        if self.cfg.llm_risk.max_daily_loss_pct and risk_state.loss_pct >= self.cfg.llm_risk.max_daily_loss_pct:
            reasons.append(f"loss {risk_state.loss_pct:.2f}% >= {self.cfg.llm_risk.max_daily_loss_pct:.2f}%")
        if self.cfg.llm_risk.max_drawdown_pct and risk_state.drawdown_pct >= self.cfg.llm_risk.max_drawdown_pct:
            reasons.append(f"drawdown {risk_state.drawdown_pct:.2f}% >= {self.cfg.llm_risk.max_drawdown_pct:.2f}%")
        if self.cfg.llm_risk.max_crash_pct and risk_state.crash_pct >= self.cfg.llm_risk.max_crash_pct:
            reasons.append(f"crash {risk_state.crash_pct:.2f}% >= {self.cfg.llm_risk.max_crash_pct:.2f}%")
        if self.cfg.llm_risk.block_on_news_risk and sentiment.news_risk.lower() in {"high", "elevated"}:
            reasons.append(f"news risk {sentiment.news_risk}")

        # RSI overbought: pause new buys entirely
        if rsi is not None and rsi >= self.cfg.indicators.rsi_overbought:
            reasons.append(f"RSI overbought ({rsi:.1f} >= {self.cfg.indicators.rsi_overbought:.0f})")

        if reasons:
            return AgentDecision(
                allow_new_buys=False,
                pause_trading=True,
                reason="LLM risk veto: " + "; ".join(reasons),
                agent="llm_risk",
                order_size_multiplier=0.0,
            )
        return AgentDecision(
            allow_new_buys=True,
            pause_trading=False,
            reason=None,
            agent="llm_risk",
            order_size_multiplier=order_size_multiplier,
        )

    def _rsi_multiplier(self, rsi: Optional[float]) -> float:
        """Map RSI to an order size multiplier.

        Oversold (RSI < rsi_oversold)  → 1.25 (buy more aggressively)
        Neutral  (RSI 30–50)           → 1.00
        Caution  (RSI 50–70)           → 0.75 (market trending up, be careful)
        Overbought (RSI >= rsi_overbought) → 0.0 (no new buys; handled above)
        """
        if rsi is None:
            return 1.0
        oversold = self.cfg.indicators.rsi_oversold
        overbought = self.cfg.indicators.rsi_overbought
        if rsi < oversold:
            return 1.25
        if rsi < 50.0:
            return 1.0
        if rsi < overbought:
            return 0.75
        return 0.0


class ManagerAgent:
    """
    Aggregates risk guard and LLM risk agent decisions into a final policy.
    """

    def decide(
        self,
        base_state: RiskState,
        llm_decision: AgentDecision,
        health_ok: bool,
    ) -> AgentDecision:
        reasons = []
        if base_state.paused:
            reasons.append("risk guard pause")
        if llm_decision.pause_trading:
            reasons.append("llm veto")
        if not health_ok:
            reasons.append("health check failed")

        if reasons:
            return AgentDecision(
                allow_new_buys=False,
                pause_trading=True,
                reason="Manager pause: " + "; ".join(reasons),
                agent="manager",
            )
        return AgentDecision(allow_new_buys=True, pause_trading=False, reason=None, agent="manager")


def _merge_reasons(*reasons: Optional[str]) -> Optional[str]:
    parts = [reason for reason in reasons if reason]
    if not parts:
        return None
    return " | ".join(parts)


class RiskCouncil:
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.risk_guard = RiskGuard(cfg)
        self.llm_agent = LLMRiskAgent(cfg)
        self.manager = ManagerAgent()

    def restore_state(self, start_equity: float | None, max_equity: float | None) -> None:
        self.risk_guard.restore_state(start_equity, max_equity)

    def evaluate(
        self,
        price: float,
        balances: dict,
        sentiment: SentimentSnapshot,
        health_ok: bool,
        rsi: Optional[float] = None,
    ) -> RiskState:
        base_state = self.risk_guard.evaluate(price, balances)
        llm_decision = self.llm_agent.decide(base_state, sentiment, rsi=rsi)
        manager_decision = self.manager.decide(base_state, llm_decision, health_ok)

        paused = base_state.paused or llm_decision.pause_trading or manager_decision.pause_trading
        allow_new_buys = base_state.allow_new_buys and llm_decision.allow_new_buys and manager_decision.allow_new_buys
        reason = _merge_reasons(base_state.reason, llm_decision.reason, manager_decision.reason)

        return RiskState(
            equity=base_state.equity,
            drawdown_pct=base_state.drawdown_pct,
            loss_pct=base_state.loss_pct,
            crash_pct=base_state.crash_pct,
            paused=paused,
            allow_new_buys=allow_new_buys,
            reason=reason,
            start_equity=base_state.start_equity,
            max_equity=base_state.max_equity,
            order_size_multiplier=llm_decision.order_size_multiplier,
        )
