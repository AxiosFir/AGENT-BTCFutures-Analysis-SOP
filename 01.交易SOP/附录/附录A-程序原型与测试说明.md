---
document_type: sop_appendix
status: draft
created: 2026-07-17
applies_to: "[[../BTC日内合约分析SOP_v3.5]]"
---

# 附录 A：程序原型与测试

原型文件：[[../../02.策略研究/BTC多智能体分析编排.py]]  
自动化测试：[[../../02.策略研究/BTC多智能体分析编排测试.py]]

## 2026-07-17 原型验证

- 7 个自动化测试全部通过；
- 验证成交量异常会被标为 AUXILIARY/WARN；
- 验证合法原始 K 线量比可通过；
- 验证 CORE/BLOCK 强制 D；
- 验证复核不能升级；
- 验证旧证据包被拒绝；
- 验证可选 skill 依赖缺失只产生 ENVIRONMENT/WARN；
- 验证多空初始调用互不可见、并行执行；
- 验证辩论最多两轮。

BTCUSDT 原始 K 线实测时，15m、1H、4H、1D 各取得 209 根已收盘记录，OHLC、ATR14、20 均量和量比均通过字段校验。
