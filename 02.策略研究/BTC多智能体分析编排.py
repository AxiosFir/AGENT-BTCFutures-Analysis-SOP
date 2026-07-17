"""BTC/ETH 日内分析 SOP v3.5 的可运行编排原型。

定位：验证数据契约、字段校验、错误分层和多智能体状态机；不下单。
LLM 与 TradingView 通过依赖注入接入，本文件不绑定具体厂商 SDK。
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Awaitable, Callable, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Grade(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"


class AgentRole(str, Enum):
    BULL = "BULL"
    BEAR = "BEAR"


class Stage(str, Enum):
    INITIAL_ANALYSIS = "INITIAL_ANALYSIS"
    PARALLEL_CASES = "PARALLEL_CASES"
    CROSS_REBUTTAL = "CROSS_REBUTTAL"
    JUDGE = "JUDGE"
    EXTERNAL_REVIEW = "EXTERNAL_REVIEW"
    FINALIZE = "FINALIZE"
    COMPLETE = "COMPLETE"


class ErrorScope(str, Enum):
    CORE = "CORE"
    AUXILIARY = "AUXILIARY"
    ENVIRONMENT = "ENVIRONMENT"


class ErrorSeverity(str, Enum):
    WARN = "WARN"
    DOWNGRADE = "DOWNGRADE"
    BLOCK = "BLOCK"


class DataStatus(str, Enum):
    VALID = "VALID"
    STALE = "STALE"
    MISSING = "MISSING"
    ANOMALOUS = "ANOMALOUS"
    CONFLICTING = "CONFLICTING"


class ReviewVerdict(str, Enum):
    CONFIRM = "CONFIRM"
    NEUTRAL = "NEUTRAL"
    CONFLICT = "CONFLICT"
    ERROR = "ERROR"


GRADE_SCORE = {Grade.D: 0, Grade.C: 1, Grade.B: 2, Grade.A: 3}
SCORE_GRADE = {value: key for key, value in GRADE_SCORE.items()}


class PipelineIssue(StrictModel):
    code: str
    scope: ErrorScope
    severity: ErrorSeverity
    source: str
    field: str | None = None
    message: str
    grade_cap: Grade | None = None
    retryable: bool = False

    @model_validator(mode="after")
    def validate_blocking_issue(self) -> "PipelineIssue":
        if self.scope == ErrorScope.CORE and self.severity == ErrorSeverity.BLOCK:
            if self.grade_cap not in (None, Grade.D):
                raise ValueError("核心阻断错误的评级上限只能是 D")
            self.grade_cap = Grade.D
        return self


class EvidenceItem(StrictModel):
    evidence_id: str
    source: str
    timeframe: str | None = None
    observed_at: datetime
    data_status: DataStatus
    value: Any


class EvidencePacket(StrictModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    analysis_id: str
    generation: int = Field(ge=1)
    packet_id: str
    content_hash: str
    created_at: datetime
    items: tuple[EvidenceItem, ...]

    @classmethod
    def build(
        cls, analysis_id: str, generation: int, items: list[EvidenceItem]
    ) -> "EvidencePacket":
        serialized = json.dumps(
            [item.model_dump(mode="json") for item in items],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return cls(
            analysis_id=analysis_id,
            generation=generation,
            packet_id=f"{analysis_id}-g{generation}",
            content_hash=digest,
            created_at=datetime.now(UTC),
            items=tuple(items),
        )


class EvidenceRef(StrictModel):
    evidence_id: str
    interpretation: str


class Claim(StrictModel):
    claim_id: str
    statement: str
    evidence_refs: list[EvidenceRef] = Field(min_length=1)


class PriceZone(StrictModel):
    lower: Decimal = Field(gt=0)
    upper: Decimal = Field(gt=0)

    @model_validator(mode="after")
    def validate_zone(self) -> "PriceZone":
        if self.lower > self.upper:
            raise ValueError("价格区间下限不得高于上限")
        return self


class TradeScenario(StrictModel):
    direction: Literal[Direction.LONG, Direction.SHORT]
    entry_zone: PriceZone
    trigger: str
    stop_loss: Decimal = Field(gt=0)
    take_profits: list[Decimal] = Field(min_length=1, max_length=2)
    risk_reward: Decimal = Field(ge=Decimal("1.5"))
    invalidation: str
    valid_until: datetime

    @model_validator(mode="after")
    def validate_price_order(self) -> "TradeScenario":
        if self.direction == Direction.LONG:
            if self.stop_loss >= self.entry_zone.lower:
                raise ValueError("LONG 止损必须低于入场区")
            if any(tp <= self.entry_zone.upper for tp in self.take_profits):
                raise ValueError("LONG 止盈必须高于入场区")
        else:
            if self.stop_loss <= self.entry_zone.upper:
                raise ValueError("SHORT 止损必须高于入场区")
            if any(tp >= self.entry_zone.lower for tp in self.take_profits):
                raise ValueError("SHORT 止盈必须低于入场区")
        return self


class InitialAnalysisPayload(StrictModel):
    market_regime: Literal["TREND", "RANGE", "COMPRESSION", "DISORDERLY"]
    neutral_claims: list[Claim]
    open_questions: list[str] = Field(default_factory=list)


class DirectionalCasePayload(StrictModel):
    role: AgentRole
    direction: Direction
    thesis: str
    claims: list[Claim] = Field(min_length=1)
    adverse_evidence: list[EvidenceRef] = Field(min_length=1)
    weakest_point: str
    scenario: TradeScenario | None = None
    suggested_grade: Grade

    @model_validator(mode="after")
    def validate_role_direction(self) -> "DirectionalCasePayload":
        expected = Direction.LONG if self.role == AgentRole.BULL else Direction.SHORT
        if self.direction != expected:
            raise ValueError("代理角色与方向不一致")
        if self.scenario is not None and self.scenario.direction != self.direction:
            raise ValueError("代理方向与交易场景方向不一致")
        if self.scenario is None and self.suggested_grade != Grade.D:
            raise ValueError("无交易场景时代理评级必须为 D")
        return self


class RebuttalItem(StrictModel):
    target_claim_id: str
    verdict: Literal["ACCEPTED", "PARTIAL", "REJECTED", "UNVERIFIED"]
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    response: str
    plan_changed: bool = False

    @model_validator(mode="after")
    def require_evidence(self) -> "RebuttalItem":
        if self.verdict != "UNVERIFIED" and not self.evidence_refs:
            raise ValueError("可验证的反驳必须引用证据")
        return self


class RebuttalPayload(StrictModel):
    round_no: int = Field(ge=1, le=2)
    responder: AgentRole
    items: list[RebuttalItem] = Field(min_length=1)
    revised_case: DirectionalCasePayload
    requests_another_round: bool = False


class JudgePayload(StrictModel):
    preferred_direction: Direction
    bull_candidate_grade: Grade
    bear_candidate_grade: Grade
    preliminary_grade: Grade
    unresolved_disputes: list[str]
    preliminary_reason: str


class ReviewPayload(StrictModel):
    reviewer: str
    available: bool
    verdict: ReviewVerdict
    issues: list[PipelineIssue] = Field(default_factory=list)
    contains_new_market_evidence: bool = False


PayloadT = TypeVar("PayloadT", bound=StrictModel)


class StageEnvelope(StrictModel, Generic[PayloadT]):
    schema_version: Literal["1.1"] = "1.1"
    analysis_id: str
    evidence_generation: int = Field(ge=1)
    evidence_hash: str
    stage: Stage
    generated_at: datetime
    payload: PayloadT
    issues: list[PipelineIssue] = Field(default_factory=list)


def wrap_stage(
    packet: EvidencePacket, stage: Stage, payload: PayloadT
) -> StageEnvelope[PayloadT]:
    return StageEnvelope[type(payload)](  # type: ignore[valid-type]
        analysis_id=packet.analysis_id,
        evidence_generation=packet.generation,
        evidence_hash=packet.content_hash,
        stage=stage,
        generated_at=datetime.now(UTC),
        payload=payload,
    )


def assert_current_packet(artifact: StageEnvelope[Any], packet: EvidencePacket) -> None:
    if (
        artifact.analysis_id != packet.analysis_id
        or artifact.evidence_generation != packet.generation
        or artifact.evidence_hash != packet.content_hash
    ):
        raise ValueError("阶段产物引用了旧证据包")


def validate_evidence_refs(model: BaseModel, packet: EvidencePacket) -> None:
    valid_ids = {item.evidence_id for item in packet.items}

    def walk(value: Any) -> None:
        if isinstance(value, EvidenceRef):
            if value.evidence_id not in valid_ids:
                raise ValueError(f"未知或过期的 evidence_id: {value.evidence_id}")
            return
        if isinstance(value, BaseModel):
            for field_value in value.__dict__.values():
                walk(field_value)
            return
        if isinstance(value, dict):
            for field_value in value.values():
                walk(field_value)
            return
        if isinstance(value, (list, tuple, set)):
            for field_value in value:
                walk(field_value)

    walk(model)


class VolumeMetrics(StrictModel):
    current_volume: Decimal = Field(ge=0)
    average_volume: Decimal = Field(gt=0)
    volume_ratio: Decimal = Field(ge=0)
    bar_state: Literal["CLOSED", "FORMING"]

    @model_validator(mode="after")
    def validate_ratio(self) -> "VolumeMetrics":
        expected = self.current_volume / self.average_volume
        tolerance = max(Decimal("0.02"), abs(expected) * Decimal("0.03"))
        if abs(self.volume_ratio - expected) > tolerance:
            raise ValueError("volume_ratio 与 current_volume / average_volume 不一致")
        return self


def validate_volume_fields(
    *, current_volume: Any, average_volume: Any, volume_ratio: Any, source: str
) -> tuple[VolumeMetrics | None, list[PipelineIssue]]:
    try:
        metrics = VolumeMetrics(
            current_volume=Decimal(str(current_volume)),
            average_volume=Decimal(str(average_volume)),
            volume_ratio=Decimal(str(volume_ratio)),
            bar_state="CLOSED",
        )
        return metrics, []
    except Exception as exc:
        return None, [
            PipelineIssue(
                code="VOLUME_INVARIANT_FAILED",
                scope=ErrorScope.AUXILIARY,
                severity=ErrorSeverity.WARN,
                source=source,
                field="average_volume,volume_ratio",
                message=str(exc),
            )
        ]


def check_optional_skill_environment(
    module_name: str = "ccxt",
) -> list[PipelineIssue]:
    """只做预检，不安装依赖；失败不得中断核心分析链。"""
    if importlib.util.find_spec(module_name) is not None:
        return []
    return [
        PipelineIssue(
            code="OPTIONAL_SKILL_DEPENDENCY_MISSING",
            scope=ErrorScope.ENVIRONMENT,
            severity=ErrorSeverity.WARN,
            source="cryptocurrency-trader",
            field=module_name,
            message=f"可选复核依赖 {module_name} 不可用；跳过该复核且不自动安装",
        )
    ]


class KlineSummary(StrictModel):
    symbol: str
    interval: str
    server_time: datetime
    last_closed_at: datetime
    closed_rows: int = Field(ge=21)
    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)
    current_volume: Decimal = Field(ge=0)
    average_volume_20: Decimal = Field(gt=0)
    volume_ratio: Decimal = Field(ge=0)
    atr_14: Decimal = Field(gt=0)
    issues: list[PipelineIssue] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_ohlc(self) -> "KlineSummary":
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("K 线 High 逻辑错误")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("K 线 Low 逻辑错误")
        return self


def _get_json(url: str, timeout: float = 12.0) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": "SOP-v3.5-test"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_binance_kline_summary(
    symbol: str, interval: str, limit: int = 210
) -> KlineSummary:
    base = "https://fapi.binance.com"
    server_ms = int(_get_json(f"{base}/fapi/v1/time")["serverTime"])
    query = urllib.parse.urlencode(
        {"symbol": symbol, "interval": interval, "limit": limit}
    )
    rows = _get_json(f"{base}/fapi/v1/klines?{query}")
    closed = [row for row in rows if int(row[6]) < server_ms]
    if len(closed) < 21:
        raise ValueError(f"{interval} 已收盘 K 线不足 21 根")

    for previous, current in zip(closed, closed[1:]):
        if int(current[0]) <= int(previous[0]):
            raise ValueError(f"{interval} K 线时间戳重复或倒序")
        o, h, low, c, volume = map(Decimal, current[1:6])
        if h < max(o, c, low) or low > min(o, c, h) or volume < 0:
            raise ValueError(f"{interval} K 线字段逻辑错误")

    last = closed[-1]
    previous_20 = closed[-21:-1]
    average = sum((Decimal(row[5]) for row in previous_20), Decimal(0)) / 20
    current_volume = Decimal(last[5])
    ratio = current_volume / average

    true_ranges: list[Decimal] = []
    for index in range(len(closed) - 14, len(closed)):
        row = closed[index]
        prev_close = Decimal(closed[index - 1][4])
        high = Decimal(row[2])
        low = Decimal(row[3])
        true_ranges.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))

    return KlineSummary(
        symbol=symbol,
        interval=interval,
        server_time=datetime.fromtimestamp(server_ms / 1000, UTC),
        last_closed_at=datetime.fromtimestamp(int(last[6]) / 1000, UTC),
        closed_rows=len(closed),
        open=Decimal(last[1]),
        high=Decimal(last[2]),
        low=Decimal(last[3]),
        close=Decimal(last[4]),
        current_volume=current_volume,
        average_volume_20=average,
        volume_ratio=ratio,
        atr_14=sum(true_ranges, Decimal(0)) / 14,
    )


def downgrade_one(grade: Grade) -> Grade:
    return SCORE_GRADE[max(0, GRADE_SCORE[grade] - 1)]


def deterministic_final_grade(
    preliminary: Grade,
    *,
    evidence_cap: Grade = Grade.A,
    data_cap: Grade = Grade.A,
    timeframe_cap: Grade = Grade.A,
    issues: list[PipelineIssue] | None = None,
    reviews: list[ReviewPayload] | None = None,
) -> Grade:
    issues = issues or []
    reviews = reviews or []
    caps = [preliminary, evidence_cap, data_cap, timeframe_cap]
    caps.extend(issue.grade_cap for issue in issues if issue.grade_cap is not None)

    if any(
        issue.scope == ErrorScope.CORE and issue.severity == ErrorSeverity.BLOCK
        for issue in issues
    ):
        caps.append(Grade.D)

    material_conflict = any(review.verdict == ReviewVerdict.CONFLICT for review in reviews)
    if material_conflict:
        caps.append(downgrade_one(preliminary))

    return min(caps, key=lambda grade: GRADE_SCORE[grade])


AgentCall = Callable[..., Awaitable[BaseModel | dict[str, Any] | str]]


class AgentSet(StrictModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    initial: AgentCall
    bull: AgentCall
    bear: AgentCall
    rebuttal: AgentCall
    judge: AgentCall
    reviewers: list[AgentCall] = Field(default_factory=list)


class OrchestrationResult(StrictModel):
    analysis_id: str
    evidence_generation: int
    stages: list[Stage]
    debate_rounds: int
    preliminary_grade: Grade
    final_grade: Grade
    issues: list[PipelineIssue]
    bull_case: DirectionalCasePayload
    bear_case: DirectionalCasePayload
    judge: JudgePayload
    reviews: list[ReviewPayload]


class Orchestrator:
    """有限状态多智能体编排器；初始多空分析真正并行且互不可见。"""

    def __init__(self, agents: AgentSet, max_debate_rounds: int = 2):
        self.agents = agents
        self.max_debate_rounds = max_debate_rounds

    async def _typed_call(
        self,
        call: AgentCall,
        schema: type[PayloadT],
        packet: EvidencePacket,
        **kwargs: Any,
    ) -> PayloadT:
        last_error: Exception | None = None
        for attempt in range(3):
            raw = await call(packet=packet, attempt=attempt, **kwargs)
            try:
                if isinstance(raw, schema):
                    payload = raw
                elif isinstance(raw, str):
                    payload = TypeAdapter(schema).validate_json(raw)
                else:
                    payload = TypeAdapter(schema).validate_python(raw)
                validate_evidence_refs(payload, packet)
                return payload
            except Exception as exc:  # 最多两次 Schema 修复
                last_error = exc
        raise ValueError(f"代理输出连续三次未通过 Schema：{last_error}")

    async def run(self, packet: EvidencePacket) -> OrchestrationResult:
        stages: list[Stage] = []
        issues: list[PipelineIssue] = []

        initial = await self._typed_call(
            self.agents.initial, InitialAnalysisPayload, packet
        )
        stages.append(Stage.INITIAL_ANALYSIS)

        # 独立性保证：两个任务只接收同一 packet 与 initial，互不接收对方结果。
        bull_task = self._typed_call(
            self.agents.bull,
            DirectionalCasePayload,
            packet,
            initial=initial,
            role=AgentRole.BULL,
        )
        bear_task = self._typed_call(
            self.agents.bear,
            DirectionalCasePayload,
            packet,
            initial=initial,
            role=AgentRole.BEAR,
        )
        bull, bear = await asyncio.gather(bull_task, bear_task)
        stages.append(Stage.PARALLEL_CASES)

        rounds = 0
        while rounds < self.max_debate_rounds:
            rounds += 1
            bull_task = self._typed_call(
                self.agents.rebuttal,
                RebuttalPayload,
                packet,
                round_no=rounds,
                own_case=bull,
                opponent_case=bear,
                role=AgentRole.BULL,
            )
            bear_task = self._typed_call(
                self.agents.rebuttal,
                RebuttalPayload,
                packet,
                round_no=rounds,
                own_case=bear,
                opponent_case=bull,
                role=AgentRole.BEAR,
            )
            bull_rebuttal, bear_rebuttal = await asyncio.gather(bull_task, bear_task)
            bull = bull_rebuttal.revised_case
            bear = bear_rebuttal.revised_case
            if not (
                bull_rebuttal.requests_another_round
                or bear_rebuttal.requests_another_round
            ):
                break
        stages.append(Stage.CROSS_REBUTTAL)

        judge = await self._typed_call(
            self.agents.judge,
            JudgePayload,
            packet,
            initial=initial,
            bull_case=bull,
            bear_case=bear,
        )
        stages.append(Stage.JUDGE)

        review_tasks = [
            self._typed_call(call, ReviewPayload, packet, judge=judge)
            for call in self.agents.reviewers
        ]
        reviews = list(await asyncio.gather(*review_tasks)) if review_tasks else []
        for review in reviews:
            issues.extend(review.issues)
            if review.contains_new_market_evidence:
                issues.append(
                    PipelineIssue(
                        code="REVIEW_INTRODUCED_NEW_EVIDENCE",
                        scope=ErrorScope.CORE,
                        severity=ErrorSeverity.BLOCK,
                        source=review.reviewer,
                        message="复核发现新市场事实，必须刷新证据包并重跑，不能直接写入结论",
                        grade_cap=Grade.D,
                    )
                )
        stages.append(Stage.EXTERNAL_REVIEW)

        final_grade = deterministic_final_grade(
            judge.preliminary_grade, issues=issues, reviews=reviews
        )
        stages.extend((Stage.FINALIZE, Stage.COMPLETE))
        return OrchestrationResult(
            analysis_id=packet.analysis_id,
            evidence_generation=packet.generation,
            stages=stages,
            debate_rounds=rounds,
            preliminary_grade=judge.preliminary_grade,
            final_grade=final_grade,
            issues=issues,
            bull_case=bull,
            bear_case=bear,
            judge=judge,
            reviews=reviews,
        )


def _main() -> None:
    parser = argparse.ArgumentParser(description="SOP v3.5 原始 K 线测试")
    parser.add_argument("--test-binance", choices=("BTCUSDT", "ETHUSDT"))
    args = parser.parse_args()
    if not args.test_binance:
        parser.print_help()
        return
    summaries = [
        fetch_binance_kline_summary(args.test_binance, timeframe)
        for timeframe in ("15m", "1h", "4h", "1d")
    ]
    print(
        json.dumps(
            [summary.model_dump(mode="json", exclude_none=True) for summary in summaries],
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    _main()
