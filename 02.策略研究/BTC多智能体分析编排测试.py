import unittest
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from BTC多智能体分析编排 import (
    AgentRole,
    AgentSet,
    Claim,
    DataStatus,
    Direction,
    DirectionalCasePayload,
    ErrorScope,
    ErrorSeverity,
    EvidenceItem,
    EvidencePacket,
    EvidenceRef,
    Grade,
    InitialAnalysisPayload,
    JudgePayload,
    Orchestrator,
    PipelineIssue,
    PriceZone,
    RebuttalItem,
    RebuttalPayload,
    ReviewPayload,
    ReviewVerdict,
    Stage,
    TradeScenario,
    assert_current_packet,
    check_optional_skill_environment,
    deterministic_final_grade,
    validate_volume_fields,
    wrap_stage,
)


def make_packet(generation: int = 1) -> EvidencePacket:
    return EvidencePacket.build(
        analysis_id="test-btc",
        generation=generation,
        items=[
            EvidenceItem(
                evidence_id=f"BN-1H-CLOSE-G{generation}",
                source="Binance raw kline",
                timeframe="1h",
                observed_at=datetime.now(UTC),
                data_status=DataStatus.VALID,
                value="63457.5",
            )
        ],
    )


def make_claim(packet: EvidencePacket, suffix: str) -> Claim:
    return Claim(
        claim_id=f"claim-{suffix}",
        statement=f"测试主张 {suffix}",
        evidence_refs=[
            EvidenceRef(
                evidence_id=packet.items[0].evidence_id,
                interpretation="引用当前证据包",
            )
        ],
    )


def make_case(packet: EvidencePacket, role: AgentRole) -> DirectionalCasePayload:
    is_bull = role == AgentRole.BULL
    direction = Direction.LONG if is_bull else Direction.SHORT
    return DirectionalCasePayload(
        role=role,
        direction=direction,
        thesis="独立方向论证",
        claims=[make_claim(packet, role.value)],
        adverse_evidence=[
            EvidenceRef(
                evidence_id=packet.items[0].evidence_id,
                interpretation="主动承认反向风险",
            )
        ],
        weakest_point="仍需触发确认",
        scenario=TradeScenario(
            direction=direction,
            entry_zone=PriceZone(
                lower=Decimal("63000") if is_bull else Decimal("64000"),
                upper=Decimal("63100") if is_bull else Decimal("64100"),
            ),
            trigger="15m 收盘确认",
            stop_loss=Decimal("62500") if is_bull else Decimal("64600"),
            take_profits=[Decimal("64000")] if is_bull else [Decimal("63000")],
            risk_reward=Decimal("1.6"),
            invalidation="结构反向破坏",
            valid_until=datetime.now(UTC) + timedelta(hours=2),
        ),
        suggested_grade=Grade.B,
    )


class 字段校验测试(unittest.TestCase):
    def test_异常成交量只标为辅助错误(self):
        metrics, issues = validate_volume_fields(
            current_volume=661,
            average_volume=0,
            volume_ratio=1,
            source="TradingView.volume_confirmation_analysis",
        )
        self.assertIsNone(metrics)
        self.assertEqual(issues[0].scope, ErrorScope.AUXILIARY)
        self.assertEqual(issues[0].severity, ErrorSeverity.WARN)

    def test_合法原始成交量通过(self):
        metrics, issues = validate_volume_fields(
            current_volume="5328.647",
            average_volume="6177.5219",
            volume_ratio="0.86259",
            source="Binance raw kline",
        )
        self.assertIsNotNone(metrics)
        self.assertEqual(issues, [])

    def test_核心阻断错误强制评级为D(self):
        issue = PipelineIssue(
            code="INVALID_1H_OHLC",
            scope=ErrorScope.CORE,
            severity=ErrorSeverity.BLOCK,
            source="Binance raw kline",
            field="1h.high",
            message="High 低于 Low",
        )
        self.assertEqual(deterministic_final_grade(Grade.A, issues=[issue]), Grade.D)

    def test_复核不得升级(self):
        review = ReviewPayload(
            reviewer="reviewer",
            available=True,
            verdict=ReviewVerdict.CONFIRM,
        )
        self.assertEqual(deterministic_final_grade(Grade.C, reviews=[review]), Grade.C)

    def test_旧证据包被拒绝(self):
        old_packet = make_packet(1)
        new_packet = make_packet(2)
        artifact = wrap_stage(
            old_packet,
            Stage.INITIAL_ANALYSIS,
            InitialAnalysisPayload(
                market_regime="RANGE",
                neutral_claims=[make_claim(old_packet, "old")],
            ),
        )
        with self.assertRaisesRegex(ValueError, "旧证据包"):
            assert_current_packet(artifact, new_packet)

    def test_可选依赖缺失只产生环境警告(self):
        issues = check_optional_skill_environment(
            "module_that_must_not_exist_for_sop_v35_test"
        )
        self.assertEqual(issues[0].scope, ErrorScope.ENVIRONMENT)
        self.assertEqual(issues[0].severity, ErrorSeverity.WARN)
        self.assertIsNone(issues[0].grade_cap)


class 多智能体编排测试(unittest.IsolatedAsyncioTestCase):
    async def test_多空独立且辩论不超过两轮(self):
        packet = make_packet()
        call_log = []

        async def initial(**kwargs):
            return InitialAnalysisPayload(
                market_regime="COMPRESSION",
                neutral_claims=[make_claim(kwargs["packet"], "initial")],
            )

        async def case_agent(**kwargs):
            self.assertNotIn("opponent_case", kwargs)
            call_log.append(("case", kwargs["role"]))
            return make_case(kwargs["packet"], kwargs["role"])

        async def rebuttal(**kwargs):
            role = kwargs["role"]
            own = kwargs["own_case"]
            opponent = kwargs["opponent_case"]
            call_log.append(("rebuttal", role, kwargs["round_no"]))
            return RebuttalPayload(
                round_no=kwargs["round_no"],
                responder=role,
                items=[
                    RebuttalItem(
                        target_claim_id=opponent.claims[0].claim_id,
                        verdict="PARTIAL",
                        evidence_refs=[
                            EvidenceRef(
                                evidence_id=kwargs["packet"].items[0].evidence_id,
                                interpretation="同一证据的对抗解释",
                            )
                        ],
                        response="证据不足以排除本方路径",
                    )
                ],
                revised_case=own,
                requests_another_round=True,
            )

        async def judge(**kwargs):
            return JudgePayload(
                preferred_direction=Direction.NEUTRAL,
                bull_candidate_grade=kwargs["bull_case"].suggested_grade,
                bear_candidate_grade=kwargs["bear_case"].suggested_grade,
                preliminary_grade=Grade.C,
                unresolved_disputes=["等待压缩突破"],
                preliminary_reason="方向尚未确认",
            )

        async def reviewer(**kwargs):
            return ReviewPayload(
                reviewer="test-reviewer",
                available=True,
                verdict=ReviewVerdict.CONFIRM,
            )

        result = await Orchestrator(
            AgentSet(
                initial=initial,
                bull=case_agent,
                bear=case_agent,
                rebuttal=rebuttal,
                judge=judge,
                reviewers=[reviewer],
            ),
            max_debate_rounds=2,
        ).run(packet)

        self.assertEqual(result.debate_rounds, 2)
        self.assertEqual(result.preliminary_grade, Grade.C)
        self.assertEqual(result.final_grade, Grade.C)
        self.assertCountEqual(
            [entry[1] for entry in call_log if entry[0] == "case"],
            [AgentRole.BULL, AgentRole.BEAR],
        )
        self.assertEqual(
            len([entry for entry in call_log if entry[0] == "rebuttal"]), 4
        )


if __name__ == "__main__":
    unittest.main()
