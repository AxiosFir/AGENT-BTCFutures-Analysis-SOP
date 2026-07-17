---
document_type: trading_analysis_output_template
status: draft
created: 2026-07-17
applies_to: "[[../01.交易SOP/BTC日内合约分析SOP_v3.5]]"
---

# BTC 分析输出模板

> [!warning] 草稿状态
> 本模板与 SOP v3.5 配套，尚未成为当前生效模板。

## 使用规则

1. 只负责用户可见报告，不包含内部 Pydantic 模型、分析规则或评级逻辑。
2. 根据最终 action 只选择 EXECUTE、WAIT_TRIGGER、NO_TRADE 中的一种模板。
3. 最多展示 3 条核心理由、3 条主要风险和 3 条重新评估条件。
4. 使用 `exclude_none=True`，不显示空字段。

## EXECUTE

仅用于最终评级为 A、B 或 C，且触发状态为 TRIGGERED。

~~~text
{SYMBOL}｜{generated_at}｜数据：{data_status}

市场状态：{regime + modifiers}
优先方向：{LONG / SHORT}
最终评级：{A / B / C}
触发状态：TRIGGERED

核心理由：
1. {最多三条}

交易计划：
入场区：{entry_zone}
触发：{trigger}
止损：{stop_loss}
TP1 / TP2：{take_profits}
R:R：{risk_reward}
风险参考：{risk_reference}
有效期：{valid_until}
失效条件：{invalidation}

反向切换：{一条必要条件}
合约数据：{一句话}
独立复核：{一句话}
主要风险：{最多三条}
重新评估：{最多三条}
~~~

## WAIT_TRIGGER

仅用于已经定义候选计划，但触发尚未发生。不得使用“立即执行”措辞。

~~~text
{SYMBOL}｜{generated_at}｜数据：{data_status}

市场状态：{regime + modifiers}
候选方向：{LONG / SHORT}
候选评级：{A / B / C}
触发状态：WAITING

核心理由：
1. {最多三条}

候选计划：
关注入场区：{entry_zone}
等待触发：{trigger}
止损参考：{stop_loss}
TP1 / TP2：{take_profits}
R:R：{risk_reward}
有效期：{valid_until}
失效条件：{invalidation}

反向切换：{一条必要条件}
合约数据：{一句话}
独立复核：{一句话}
主要风险：{最多三条}
重新评估：{最多三条}
~~~

## NO_TRADE

仅用于最终评级为 D。不得显示无意义的入场、止损、止盈或仓位字段。

~~~text
{SYMBOL}｜{generated_at}｜数据：{data_status}

市场状态：{regime + modifiers}
优先方向：NEUTRAL
最终评级：D
结论：NO_TRADE

观望原因：
1. {最多三条}

核心冲突：{一句话}
主要风险：{最多三条}
重新分析条件：{最多三条}
~~~
