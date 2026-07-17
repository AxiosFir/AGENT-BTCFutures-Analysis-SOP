---
document_type: trading_sop
status: draft
version: "3.4"
created: 2026-07-17
market: Binance USD-M Futures
symbols:
  - BTCUSDT
  - ETHUSDT
supersedes: "[[BTC_ETH_日内合约分析SOP_v3.3_BinanceFutures]]"
---

# BTC/ETH 日内合约分析 SOP v3.4

> [!warning] 草稿状态
> 本文档状态为 draft，尚未替换 [[BTC_ETH_日内合约分析SOP_v3.3_BinanceFutures]]，不具有当前执行权。只有用户确认并更新 [[../00.项目管理/当前生效版本|当前生效版本]] 后才能生效。

## 0. 文档定位与核心原则

### 0.1 适用范围

- 交易标的：BTC/USDT、ETH/USDT。
- 市场：Binance USD-M 永续合约。
- 用途：日内分析、短线合约计划、入场前决策支持。
- 时间框架：1D、4H、1H、15m；1H 为主决策周期，15m 为执行周期。
- 核心工具：TradingView MCP、Binance 官方合约公开 API、cryptocurrency-trader skill。

### 0.2 职责边界

1. 本 SOP 只生成交易分析和计划，不自动下单，不代替用户作最终决策。
2. 禁止编造数据。缺失、过期、异常或冲突的数据必须明确标记。
3. 先验证数据，再分析市场；先建立多空路径，再形成优先方向。
4. 所有重要判断必须能够追溯到证据，不得只凭工具的自然语言结论。
5. 多头代理、空头代理、裁判和复核工具都不能覆盖硬性风险规则。
6. 最终评级只使用 A、B、C、D；不输出未经校准的置信度百分比。
7. 评级与触发状态分开：
   - 评级表示机会质量；
   - TRIGGERED、WAITING、INVALIDATED 表示执行状态。
8. 没有明确触发、止损、止盈、失效条件或有效期时，最终评级必须为 D。
9. 每次分析必须同时评估做多与做空，但最终报告只展示必要信息。
10. 对本文档的后续修改必须创建新版本，不得覆盖本文件。

### 0.3 五阶段主流程

~~~text
1. 数据获取与数据验证
2. 初步分析，并交给多空代理独立分析
3. 多空代理交叉辩论
4. 裁判初判、数据复核、独立复核、最终结论与评级
5. Pydantic 结构化输出与精简报告渲染
~~~

---

## 1. 第一阶段：数据获取与数据验证

### 1.1 统一参数

每次分析开始时先生成一份运行参数，后续所有工具复用，不临时改变符号或周期。

| 参数 | BTC 默认值 | ETH 默认值 | 说明 |
|---|---|---|---|
| ASSET | BTC | ETH | 新闻和情绪查询使用 |
| SYMBOL | BTCUSDT | ETHUSDT | TradingView 与 Binance 使用 |
| PAIR | BTC/USDT | ETH/USDT | cryptocurrency-trader 使用 |
| EXCHANGE | BINANCE | BINANCE | TradingView MCP 使用 |
| QUALIFIED_SYMBOL | BINANCE:BTCUSDT | BINANCE:ETHUSDT | 部分成交量工具使用 |
| EXEC_TF | 15m | 15m | 入场触发周期 |
| DECISION_TF | 1h | 1h | 主决策周期 |
| CONTEXT_TF | 4h | 4h | 背景约束周期 |
| BACKGROUND_TF | 1d | 1d | 弱背景周期 |
| DERIVATIVE_PERIOD | 15m | 15m | 合约历史数据周期 |
| DERIVATIVE_LIMIT | 30 | 30 | 约 7.5 小时的 15m 数据 |
| BINANCE_BASE_URL | https://fapi.binance.com | 同左 | USD-M Futures 基础地址 |

运行开始时还必须记录：

- analysis_id；
- batch_started_at；
- 当前 UTC 时间；
- America/New_York 当地时间；
- 用户账户权益，未提供时标记为 UNKNOWN；
- 当前交易标的。

### 1.2 调用原则

1. 数据获取类调用尽量并行，减少时间戳漂移。
2. 分析、辩论和复核类调用按阶段顺序执行。
3. 获取阶段只收集结果，不直接采用工具自带的最终方向。
4. 每项数据单独记录状态，不得因一个接口失败而把整组数据标记为缺失。
5. 任何工具返回值都必须保留来源、时间周期和获取时间。
6. 同一轮分析只使用同一个 SYMBOL、EXCHANGE 和数据批次。

### 1.3 TradingView MCP：基础数据调用

#### 必需调用

以下四个调用可并行执行：

~~~text
coin_analysis(symbol="{SYMBOL}", exchange="{EXCHANGE}", timeframe="15m")
coin_analysis(symbol="{SYMBOL}", exchange="{EXCHANGE}", timeframe="1h")
coin_analysis(symbol="{SYMBOL}", exchange="{EXCHANGE}", timeframe="4h")
coin_analysis(symbol="{SYMBOL}", exchange="{EXCHANGE}", timeframe="1d")
~~~

#### 背景调用

以下调用可与基础数据并行：

~~~text
market_snapshot()
financial_news(symbol="{ASSET}", category="crypto", limit=10)
~~~

#### 获取阶段提取字段

即使 coin_analysis 返回方向结论，本阶段也只提取：

- 当前价格与时间戳；
- OHLC、成交量及近期结构演变；
- EMA、RSI、MACD、ADX、ATR、布林带、Stochastic；
- 前高、前低、支撑、阻力、VWAP、Pivot；
- 工具返回的数据缺失与异常说明。

工具生成的 LONG、SHORT、BUY、SELL 等结论暂不进入最终决策。

### 1.4 Binance 合约数据：统一请求清单

以下请求使用同一 SYMBOL、PERIOD 和 LIMIT。除盘口外均可并行。

| ID | 数据 | 可直接替换参数的请求 |
|---|---|---|
| B01 | 当前 Funding、标记价、指数价 | GET {BINANCE_BASE_URL}/fapi/v1/premiumIndex?symbol={SYMBOL} |
| B02 | Funding 历史 | GET {BINANCE_BASE_URL}/fapi/v1/fundingRate?symbol={SYMBOL}&limit=30 |
| B03 | 当前 OI | GET {BINANCE_BASE_URL}/fapi/v1/openInterest?symbol={SYMBOL} |
| B04 | OI 历史 | GET {BINANCE_BASE_URL}/futures/data/openInterestHist?symbol={SYMBOL}&period={DERIVATIVE_PERIOD}&limit={DERIVATIVE_LIMIT} |
| B05 | 全市场账户多空比 | GET {BINANCE_BASE_URL}/futures/data/globalLongShortAccountRatio?symbol={SYMBOL}&period={DERIVATIVE_PERIOD}&limit={DERIVATIVE_LIMIT} |
| B06 | 大户持仓多空比 | GET {BINANCE_BASE_URL}/futures/data/topLongShortPositionRatio?symbol={SYMBOL}&period={DERIVATIVE_PERIOD}&limit={DERIVATIVE_LIMIT} |
| B07 | 大户账户多空比 | GET {BINANCE_BASE_URL}/futures/data/topLongShortAccountRatio?symbol={SYMBOL}&period={DERIVATIVE_PERIOD}&limit={DERIVATIVE_LIMIT} |
| B08 | 主动买卖量比 | GET {BINANCE_BASE_URL}/futures/data/takerlongshortRatio?symbol={SYMBOL}&period={DERIVATIVE_PERIOD}&limit={DERIVATIVE_LIMIT} |
| B09 | 盘口深度 | GET {BINANCE_BASE_URL}/fapi/v1/depth?symbol={SYMBOL}&limit=100 |

#### 快速复制模板

BTC：

~~~text
https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT
https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&limit=30
https://fapi.binance.com/fapi/v1/openInterest?symbol=BTCUSDT
https://fapi.binance.com/futures/data/openInterestHist?symbol=BTCUSDT&period=15m&limit=30
https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol=BTCUSDT&period=15m&limit=30
https://fapi.binance.com/futures/data/topLongShortPositionRatio?symbol=BTCUSDT&period=15m&limit=30
https://fapi.binance.com/futures/data/topLongShortAccountRatio?symbol=BTCUSDT&period=15m&limit=30
https://fapi.binance.com/futures/data/takerlongshortRatio?symbol=BTCUSDT&period=15m&limit=30
https://fapi.binance.com/fapi/v1/depth?symbol=BTCUSDT&limit=100
~~~

ETH：将 BTCUSDT 统一替换为 ETHUSDT。

#### Binance 请求失败处理

为便于自动化封装，所有 Binance 请求统一返回：

- request_id；
- endpoint_id；
- requested_at；
- http_status；
- data_status；
- payload；
- error_message。

推荐失败处理：

| 情况 | 处理 |
|---|---|
| HTTP 200 且字段完整 | 标记 VALID |
| HTTP 200 但返回空数组或缺少关键字段 | 标记 MISSING，不得当作 0 |
| HTTP 400 或参数错误 | 检查 SYMBOL、PERIOD、LIMIT；修正一次后停止重试 |
| HTTP 418 | 立即停止请求，禁止继续重试 |
| HTTP 429 | 读取 Retry-After，退避后再请求 |
| HTTP 451 | 视为地区或访问限制，不重复请求；改用已有 MCP/API 封装 |
| HTTP 5xx 或网络超时 | 指数退避，最多重试 3 次 |
| JSON 解析失败 | 标记 ANOMALOUS，保留原始错误 |

统一降级顺序：

~~~text
Binance 官方公开 API
→ 已有 Binance MCP/API 封装
→ 单项标记 MISSING
→ 按 1.7 节执行评级降级
~~~

不得为了补齐数据而自动切换到口径不明的第三方来源。

### 1.5 数据状态

每项数据必须独立标记：

| 状态 | 含义 | 处理 |
|---|---|---|
| VALID | 字段完整、时间有效、逻辑正常 | 可进入证据包 |
| STALE | 数据时间超过对应周期允许范围 | 不作方向证据，必要时刷新 |
| MISSING | 接口失败或字段缺失 | 保留缺失项，不得补写 |
| ANOMALOUS | 数值异常、冻结或逻辑错误 | 暂停使用并复核 |
| CONFLICTING | 与同时间窗口的其他来源严重不一致 | 标记冲突，进入第 4 阶段复核 |

### 1.6 数据验证规则

#### 基础完整性

- 价格必须大于 0。
- High 必须不低于 Open、Close 和 Low。
- Low 必须不高于 Open、Close 和 High。
- 成交量不得为负。
- RSI 必须位于 0 至 100。
- ATR 必须大于 0。
- 布林带上轨必须高于下轨。
- 不得把缺失值、默认值或示例值当作市场事实。

#### 时间一致性

- 数据获取总耗时超过 5 分钟时，第 4 阶段必须检查是否需要刷新。
- 15m 和 1H 数据必须包含最新已收盘 K 线或明确标记正在形成的 K 线。
- 合约历史数据最新时间不得明显早于分析批次。
- 新闻必须记录发生时间，不得只记录抓取时间。
- 无法取得数据时间戳时，状态标记为时间未验证。

#### 来源一致性

- TradingView 当前价格与 Binance 标记价允许存在合理基差，但明显偏离必须解释。
- OI 当前值与 OI 历史末值口径不同时，不直接比较绝对数值，只比较各自时间序列变化。
- 盘口只使用当前快照，不作为独立方向证据。

### 1.7 数据缺失与降级

| 缺失情况 | 处理 |
|---|---|
| 1H 或 15m 核心价格结构不可用 | 直接 D |
| 4H 不可用 | 最高 C |
| 1D 不可用 | 标记背景缺失；不自动降级，但不得判断日线关键区 |
| Funding 单项缺失 | 合约证据降权，不自动 D |
| OI 当前和历史同时缺失 | 合约证据不完整，最高 C |
| 多空比或盘口单项缺失 | 逐项标记，不连带其他接口 |
| Binance 合约数据整体不可用 | 技术结构强时最高 C，否则 D |
| 新闻接口不可用 | 标记事件风险未验证；重大事件窗口内最高 C |
| cryptocurrency-trader 不可用 | 标记独立复核缺失，不自动降级 |

### 1.8 证据包

验证后的数据形成不可变 EvidencePacket。每项证据包含：

- evidence_id；
- source；
- timeframe；
- observed_at；
- value；
- data_status；
- evidence_type；
- raw_description；
- normalized_interpretation。

证据 ID 建议格式：

~~~text
TV-1H-STRUCTURE-001
TV-15M-VOLUME-002
BN-FUNDING-003
BN-OI-004
NEWS-MACRO-005
~~~

后续分析只允许引用 EvidencePacket 中的证据。新增或刷新数据必须生成新批次或修订版证据包。

---

## 2. 第二阶段：初步分析与多空代理独立分析

### 2.1 初步分析的职责

主分析器基于 EvidencePacket 生成中立的 InitialAnalysis，负责整理事实和问题，不负责给出最终评级。

InitialAnalysis 必须包含：

1. 当前交易时段与事件风险；
2. 主市场状态；
3. 市场修正标签；
4. 1D 关键区影响；
5. 4H 背景与结构边界；
6. 1H 主结构；
7. 15m 当前执行结构；
8. 上方 1 至 2 个核心阻力区；
9. 下方 1 至 2 个核心支撑区；
10. 当前均衡区；
11. 成交量和合约数据摘要；
12. 需要多空代理解决的分歧。

如保留初步倾向，必须写成“可反驳假设”，不得包含 A/B/C/D 最终评级。

### 2.2 时间框架分工

| 周期 | 作用 | 不得替代 |
|---|---|---|
| 1D | 大级别关键区和极端位置背景 | 不直接决定日内方向 |
| 4H | 趋势背景、结构边界、目标上限 | 不单独否决 1H 反转 |
| 1H | 日内方向、结构和候选计划 | 不替代 15m 触发 |
| 15m | 入场触发、取消、止损定位 | 不单独定义大级别目标 |

### 2.3 市场状态

#### 主状态：只能选择一个

- TREND：趋势。
- RANGE：区间。
- COMPRESSION：波动压缩。
- DISORDERLY：无序高波动。

#### 修正标签：可以多选

- NEWS_DRIVEN：新闻驱动。
- FALSE_BREAK：假突破或扫损。
- LIQUIDITY_RISK：流动性异常。
- LONG_CROWDING：多头拥挤。
- SHORT_CROWDING：空头拥挤。
- DAILY_KEY_ZONE：位于日线关键区。

### 2.4 支撑阻力规则

- 必须用区间表达，不只写单点。
- 核心交易位必须具有结构来源并服务于入场、止损、止盈或失效判断。
- 距离当前价格过近、无法支持 R:R 的位置降级为观察位。
- 上方最多保留 2 个核心阻力区，下方最多保留 2 个核心支撑区。
- 当前价格位于区间中部时，不得因轻微指标共振追单。

### 2.5 多头代理

多头代理接收相同的 EvidencePacket 和 InitialAnalysis，独立输出 BullCase：

- thesis：多头核心论点；
- conditions：多头成立条件；
- evidence_refs：支持证据 ID；
- adverse_evidence：对多头不利的证据；
- weakest_point：最弱环节；
- entry_zone：候选入场区；
- trigger：15m 入场触发；
- stop_loss：结构止损；
- targets：TP1、TP2；
- risk_reward：R:R；
- invalidation：逻辑失效；
- cancellation：入场前取消条件；
- valid_until：有效期；
- suggested_grade：初步评级建议。

### 2.6 空头代理

空头代理使用相同字段生成 BearCase。两个代理初始分析时互相看不到对方的输出。

### 2.7 独立分析约束

1. 不得使用 EvidencePacket 以外的市场事实。
2. 每个核心论点必须引用 evidence_id。
3. 推断必须明确标记为推断。
4. 必须主动列出对自身不利的证据。
5. 不得因为承担多头或空头角色而强行生成交易。
6. 证据不足时可以主动建议 D。
7. 合约数据只能确认、削弱或否决方向，不能单独创造方向。
8. 指标同类信息不得重复计分。

---

## 3. 第三阶段：多空代理交叉辩论

### 3.1 辩论输入

多头代理获得 BearCase，空头代理获得 BullCase。只交换结构化结论、证据、计划和风险，不要求输出或交换模型内部思维过程。

### 3.2 逐条反驳

每个代理必须对对方的核心论点逐条回应：

| 状态 | 含义 |
|---|---|
| ACCEPTED | 对方论点成立 |
| PARTIAL | 部分成立 |
| REJECTED | 证据不支持或解释错误 |
| UNVERIFIED | 当前证据无法验证 |

每条 RebuttalItem 包含：

- rebuttal_id；
- target_claim_id；
- verdict；
- evidence_refs；
- response_summary；
- impact_on_own_case；
- plan_changed；
- revised_fields。

### 3.3 辩论轮次

- 默认 1 轮正式交叉反驳。
- 仅在证据解释完全相反、引用错误或计划发生实质变化时增加第 2 轮。
- 最多 2 轮；仍无法解决的分歧交给裁判。

### 3.4 辩论后定稿

多头和空头分别提交最终版本，形成 DebateResult：

- bull_final_case；
- bear_final_case；
- agreed_facts；
- unresolved_disputes；
- bull_weaknesses；
- bear_weaknesses。

双方都可以撤回原计划并建议观望。

---

## 4. 第四阶段：初步结论、集中复核、最终结论与评级

### 4.1 裁判初判

裁判只使用：

- EvidencePacket；
- InitialAnalysis；
- BullCase；
- BearCase；
- RebuttalItems；
- DebateResult；
- 本 SOP 的硬性规则。

裁判不得新增市场事实，不得把辩论胜负直接等同于可执行交易。

JudgePreliminaryDecision 包含：

- bull_quality；
- bear_quality；
- agreed_facts；
- unresolved_disputes；
- preferred_direction；
- bull_candidate_grade；
- bear_candidate_grade；
- preliminary_grade；
- review_questions；
- preliminary_reason。

允许的初判：

- LONG 优先；
- SHORT 优先；
- 双向等待；
- NO_TRADE。

### 4.2 数据复核

在调用分析复核工具前先检查：

1. 数据是否因分析耗时而过期；
2. evidence_id 是否存在且引用正确；
3. 关键价格是否前后一致；
4. 入场、止损、止盈的方向关系是否正确；
5. R:R 是否计算正确；
6. 支撑阻力区是否被错误引用；
7. 新闻或合约数据是否在辩论期间发生重大变化。

若关键数据已经过期，刷新对应数据并更新 EvidencePacket。若刷新结果改变方向证据，返回第 2 阶段；不得在第 4 阶段直接改方向。

### 4.3 TradingView MCP：复核调用

按下列顺序调用，便于定位分歧来源：

#### V01 多周期复核

~~~text
multi_timeframe_analysis(symbol="{SYMBOL}", exchange="{EXCHANGE}")
~~~

检查：

- 1H 主结构是否被 4H 背景严重限制；
- 15m 是否真正形成触发；
- 多周期冲突是否已被多空代理解释。

#### V02 成交量复核

~~~text
volume_confirmation_analysis(
  symbol="{QUALIFIED_SYMBOL}",
  exchange="{EXCHANGE}",
  timeframe="1h"
)
~~~

必要时补充 15m。成交量只确认价格结构，不独立产生方向。

#### V03 多代理复核

~~~text
multi_agent_analysis(
  symbol="{SYMBOL}",
  exchange="{EXCHANGE}",
  timeframe="1h"
)
~~~

该工具属于外部复核，不等同于第 2、3 阶段的多空对抗辩论。

#### V04 综合复核

~~~text
combined_analysis(
  symbol="{SYMBOL}",
  exchange="{EXCHANGE}",
  timeframe="1h"
)
~~~

用于检查技术、新闻和情绪之间是否存在未处理的重大冲突。

#### V05 情绪复核：可选

~~~text
market_sentiment(symbol="{ASSET}", category="crypto", limit=20)
~~~

情绪仅为低权重信息，不加入六类证据计分。

### 4.4 Binance 合约数据复核

对 B01 至 B09 的结果作统一解释：

| 模块 | 重点检查 | 允许作用 |
|---|---|---|
| Funding | 当前值、历史位置、是否拥挤 | 确认或降权 |
| Mark 与 Index | 基差是否异常 | 流动性和拥挤风险 |
| OI | 固定窗口内增仓、减仓或平稳 | 验证价格推动类型 |
| 多空比 | 全市场与大户是否拥挤 | 识别挤压风险 |
| 主动买卖量 | 买卖主动性是否持续 | 验证短线方向 |
| 盘口深度 | 压单、承接、价差和撤单 | 仅作短时辅助 |

OI 与价格的基础解释：

| 价格 | OI | 常见含义 | 使用限制 |
|---|---|---|---|
| 上涨 | 增加 | 新仓推动，趋势可能延续 | 同时检查多头拥挤 |
| 上涨 | 下降 | 空头回补或减仓上涨 | 不宜过度追多 |
| 下跌 | 增加 | 新空或激烈换手 | 同时检查空头拥挤 |
| 下跌 | 下降 | 多头平仓或止损 | 可能接近释放尾声 |

盘口快照容易撤单或伪装，不能单独确认交易。

### 4.5 cryptocurrency-trader 独立复核

#### 定位

cryptocurrency-trader 只承担独立校验，不作为主要数据源，不覆盖 TradingView 价格结构和 Binance 合约数据。

#### 推荐调用

~~~text
python skill.py analyze {PAIR} --balance 10000
~~~

若已提供实际账户，可替换 balance；但本 SOP 不采用 skill 的仓位结果。无法直接运行 CLI 时，通过可用的 skill 调用入口执行同等分析。

#### 只提取

- 数据完整性与异常；
- 15m、1H、4H 多周期冲突；
- LONG 或 SHORT 价格逻辑；
- 止损与止盈方向；
- R:R 复算；
- validation status；
- circuit breakers；
- execution_ready。

#### 明确忽略

- 默认 2% 风险；
- 默认账户余额；
- confidence 百分比；
- Kelly 仓位；
- VaR、CVaR、Sharpe、Monte Carlo 作为硬条件；
- 自动生成的仓位和手续费；
- skill 方向对裁判结论的直接覆盖。

### 4.6 统一复核结论

所有复核结果统一映射为：

| 结论 | 处理 |
|---|---|
| CONFIRM | 维持初步评级 |
| NEUTRAL | 不加分、不降级 |
| CONFLICT | 至少降一级，或退回等待触发 |
| HARD_ERROR | 直接 D |

复核工具原则上不能直接升级评级。若复核发现新的有效证据：

1. 写入新的 EvidencePacket；
2. 返回第 2 阶段重新分析；
3. 必要时重新进行交叉辩论；
4. 重新由裁判初判。

### 4.7 六类证据

同类指标只计一类，避免重复确认：

1. 结构与趋势；
2. 动能；
3. 波动；
4. 价格位置；
5. 成交量；
6. 合约数据。

多代理观点、裁判意见和 cryptocurrency-trader 结果不构成新的证据类别。

### 4.8 A/B/C/D 最终评级

评级必须在硬性门槛检查之后执行。

| 评级 | 必要条件 | 执行含义 | 单笔账户风险参考 |
|---|---|---|---|
| A | 硬门槛全部通过；5 至 6 类证据；1H 清晰；15m 已触发；合约数据支持；R:R 不低于 2 | 高质量可执行 | 1.0% 至 1.5% |
| B | 硬门槛全部通过；至少 4 类证据；存在轻微分歧；R:R 不低于 1.5 | 标准或条件执行 | 0.5% 至 1.0% |
| C | 硬门槛通过；至少 3 类证据；逆 4H、环境不确定或关键辅助数据不完整 | 轻仓或等待精确触发 | 0.25% 至 0.5% |
| D | 任一硬门槛失败、证据不足或风险冲突无法解决 | 观望 | 0 |

补充规则：

- 逆 4H 最高为 B。
- 逆 4H 同时叠加另一项明显风险时，最高为 C。
- Binance 合约数据整体缺失时，最高为 C。
- A、B、C 处于 WAITING 时不得提前入场。
- D 即使出现表面触发也不得执行。

### 4.9 硬性禁止规则

以下任一条件出现，最终评级必须为 D：

1. 1H 或 15m 核心价格数据无效；
2. 1H 结构无法识别；
3. 没有明确入场触发；
4. 没有结构止损；
5. 没有逻辑失效条件；
6. 没有信号有效期；
7. R:R 小于 1.5；
8. 支持证据不超过 2 类；
9. 4H、1H、15m 严重冲突且无明确反转结构；
10. 重大新闻刚发生且方向尚未确认；
11. 关键数据异常无法解释；
12. 流动性差或价差异常扩大；
13. 达到连续亏损或单日停手规则；
14. 复核发现 HARD_ERROR。

### 4.10 入场触发、取消与有效期

#### 常用触发

| 类型 | LONG | SHORT |
|---|---|---|
| 回踩确认 | 回踩支撑区后 15m 收回，成交量不明显萎缩 | 反抽阻力区后 15m 收回，成交量不明显萎缩 |
| 突破确认 | 15m 放量收上阻力区，回踩不破 | 15m 放量收下支撑区，反抽不过 |
| 假突破 | 跌破支撑后快速收回并站稳 | 突破阻力后快速跌回并受压 |
| 合约确认 | OI、主动买盘或承接支持 | OI、主动卖盘或压制支持 |

#### 取消条件

- 入场前价格已经触及主要 TP 区；
- 15m 收盘反向破坏关键结构；
- 合约数据突然极端变化并与计划冲突；
- 重大新闻出现且影响不确定；
- 信号超过有效期；
- 关键数据刷新后原证据失效。

#### 有效期

| 基础 | 市场状态 | 默认有效期 |
|---|---|---|
| 15m 触发 | 趋势 | 2 至 4 根 15m K 线 |
| 15m 触发 | 区间、压缩或高波动 | 1 至 2 根 15m K 线 |
| 1H 候选计划 | 任意 | 1 至 2 根 1H K 线 |
| 4H 背景 | 任意 | 当日或下一根 4H K 线前 |

---

## 5. 第五阶段：Pydantic 结构化输出与精简展示

### 5.1 双层结构

分析过程和用户可见结果分离：

#### InternalAnalysisState：内部使用

保留：

- EvidencePacket；
- DataValidationReport；
- InitialAnalysis；
- BullCase；
- BearCase；
- RebuttalItems；
- DebateResult；
- JudgePreliminaryDecision；
- ExternalReviewReport；
- grade_change_log。

内部结构用于审计、排错和重跑，默认不渲染给用户。

#### CompactAnalysisReport：用户可见

只展示：

- 基本信息；
- 市场摘要；
- 最终方向、评级和触发状态；
- 最多 3 条核心理由；
- 优先交易计划；
- 反向切换条件；
- 合约数据结论；
- 独立复核结论；
- 最多 3 条主要风险；
- 重新评估条件。

### 5.2 最终输出模型

以下为 Pydantic v2 草案。实际实现时可拆分到独立代码文件，SOP 只保留字段契约。

~~~python
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class TriggerStatus(str, Enum):
    TRIGGERED = "TRIGGERED"
    WAITING = "WAITING"
    INVALIDATED = "INVALIDATED"


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
    HARD_ERROR = "HARD_ERROR"


class MarketRegime(str, Enum):
    TREND = "TREND"
    RANGE = "RANGE"
    COMPRESSION = "COMPRESSION"
    DISORDERLY = "DISORDERLY"


class PriceZone(StrictModel):
    lower: Decimal = Field(gt=0)
    upper: Decimal = Field(gt=0)

    @model_validator(mode="after")
    def validate_zone(self):
        if self.lower > self.upper:
            raise ValueError("价格区间下限不得高于上限")
        return self


class MarketSummary(StrictModel):
    regime: MarketRegime
    modifiers: list[str] = Field(default_factory=list, max_length=4)
    timeframe_summary: str
    event_risk: str | None = None


class TradePlan(StrictModel):
    direction: Literal[Direction.LONG, Direction.SHORT]
    grade: Literal[Grade.A, Grade.B, Grade.C]
    trigger_status: TriggerStatus
    entry_zone: PriceZone
    entry_reference: Decimal = Field(gt=0)
    trigger: str
    stop_loss: Decimal = Field(gt=0)
    take_profits: list[Decimal] = Field(min_length=1, max_length=2)
    risk_reward: Decimal = Field(ge=Decimal("1.5"))
    risk_percent_min: Decimal = Field(ge=0)
    risk_percent_max: Decimal = Field(ge=0)
    invalidation: str
    cancellation: list[str] = Field(min_length=1, max_length=3)
    valid_until: datetime

    @model_validator(mode="after")
    def validate_trade_logic(self):
        if self.risk_percent_min > self.risk_percent_max:
            raise ValueError("风险下限不得高于风险上限")

        if self.direction == Direction.LONG:
            if not self.stop_loss < self.entry_zone.lower:
                raise ValueError("LONG 止损必须低于入场区")
            if any(tp <= self.entry_zone.upper for tp in self.take_profits):
                raise ValueError("LONG 止盈必须高于入场区")

        if self.direction == Direction.SHORT:
            if not self.stop_loss > self.entry_zone.upper:
                raise ValueError("SHORT 止损必须高于入场区")
            if any(tp >= self.entry_zone.lower for tp in self.take_profits):
                raise ValueError("SHORT 止盈必须低于入场区")

        return self


class AlternativeScenario(StrictModel):
    direction: Direction
    grade: Grade
    switch_condition: str
    trigger: str | None = None
    main_risk: str


class ExecutableDecision(StrictModel):
    action: Literal["EXECUTE"]
    preferred_direction: Literal[Direction.LONG, Direction.SHORT]
    final_grade: Literal[Grade.A, Grade.B, Grade.C]
    trigger_status: Literal[TriggerStatus.TRIGGERED]
    core_reasons: list[str] = Field(min_length=1, max_length=3)
    primary_plan: TradePlan


class WaitingDecision(StrictModel):
    action: Literal["WAIT_TRIGGER"]
    preferred_direction: Direction
    final_grade: Literal[Grade.A, Grade.B, Grade.C]
    trigger_status: Literal[TriggerStatus.WAITING]
    core_reasons: list[str] = Field(min_length=1, max_length=3)
    candidate_plan: TradePlan
    waiting_for: str


class NoTradeDecision(StrictModel):
    action: Literal["NO_TRADE"]
    preferred_direction: Literal[Direction.NEUTRAL]
    final_grade: Literal[Grade.D]
    core_reasons: list[str] = Field(min_length=1, max_length=3)
    reanalysis_conditions: list[str] = Field(min_length=1, max_length=3)


FinalDecision = Annotated[
    ExecutableDecision | WaitingDecision | NoTradeDecision,
    Field(discriminator="action"),
]


class CompactAnalysisReport(StrictModel):
    schema_version: Literal["1.0"]
    analysis_id: str
    symbol: Literal["BTCUSDT", "ETHUSDT"]
    generated_at: datetime
    current_price: Decimal = Field(gt=0)
    data_status: DataStatus
    market: MarketSummary
    final_decision: FinalDecision
    alternative_scenario: AlternativeScenario | None = None
    derivatives_verdict: ReviewVerdict
    independent_review: ReviewVerdict
    key_risks: list[str] = Field(default_factory=list, max_length=3)
    warnings: list[str] = Field(default_factory=list, max_length=3)
~~~

输出时使用：

~~~python
payload = report.model_dump(mode="json", exclude_none=True)
~~~

未使用字段不得以空表格或空字符串展示。

### 5.3 条件化展示

#### EXECUTE

只在评级为 A、B、C，状态为 TRIGGERED，且所有硬门槛通过时使用。展示完整优先计划。

#### WAIT_TRIGGER

展示候选方向、评级、入场区、等待触发、失效条件和有效期；不得使用“立即执行”措辞。

#### NO_TRADE

评级必须为 D。只展示：

- 观望原因；
- 当前核心冲突；
- 重新分析条件。

不展示无意义的入场、止损、止盈和仓位空字段。

### 5.4 精简 Markdown 模板

~~~text
{SYMBOL}｜{generated_at}｜数据：{data_status}

市场状态：{market.regime + modifiers}
优先方向：{preferred_direction}
最终评级：{final_grade}
触发状态：{trigger_status 或 action}

核心理由：
1. {最多三条}

交易计划：仅 EXECUTE 或 WAIT_TRIGGER 展示
入场区：
触发：
止损：
TP1：
TP2：
R:R：
风险参考：
有效期：
失效条件：

反向路径：
评级：
方向切换条件：

合约数据：{derivatives_verdict + 一句话摘要}
独立复核：{independent_review + 一句话摘要}

主要风险：
1. {最多三条}
~~~

多空两边都具有实际交易价值时，可以完整展示两份计划；否则反向路径只展示评级和切换条件。

---

## 附录 A：风险与仓位

### A.1 仓位计算

仓位只作参考，不纳入手续费、滑点和交易规则调整：

~~~text
最大亏损金额 = 账户权益 × 单笔风险比例
价格风险 = |入场参考价 - 止损价|
合约数量 = 最大亏损金额 ÷ 价格风险
名义仓位 = 合约数量 × 入场参考价
所需杠杆 = 名义仓位 ÷ 可用保证金
~~~

用户未提供账户权益时：

- 不使用假设权益生成实际仓位；
- 只输出评级对应风险比例；
- 可以提供单位权益或百分比参考。

### A.2 杠杆

- 默认杠杆不超过 10x。
- 高波动、新闻驱动或逆 4H 不超过 5x。
- 杠杆不能替代止损，也不能改变账户风险上限。

### A.3 止损

- 必须位于结构失效位置外侧。
- 默认不小于 15m ATR × 1.2。
- 趋势突破可使用 15m ATR × 1.5 至 2.0。
- 止损放宽时必须同步降低合约数量。
- 结构止损导致 R:R 小于 1.5 时，评级为 D。

### A.4 停手规则

| 情况 | 处理 |
|---|---|
| 连续亏损 2 笔 | 下一笔风险减半 |
| 连续亏损 3 笔 | 当日停止交易 |
| 单日亏损达到权益 3% | 当日停止交易 |
| 情绪化追单或无计划开仓 | 停止交易并复盘 |

---

## 附录 B：交易时段与事件风险

### B.1 时区

- 加密市场时间统一记录为 UTC。
- 美股相关窗口使用 America/New_York 当地时间，再动态换算 UTC。
- 不得全年固定使用同一个美股 UTC 开盘时间。

### B.2 硬性降仓窗口

| 窗口 | 美东时间 | 处理 |
|---|---|---|
| 美股开盘前后 15 分钟 | 09:15 至 09:45 | 风险预算降至正常 50% |
| 美股收盘后 30 分钟 | 16:00 至 16:30 | 风险预算降至正常 50% |

重大宏观数据和央行事件优先于一般时段规则。事件刚发生且方向未确认时直接 D。

---

## 附录 C：指标操作定义

以下为统一解释框架，具体阈值应在后续回测中验证。

| 概念 | 操作定义 |
|---|---|
| 放量 | 当前周期成交量相对最近 20 根同周期均量显著增加；报告必须给出比较值 |
| OI 增加或下降 | 使用固定 PERIOD 比较连续历史值，不用单一当前值猜测 |
| OI 大增或大减 | 优先使用最近 30 个周期变化的历史分位，不使用无依据的主观词 |
| Funding 极端 | 优先与自身历史分布比较；必须给出当前值和比较窗口 |
| 多空拥挤 | 多空比、Funding、OI 至少两项同向极端，不凭单一比率判断 |
| 波动压缩 | 布林带宽度和 ATR 同时位于近期低位，成交量下降 |
| 接近日线关键区 | 当前价格与日线区间的距离进入可由 15m ATR 覆盖的范围 |
| 假突破 | 越过关键区后在约定 K 线数量内重新收回，并有成交量或结构支持 |

所有“明显、极端、大增、接近、放量”等词必须附数值、窗口或证据 ID。

---

## 附录 D：特殊情景

| 情景 | 处理 |
|---|---|
| 4H 与 1H 相反 | 1H 明确且 15m 触发时可评 B；叠加其他风险最高 C |
| 接近日线关键区 | 放大反弹、受阻和假突破风险 |
| RSI 或 MACD 背离 | 只标记动能衰竭，不直接反向 |
| 价涨量缩或价跌量缩 | 趋势持续性降权 |
| Funding 极端正值 | 多单降权，警惕多头拥挤 |
| Funding 极端负值 | 空单降权，警惕空头拥挤 |
| 价格上涨、OI 增加且多头拥挤 | 警惕诱多和多头挤压 |
| 价格下跌、OI 增加且空头拥挤 | 警惕诱空和空头挤压 |
| 盘口价差扩大 | 降级或 D，避免追单 |
| 深度挂单快速撤销 | 盘口证据失效 |
| 多空辩论核心分歧无法解决 | 最高 C；若涉及方向或止损逻辑则 D |
| 独立复核发现硬错误 | D |

---

## 附录 E：ETH 专属检查

分析 ETHUSDT 时额外检查：

- ETH/BTC 相对强弱；
- BTC 是否处于强趋势；
- ETH Funding 和 OI 是否比 BTC 更拥挤；
- 以太坊主网、Layer2、质押、ETF 和监管事件；
- Gas 费用异常是否具有事件含义。

若 BTC 处于强单边行情，ETH 独立信号必须降权；但不得仅凭 BTC 方向机械否决 ETH。

---

## 附录 F：版本变更摘要

相对 v3.3，本草稿主要调整：

1. 重组为五阶段执行流程；
2. 数据获取与分析复核工具分离；
3. Binance 接口统一参数、默认周期和可复制请求；
4. 新增 EvidencePacket 和逐项数据状态；
5. 新增独立多头、空头代理与交叉辩论；
6. 将裁判、数据复核、TradingView 复核和 cryptocurrency-trader 复核集中到第 4 阶段；
7. 评级统一为 A/B/C/D；
8. 最低 R:R 统一为 1.5；
9. 修正美股时段的夏令时问题；
10. Pydantic 成为结构化输出契约；
11. 内部完整分析与用户可见精简报告分离；
12. 保留现有参考仓位公式，不加入交易成本和交易规则调整。
