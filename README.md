# AGENT-BTCFutures-Analysis-SOP

## 中文

这是一个面向 BTC 日内合约分析的 AI 辅助交易 SOP 知识库，用于配合 Codex / AI Agent 完成行情研判、交易计划、风险控制和复盘迭代。

当前生效版本见：

- `00.项目管理/当前生效版本.md`
- `01.交易SOP/BTC日内合约分析SOP_v3.5.md`

使用时，先读取 `当前生效版本.md`，再按其中指定的 SOP 执行分析。策略研究、历史版本和归档内容只作为参考，不自动替代当前生效 SOP。

## v3.5 主要特征

v3.5 将单一分析流程升级为更结构化的 AI Agent 协作流程：

- 多空双方独立分析：分别生成看多与看空路径，避免单一路径先入为主。
- 多轮辩论机制：多空观点可以互相反驳，由裁判层整理分歧与关键条件。
- 证据包校验：分析结论需要绑定行情、成交量、结构位置等证据引用。
- 评级约束：根据数据质量、结构确认度和风险条件限制最终评级。
- 复核机制：通过额外审查层检查结论是否过度自信、条件是否遗漏。
- 标准化输出：输出交易方向、入场区间、止损、止盈、失效条件和观望条件。

本项目适合与 Codex、TradingView MCP、Binance 合约数据接口等工具配合使用。

## 后续发展

后续计划将项目从单一 SOP 继续演进为更完整的 AI 交易分析工作流：

- SOP 模块化：将行情结构、合约数据、风险控制、多空辩论、评级与输出拆成可复用模块。
- 交易日志：建立标准化交易记录，用于沉淀入场、出场、仓位、滑点和执行偏差。
- 复盘体系：完善单笔复盘、日复盘、周复盘和月复盘，让交易结果反向校验 SOP。
- 经验学习：把复盘中重复出现的有效模式和失败模式沉淀为待验证经验，再逐步升级为已验证经验。
- Skill 打包：将成熟后的 SOP、模板和执行流程打包为 Codex skill，方便在不同任务中稳定调用。

## English

An AI-assisted BTC intraday futures analysis SOP knowledge base, designed to work with Codex / AI Agents for market analysis, trade planning, risk control, and review-driven iteration.

Current active version:

- `00.项目管理/当前生效版本.md`
- `01.交易SOP/BTC日内合约分析SOP_v3.5.md`

To use this project, first read `当前生效版本.md`, then follow the SOP specified there. Strategy research, historical versions, and archived files are for reference only and do not automatically replace the active SOP.

## Key Features in v3.5

Version 3.5 upgrades the original linear analysis workflow into a more structured AI Agent collaboration process:

- Independent bull/bear analysis: generates separate bullish and bearish scenarios to reduce single-path bias.
- Multi-round debate: bull and bear views can challenge each other, while a judge layer summarizes disputes and key conditions.
- Evidence-packet validation: conclusions are linked to evidence such as price action, volume, market structure, and key levels.
- Grading constraints: final ratings are constrained by data quality, structure confirmation, and risk conditions.
- Review mechanism: an additional review layer checks for overconfidence, missing conditions, and weak assumptions.
- Standardized output: produces trade direction, entry zone, stop loss, take profits, invalidation conditions, and wait-and-see conditions.

This project is designed to work with Codex, TradingView MCP, Binance futures data APIs, and related tools.

## Disclaimer

For personal research and workflow management only. Not financial advice.

## Roadmap

The project will continue evolving from a single SOP into a more complete AI trading analysis workflow:

- Modular SOP: split market structure, futures data, risk control, bull/bear debate, grading, and output into reusable modules.
- Trade logs: build standardized records for entries, exits, position sizing, slippage, and execution deviations.
- Review system: improve single-trade, daily, weekly, and monthly reviews so trading results can feed back into the SOP.
- Experience learning: turn recurring effective patterns and failure modes into pending experience, then gradually promote them into validated experience.
- Skill packaging: package the mature SOP, templates, and execution workflow as a Codex skill for stable reuse across tasks.
