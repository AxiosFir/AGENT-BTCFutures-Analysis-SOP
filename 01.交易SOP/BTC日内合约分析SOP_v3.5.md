---
document_type: trading_sop
status: active
version: "3.5"
created: 2026-07-17
market: Binance USD-M Futures
symbols:
  - BTCUSDT
  - ETHUSDT
implementation_prototype: "[[../02.策略研究/BTC多智能体分析编排.py]]"
output_template: "[[../90.模板/BTC分析输出模板]]"
---

# BTC/ETH 日内合约分析 SOP v3.5

> [!success] 当前生效
> 本文档已确认为当前生效版本，执行入口以 [[../00.项目管理/当前生效版本|当前生效版本]] 为准。

## 0. 定位、边界与主流程

### 0.1 适用范围

- 标的：BTCUSDT、ETHUSDT。
- 市场：Binance USD-M 永续合约。
- 用途：日内分析、短线合约计划、入场前决策支持。
- 周期：1D、4H、1H、15m；1H 为主决策周期，15m 为执行周期。
- 核心数据：Binance 原始 K 线、Binance 合约数据、TradingView MCP。
- 辅助复核：TradingView 分析工具、cryptocurrency-trader skill。
- 本 SOP 只输出分析和计划，不自动下单，不代替用户作最终决策。

### 0.2 核心原则

1. 先统一获取数据，再按“验证 → 分析 → 辩论 → 复核 → 输出”顺序执行。
2. Binance 原始已收盘 K 线是 OHLC、ATR、均量和量比的核心事实源；TradingView 用于指标补充与交叉复核。
3. 正在形成的 K 线与已收盘 K 线必须分开，不得混合计算均量、结构或触发。
4. 每项判断必须引用当前 EvidencePacket 中的 evidence_id。
5. 多头和空头由两个独立代理生成初始观点，初始阶段互相看不到对方输出。
6. 裁判只能形成初步方向和初步评级；最终评级由确定性代码计算。
7. 复核只能维持或降低评级，不能直接升级。
8. 错误同时标记影响范围与严重性，辅助工具失败不得伪装成核心市场数据失败。
9. 评级仅使用 A、B、C、D；评级与 TRIGGERED、WAITING、INVALIDATED 分开。
10. 最终只向用户展示决策必要信息，完整过程保留在内部状态。

### 0.3 五阶段主流程

~~~text
1. 数据获取与字段级验证
2. 初步分析，并将同一证据包交给多空代理独立分析
3. 多空代理交叉辩论
4. 裁判初判、数据复核、独立复核、确定性评级
5. Pydantic 结构化输出与精简报告渲染
~~~

### 0.4 程序依赖与读取规则

1. 执行本 SOP 前，先完整读取一次 [[../02.策略研究/BTC多智能体分析编排.py|分析编排程序]]。
2. 后续各阶段按 SOP 调用程序中的对应功能，无须重复读取整个文件。
3. [[../02.策略研究/BTC多智能体分析编排测试.py|测试程序]]不参与日常分析，只在修改或验证分析编排程序时运行。
4. 进入第 5 阶段时读取 [[../90.模板/BTC分析输出模板|分析输出模板]]。

---

## 1. 第一阶段：数据获取与字段级验证

### 1.1 统一运行参数

| 参数 | 默认值 | 说明 |
|---|---:|---|
| SYMBOL | BTCUSDT 或 ETHUSDT | Binance 与 TradingView 使用 |
| QUALIFIED_SYMBOL | BINANCE:BTCUSDT 或 BINANCE:ETHUSDT | TradingView 部分工具必须使用 |
| KLINE_LIMIT | 210 | 足够计算 20 均量、ATR14 和近期结构 |
| EXEC_TF | 15m | 入场触发周期 |
| DECISION_TF | 1h | 主决策周期 |
| CONTEXT_TF | 4h | 背景约束周期 |
| BACKGROUND_TF | 1d | 大级别背景 |
| DERIVATIVE_PERIOD | 15m | 合约历史数据周期 |
| DERIVATIVE_LIMIT | 30 | 合约数据观察窗口 |
| BINANCE_BASE_URL | https://fapi.binance.com | Binance USD-M Futures |

每次运行由编排器生成并固定：

- analysis_id；
- batch_started_at；
- symbol；
- evidence_generation；
- 当前 UTC 与 America/New_York 时间；
- 接口超时、重试和刷新上限。

### 1.2 数据源与优先级

| 优先级 | 来源 | 用途 | 失败后的处理 |
|---|---|---|---|
| 核心 | Binance 原始已收盘 K 线 | OHLC、ATR、均量、量比、结构 | 15m/1H 刷新后仍失败则 D |
| 核心/辅助 | Binance 合约接口 | Funding、OI、多空比、主动买卖、盘口 | 按缺失范围降权或封顶 |
| 交叉来源 | TradingView `coin_analysis` | 指标、结构与关键区复核 | 不覆盖合法原始 K 线 |
| 辅助 | TradingView 复核工具 | 多周期、成交量、综合检查 | 单工具失败只禁用该模块 |
| 辅助 | cryptocurrency-trader | 独立逻辑与风险复核 | 不可用不自动降级 |

禁止为了补齐数据自动切换到口径不明的第三方来源。

### 1.3 Binance 原始 K 线接口

先取得 Binance 服务器时间：

~~~text
K00 GET {BINANCE_BASE_URL}/fapi/v1/time
~~~

四个 K 线请求可并行：

| ID | 周期 | 请求 |
|---|---|---|
| K01 | 15m | GET {BINANCE_BASE_URL}/fapi/v1/klines?symbol={SYMBOL}&interval=15m&limit={KLINE_LIMIT} |
| K02 | 1h | GET {BINANCE_BASE_URL}/fapi/v1/klines?symbol={SYMBOL}&interval=1h&limit={KLINE_LIMIT} |
| K03 | 4h | GET {BINANCE_BASE_URL}/fapi/v1/klines?symbol={SYMBOL}&interval=4h&limit={KLINE_LIMIT} |
| K04 | 1d | GET {BINANCE_BASE_URL}/fapi/v1/klines?symbol={SYMBOL}&interval=1d&limit={KLINE_LIMIT} |

Binance K 线数组字段：

| 索引 | 字段 |
|---:|---|
| 0 | open_time |
| 1 | open |
| 2 | high |
| 3 | low |
| 4 | close |
| 5 | base_volume |
| 6 | close_time |
| 7 | quote_volume |
| 8 | trade_count |
| 9 | taker_buy_base_volume |
| 10 | taker_buy_quote_volume |

只把 `close_time < server_time` 的记录放入 `closed_bars`。最后一根未收盘记录若存在，单独存为 `forming_bar`，不得用于确认触发或与已收盘历史均量直接比较。

统一派生值：

~~~text
average_volume_20 = 前 20 根已收盘 K 线成交量均值
volume_ratio = 最新已收盘 K 线成交量 / average_volume_20
ATR14 = 最新 14 根已收盘 K 线 True Range 均值
high_20 / low_20 = 最近 20 根已收盘 K 线的最高/最低
~~~

快速测试：

~~~powershell
python 02.策略研究/BTC多智能体分析编排.py --test-binance BTCUSDT
~~~

### 1.4 TradingView 数据获取

以下调用与 Binance 数据尽量并行：

~~~text
coin_analysis(symbol="{SYMBOL}", exchange="BINANCE", timeframe="15m")
coin_analysis(symbol="{SYMBOL}", exchange="BINANCE", timeframe="1h")
coin_analysis(symbol="{SYMBOL}", exchange="BINANCE", timeframe="4h")
coin_analysis(symbol="{SYMBOL}", exchange="BINANCE", timeframe="1d")
market_snapshot()
financial_news(symbol="{ASSET}", category="crypto", limit=10)
~~~

本阶段只提取价格、指标、关键区、时间戳、数据缺失和异常，不采用工具自带的 LONG、SHORT、BUY、SELL 作为结论。

### 1.5 Binance 合约接口

| ID | 数据 | 请求 |
|---|---|---|
| B01 | 当前 Funding、标记价、指数价 | GET `/fapi/v1/premiumIndex?symbol={SYMBOL}` |
| B02 | Funding 历史 | GET `/fapi/v1/fundingRate?symbol={SYMBOL}&limit=30` |
| B03 | 当前 OI | GET `/fapi/v1/openInterest?symbol={SYMBOL}` |
| B04 | OI 历史 | GET `/futures/data/openInterestHist?symbol={SYMBOL}&period={DERIVATIVE_PERIOD}&limit={DERIVATIVE_LIMIT}` |
| B05 | 全市场账户多空比 | GET `/futures/data/globalLongShortAccountRatio?symbol={SYMBOL}&period={DERIVATIVE_PERIOD}&limit={DERIVATIVE_LIMIT}` |
| B06 | 大户持仓多空比 | GET `/futures/data/topLongShortPositionRatio?symbol={SYMBOL}&period={DERIVATIVE_PERIOD}&limit={DERIVATIVE_LIMIT}` |
| B07 | 大户账户多空比 | GET `/futures/data/topLongShortAccountRatio?symbol={SYMBOL}&period={DERIVATIVE_PERIOD}&limit={DERIVATIVE_LIMIT}` |
| B08 | 主动买卖量比 | GET `/futures/data/takerlongshortRatio?symbol={SYMBOL}&period={DERIVATIVE_PERIOD}&limit={DERIVATIVE_LIMIT}` |
| B09 | 盘口深度 | GET `/fapi/v1/depth?symbol={SYMBOL}&limit=100` |

所有接口适配器统一返回：

~~~text
request_id, endpoint_id, requested_at, received_at,
http_status, data_status, payload, issues, retry_count
~~~

HTTP 418 立即停止；429 遵守 `Retry-After`；400 只允许修正参数一次；5xx 或超时指数退避，最多三次。空数组或缺失字段标记 MISSING，不得转换成 0。

### 1.6 字段级验证

#### K 线与指标

| 字段 | 规则 | 失败范围 |
|---|---|---|
| open/high/low/close | 均大于 0 | 15m/1H 为 CORE |
| OHLC 关系 | `high >= max(open, close, low)`；`low <= min(open, close, high)` | 对应周期错误 |
| open_time | 严格递增、不得重复 | 对应周期错误 |
| volume | 不得为负 | 对应来源异常 |
| average_volume_20 | 必须大于 0 | 成交量模块异常 |
| volume_ratio | 非负、有限，且与 `current/average` 一致 | 成交量模块异常 |
| ATR14 | 大于 0、有限 | 波动模块异常 |
| RSI | 0 至 100 | 指标来源异常 |
| Bollinger | 上轨高于中轨，中轨高于下轨 | 指标来源异常 |
| 时间戳 | 必须标明已收盘或正在形成 | 无法确认则不得用于触发 |

成交量不变量：

~~~text
若 current_volume > 0 且 average_volume <= 0 → ANOMALOUS
若 average_volume > 0 且 volume_ratio 与 current_volume / average_volume 偏差超限 → ANOMALOUS
若 average_volume = 0 且 volume_ratio = 1 → 必须报错，禁止解释为“正常量能”
~~~

默认容差为 `max(0.02, 计算量比 × 3%)`。原始 K 线计算合法时，TradingView 成交量工具异常只淘汰该工具结果，不淘汰成交量证据类别。

#### 跨来源验证

1. TradingView 价格与 Binance 标记价可存在合理基差，偏差阈值配置化并记录。
2. 1D 与 4H 若 OHLC 完全相同，先比较 open_time、close_time 和是否为形成中 K 线；无法解释则标记来源异常。
3. TradingView 与 Binance 发生冲突时，合法的 Binance 已收盘原始 K 线负责 OHLC 事实，TradingView 只保留为冲突记录。
4. OI 当前值与历史末值口径不同则不比较绝对值，只比较各自时间序列变化。
5. 新闻必须保留事件时间，不能只保留抓取时间。

### 1.7 错误分层与处理

错误使用两个相互独立的维度：

| 维度 | 枚举 | 含义 |
|---|---|---|
| 影响范围 | CORE | 会改变方向、触发、止损、R:R 或主要价格结构 |
| 影响范围 | AUXILIARY | 单项复核、情绪、盘口、辅助指标或低权重信息 |
| 影响范围 | ENVIRONMENT | 依赖缺失、编码、网络或工具运行环境问题 |
| 严重性 | WARN | 记录并排除无效字段，不直接降级 |
| 严重性 | DOWNGRADE | 设置评级上限或降一级 |
| 严重性 | BLOCK | 当前链路停止；CORE + BLOCK 直接 D 或刷新重跑 |

典型映射：

| 情况 | scope / severity | 处理 |
|---|---|---|
| 15m 或 1H 原始 K 线刷新后仍无效 | CORE / BLOCK | D |
| 4H 不可用 | CORE / DOWNGRADE | 最高 C |
| 1D 不可用 | AUXILIARY / WARN | 禁止判断日线关键区，不自动降级 |
| `average_volume=0, volume_ratio=1` | AUXILIARY / WARN | 禁用该工具的成交量结果 |
| 原始 K 线成交量也无效 | CORE / DOWNGRADE | 移除成交量证据，按剩余证据重评 |
| Funding 单项缺失 | AUXILIARY / WARN | 合约证据降权，不自动降级 |
| OI 当前与历史同时缺失 | CORE / DOWNGRADE | 最高 C |
| 盘口、情绪或独立复核工具不可用 | AUXILIARY 或 ENVIRONMENT / WARN | 保留其他结果，不自动 D |
| 入场/止损/止盈方向错误或 R:R < 1.5 | CORE / BLOCK | D |
| 代理三次仍无法通过 Schema | CORE / BLOCK | 辩论链不完整，D |
| 编排器内部异常 | ENVIRONMENT / BLOCK | 安全输出 D/NO_TRADE，标记 run_status=FAILED |

辅助错误不会自动触发 D。先排除受影响字段，再根据剩余有效证据和评级封顶规则计算。

### 1.8 EvidencePacket

验证通过的证据形成不可变 EvidencePacket：

~~~text
analysis_id, generation, packet_id, content_hash, created_at, items
~~~

每项 EvidenceItem 包含：

~~~text
evidence_id, source, timeframe, observed_at, data_status, value
~~~

刷新数据时必须创建 `generation + 1` 的新证据包，清空 InitialAnalysis 之后的全部产物。旧包只供审计，不再传给代理。

---

## 2. 第二阶段：初步分析与多空独立分析

### 2.1 中立初步分析

InitialAnalysis 只完成：

- 1D、4H、1H、15m 的结构与周期分工；
- 市场主状态：TREND、RANGE、COMPRESSION、DISORDERLY 四选一；
- 支撑、阻力、波动、动能、成交量和合约数据事实；
- 已确认事实与推断分离；
- 尚待多空代理解决的问题。

InitialAnalysis 不给最终方向，不给最终评级。

### 2.2 多空代理独立性

编排器并行启动：

~~~text
BullAgent(EvidencePacket, InitialAnalysis)
BearAgent(EvidencePacket, InitialAnalysis)
~~~

初始调用约束：

1. 两侧使用相同 `analysis_id`、`generation` 和 `content_hash`。
2. BullAgent 只论证 LONG，BearAgent 只论证 SHORT。
3. 初始调用不传入对方输出，提示词中也不得摘要对方观点。
4. 两侧都必须列出反向证据和自身最弱点。
5. 所有 Claim 必须引用 EvidencePacket；不得联网补充事实。
6. 无合法交易场景时允许主动给 D，不得为了完成任务强行造单。

### 2.3 内部 Pydantic 复用

不使用“所有字段均 Optional”的单一巨型模型。采用：

~~~text
共享组件：EvidenceRef、Claim、PriceZone、TradeScenario、PipelineIssue
多空共用：DirectionalCasePayload(role=BULL/BEAR)
阶段专用：InitialAnalysisPayload、RebuttalPayload、JudgePayload、ReviewPayload
统一信封：StageEnvelope[PayloadT]
最终投影：CompactAnalysisReport
~~~

LLM 只生成阶段 Payload。`analysis_id`、`stage`、`evidence_generation`、`evidence_hash`、`generated_at` 和 issues 由编排器填写，防止代理伪造批次或时间。

DirectionalCase 的跨字段校验必须保证：

- BULL 对应 LONG，BEAR 对应 SHORT；
- 场景方向与代理方向一致；
- LONG 止损低于入场区，止盈高于入场区；
- SHORT 止损高于入场区，止盈低于入场区；
- R:R 不低于 1.5；
- 没有场景时 suggested_grade 必须为 D。

---

## 3. 第三阶段：多空交叉辩论

### 3.1 辩论方式

独立立论完成后，双方获得：

- 同一 EvidencePacket；
- 自己的 DirectionalCase；
- 对方的 DirectionalCase；
- 当前轮次。

每个 RebuttalItem 必须指定 `target_claim_id`，并给出 ACCEPTED、PARTIAL、REJECTED 或 UNVERIFIED。除 UNVERIFIED 外必须引用当前证据。

### 3.2 必须逐条检查

1. 对方是否引用不存在或过期的 evidence_id；
2. 是否把事实和推断混在一起；
3. 是否忽略不利证据；
4. 触发、止损、止盈和失效条件是否方向正确；
5. R:R 是否复算一致；
6. 场景是否仍在有效期内；
7. 反驳是否真正导致计划字段变化。

### 3.3 轮次与停止条件

- 默认一轮，最多两轮。
- 只有同一证据存在相反解释、发现引用错误，或交易计划发生实质修改时进入第二轮。
- 达到两轮后强制停止，未解决分歧交给裁判。
- 若分歧涉及方向、触发或止损且无法收敛，最终为 D；非关键分歧最高 C。

---

## 4. 第四阶段：裁判、集中复核与确定性评级

### 4.1 裁判初判

裁判只能使用当前证据包和已校验的内部产物，输出：

- preferred_direction；
- bull_candidate_grade；
- bear_candidate_grade；
- preliminary_grade；
- agreed facts；
- unresolved disputes；
- review questions；
- preliminary reason。

裁判不得新增市场事实，不得把“辩论胜负”直接等同于可执行交易。

### 4.2 复核前刷新检查

出现下列任一情况，生成新证据包并从第 2 阶段完整重跑：

- 出现新的已收盘 15m K 线且会影响触发；
- 价格漂移超过 `max(0.25 × ATR15m, 0.3% × packet_price)`；
- 价格穿越入场、触发、止损或核心结构区；
- 发生新的重大事件；
- 合约数据变化足以改变拥挤或增减仓判断；
- 复核发现新的方向性市场事实。

不得把复核发现的新事实直接塞进旧结论。

### 4.3 集中复核

数据仍有效后，独立复核可并行：

~~~text
V01 multi_timeframe_analysis(symbol="{SYMBOL}", exchange="BINANCE")
V02 volume_confirmation_analysis(symbol="{QUALIFIED_SYMBOL}", exchange="BINANCE", timeframe="1h")
V03 multi_agent_analysis(symbol="{SYMBOL}", exchange="BINANCE", timeframe="1h")
V04 combined_analysis(symbol="{SYMBOL}", exchange="BINANCE", timeframe="1h")
V05 market_sentiment(symbol="{ASSET}", category="crypto", limit=20)  # 可选
~~~

其中 V02 必须通过 1.6 节成交量不变量后才能使用。未限定交易所的 `BTCUSDT` 不用于该工具，必须使用 `BINANCE:BTCUSDT` 或 `BINANCE:ETHUSDT`。

Binance 合约复核继续检查 Funding、Mark/Index 基差、OI、多空比、主动买卖量和盘口；盘口不作为独立方向证据。

cryptocurrency-trader 只提取数据异常、多周期冲突、方向逻辑、止损止盈方向、R:R、validation status、circuit breakers 和 execution_ready。忽略默认余额、2% 风险、confidence、Kelly、VaR/CVaR/Sharpe、Monte Carlo 仓位及其方向覆盖建议。

若 skill 缺少 `ccxt`、编码失败或 CLI 不可用，记录 ENVIRONMENT/WARN，不自动安装依赖，不自动降级。

### 4.4 程序化编排状态机

~~~text
FETCH_DATA → VALIDATE_DATA → BUILD_EVIDENCE → INITIAL_ANALYSIS
→ PARALLEL_CASES → CROSS_REBUTTAL → JUDGE
→ REFRESH_CHECK → EXTERNAL_REVIEW → APPLY_HARD_GATES
→ COMPUTE_FINAL_GRADE → VALIDATE_OUTPUT → COMPLETE
~~~

强制上限：

| 项目 | 上限 |
|---|---:|
| 单接口瞬时错误重试 | 3 次 |
| LLM Schema 修复 | 初次后最多 2 次 |
| 交叉辩论 | 2 轮 |
| 完整刷新重跑 | 2 次 |
| 状态转移 | 40 次 |
| 单次运行 | 建议 15 分钟 |

辅助工具失败必须捕获为规范化 issue，不得取消同组其他复核。只有核心 K 线链路在重试耗尽后才终止该批次。

### 4.5 六类证据与评级

六类证据：结构与趋势、动能、波动、价格位置、成交量、合约数据。同类指标只计一类；代理、裁判和复核意见不是新证据类别。

| 评级 | 必要条件 | 执行含义 | 单笔账户风险参考 |
|---|---|---|---|
| A | 硬门槛全部通过；5–6 类证据；1H 清晰；15m 已触发；合约数据支持；R:R ≥ 2 | 高质量可执行 | 1.0%–1.5% |
| B | 硬门槛通过；至少 4 类证据；轻微分歧；R:R ≥ 1.5 | 标准或条件执行 | 0.5%–1.0% |
| C | 硬门槛通过；至少 3 类证据；环境不确定或辅助数据不完整 | 轻仓或等待精确触发 | 0.25%–0.5% |
| D | 任一硬门槛失败、证据不足或风险冲突无法解决 | 观望 | 0 |

最终评级由代码取所有上限中的最低值：

~~~python
final_grade = min_grade(
    preliminary_grade,
    evidence_coverage_cap,
    data_quality_cap,
    timeframe_cap,
    review_cap,
    hard_gate_cap,
)
~~~

`CONFIRM` 与 `NEUTRAL` 维持初评；普通方向冲突至少降一级；影响触发、止损、R:R 或核心结构的冲突直接 D。任何复核建议都不得调用升级函数。

### 4.6 硬性门槛

以下任一条件最终为 D：

1. 15m 或 1H 核心价格数据无效；
2. 1H 结构无法识别；
3. 没有可验证的入场触发定义；
4. 没有结构止损、逻辑失效条件或有效期；
5. R:R 小于 1.5 或复算不一致；
6. 支持证据不超过 2 类；
7. 多周期严重冲突且无确认结构；
8. 重大事件刚发生且方向未确认；
9. 关键数据异常无法解释；
10. 流动性或价差异常；
11. 达到个人停手规则；
12. 核心代理链路 Schema 校验持续失败；
13. 旧 evidence_generation 或 evidence_hash 被引用。

“已定义触发但尚未发生”可以是 A/B/C + WAITING；“根本没有明确触发定义”必须为 D。

---

## 5. 第五阶段：结构化输出与精简展示

### 5.1 内部输出

内部保留：

- RawDataBatch 与 DataValidationReport；
- EvidencePacket 各 generation；
- InitialAnalysisPayload；
- Bull/Bear DirectionalCasePayload；
- 各轮 RebuttalPayload；
- JudgePayload；
- ReviewPayload；
- PipelineIssue 与 grade_change_log；
- run_status、状态转移记录和重试次数。

每个阶段由 `StageEnvelope[PayloadT]` 包装。完整 Pydantic v2 契约和可运行的多智能体编排原型见 [[../02.策略研究/BTC多智能体分析编排.py]]。当前原型直接接收已验证 EvidencePacket；数据提供器接入和完整刷新循环按 4.4 节接口继续封装。

### 5.2 用户可见输出

最终报告使用 [[../90.模板/BTC分析输出模板|BTC 分析输出模板]]。该模板只负责用户可见展示，不改变程序内部数据模型、校验规则或评级逻辑。

使用：

~~~python
report.model_dump(mode="json", exclude_none=True)
~~~

根据最终 action 选择 EXECUTE、WAIT_TRIGGER 或 NO_TRADE 模板，只展示对应字段。

---

## 附录

- [[附录/附录A-程序原型与测试说明|附录 A：程序原型与测试]]
- [[附录/附录B-v3.5变更摘要|附录 B：v3.5 变更摘要]]
