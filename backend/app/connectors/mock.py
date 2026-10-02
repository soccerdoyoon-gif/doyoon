"""Mock connector — API Key 가 없어도 전체 흐름을 테스트할 수 있게 해 줍니다.

여기서 만드는 성과 수치는 '테스트용 가짜 데이터' 이며 source='mock' 으로 저장되어
대시보드/AI 분석에서 실제 데이터와 구분됩니다.
"""
from __future__ import annotations

import random

from app.connectors.base import BaseConnector, MetricsResult, PublishRequest, PublishResult, stable_seed


class MockConnector(BaseConnector):
    mode = "mock"

    def __init__(self, platform: str, http=None, fail_times: int = 0):
        super().__init__(http)
        self.platform = platform
        self.fail_times = fail_times  # 테스트용: 처음 N 번 실패
        self.calls = 0

    def is_configured(self) -> bool:
        return True

    def publish(self, req: PublishRequest) -> PublishResult:
        self.calls += 1
        if self.calls <= self.fail_times:
            from app.connectors.base import ConnectorError

            raise ConnectorError(f"[MOCK] {self.platform} 임시 오류 (테스트)", retryable=True)
        return PublishResult(
            success=True,
            external_id=f"mock-{self.platform}-{req.content_id}",
            url=f"https://example.com/mock/{self.platform}/{req.content_id}",
            dry_run=self.settings.dry_run,
            simulated=True,
            message=f"[MOCK] {self.platform} 에 다음 게시물을 게시했을 것: {req.full_caption[:120]!r}",
        )

    def get_metrics(self, external_id: str, hours_since_publish: float = 24.0) -> MetricsResult:
        rng = random.Random(stable_seed(self.platform, external_id))
        growth = min(1.0, max(0.05, hours_since_publish / 48.0))
        base = rng.randint(300, 6000)
        reach = int(base * growth)
        views = int(reach * rng.uniform(1.0, 2.5)) if self.platform in ("tiktok", "instagram") else None
        likes = int(reach * rng.uniform(0.01, 0.09))
        m = MetricsResult(
            impressions=int(reach * rng.uniform(1.1, 1.6)),
            reach=reach if self.platform != "x" else None,
            views=views,
            likes=likes,
            comments=int(likes * rng.uniform(0.02, 0.15)),
            shares=int(likes * rng.uniform(0.01, 0.2)),
            saves=int(likes * rng.uniform(0.05, 0.3)) if self.platform in ("instagram", "x") else None,
            clicks=int(reach * rng.uniform(0.002, 0.02)) if self.platform in ("x", "facebook") else None,
            followers_gained=None,
            source="mock",
        )
        return m
