---
document_type: sop_appendix
status: draft
created: 2026-07-17
applies_to: "[[../BTC日内合约分析SOP_v3.5]]"
---

# 附录 B：v3.5 变更摘要

相对 v3.4：

1. 新增 Binance 15m、1H、4H、1D 原始 K 线核心来源；
2. 明确已收盘 K 线与形成中 K 线分离；
3. 新增字段级校验和成交量不变量；
4. 将错误拆为 CORE、AUXILIARY、ENVIRONMENT，并独立记录严重性；
5. 用统一 DirectionalCase 复用多空模型，用 StageEnvelope 统一元数据；
6. 为初步分析、多空、反驳、裁判和复核分别设置严格 Payload；
7. 将多智能体流程改为有限状态、可重试、可刷新、可审计的程序化编排；
8. 最终评级改为确定性代码收口，保证复核不得升级；
9. 保持最终用户报告精简，隐藏非必要分析过程；
10. 保留 v3.4，不更新当前生效版本。
