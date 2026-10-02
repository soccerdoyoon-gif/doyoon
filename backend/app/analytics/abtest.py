"""A/B 테스트 통계 — 두 비율 z-검정.

데이터가 적으면 결론을 내리지 않고 'insufficient_data' 를 돌려줍니다.
AI 도 이 결과를 그대로 따르도록 프롬프트에서 강제합니다.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

MIN_TRIALS = 1000  # 변형당 최소 노출(또는 클릭) 수
MIN_SUCCESSES = 30  # 변형당 최소 성공(클릭/참여/전환) 수
ALPHA = 0.05


@dataclass
class VariantStat:
    label: str
    trials: int
    successes: int

    @property
    def rate(self) -> float | None:
        return self.successes / self.trials if self.trials else None


@dataclass
class ABResult:
    verdict: str  # insufficient_data / no_significant_difference / significant
    winner: str | None
    p_value: float | None
    lift_percent: float | None
    rates: dict
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


def trials_successes(metric: str, impressions: int, clicks: int, engagements: int, conversions: int) -> tuple[int, int]:
    if metric == "ctr":
        return impressions, clicks
    if metric == "engagement_rate":
        return impressions, engagements
    if metric == "conversion_rate":
        return clicks, conversions
    raise ValueError(f"unknown metric {metric}")


def compare(a: VariantStat, b: VariantStat, min_trials: int = MIN_TRIALS, min_successes: int = MIN_SUCCESSES) -> ABResult:
    rates = {a.label: a.rate, b.label: b.rate}
    short = [v.label for v in (a, b) if v.trials < min_trials or v.successes < min_successes]
    if short:
        return ABResult(
            "insufficient_data",
            None,
            None,
            None,
            rates,
            f"데이터 부족: 변형 {', '.join(short)} 의 표본이 작습니다 (변형당 최소 {min_trials} 회 노출, {min_successes} 회 성공 필요). 아직 결론을 내리지 마세요.",
        )
    p1, p2 = a.successes / a.trials, b.successes / b.trials
    pooled = (a.successes + b.successes) / (a.trials + b.trials)
    se = math.sqrt(pooled * (1 - pooled) * (1 / a.trials + 1 / b.trials))
    if se == 0:
        return ABResult("no_significant_difference", None, 1.0, 0.0, rates, "두 변형의 비율이 같습니다.")
    z = (p1 - p2) / se
    p_value = math.erfc(abs(z) / math.sqrt(2))
    winner_v, loser_v = (a, b) if p1 > p2 else (b, a)
    lift = ((winner_v.rate - loser_v.rate) / loser_v.rate * 100) if loser_v.rate else None
    if p_value < ALPHA:
        return ABResult(
            "significant",
            winner_v.label,
            round(p_value, 5),
            round(lift, 2) if lift is not None else None,
            rates,
            f"변형 {winner_v.label} 가 통계적으로 유의하게 높습니다 (p={p_value:.4f}).",
        )
    return ABResult(
        "no_significant_difference",
        None,
        round(p_value, 5),
        round(lift, 2) if lift is not None else None,
        rates,
        f"유의한 차이가 없습니다 (p={p_value:.4f}). 테스트를 더 진행하거나 무승부로 보세요.",
    )
