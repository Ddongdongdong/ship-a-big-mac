# 麦当劳完整能力工作流

运行 `python -m ship_a_big_mac features` 查看 35 个工具分类；用 `mcp-inspect <tool>` 获取实时参数。客户端协议为 `2025-03-26`，在用户提供的服务版本上限 `2025-06-18` 内，已实测连接。

## 查询入口

| 用户需求 | 快捷命令 / 工具 | 后续处理 |
|---|---|---|
| 营养、热量 | `nutrition` → `list-nutrition-foods` | 按目标筛选官方数据；缺少过敏原或营养字段就说明未提供，不作医疗结论 |
| 近期活动 | `calendar` → `campaign-calendar` | 可传 `--arguments '{"specifiedDate":"2026-10-15"}'`；日期按用户问题或 `now-time-info` 确定 |
| 可领取的券 | `available-coupons` | 实际领取走确认流程 |
| 已持有的券 | `coupons` → `query-my-coupons` | 门店适用性再查 `query-store-coupons` |
| 查积分 | `points` → `query-my-account` | 区分可用、冻结与过期积分 |
| 积分商品 | `mall` → `mall-points-products` | 取真实 `spuId` 查 `mall-product-detail`，核对规格、积分/现金成本和有效期 |
| 餐品订单 | `orders` → `order-list` | 真实订单号查 `query-order`；商城订单用 `mall-order-list` / `mall-order-detail` |
| 外送地址 | `addresses` → `delivery-query-addresses` | 用户选地址后查 `delivery-query-stores` |

快捷命令支持 `--arguments @.mcd/arguments.json`；其余查询用 `mcp-call <tool> --arguments @.mcd/arguments.json`。

## 领券

查可领券 → 说明将领取当前所有可领麦麦省券 → `mcp-action auto-bind-coupons` 预览 → 获得针对该操作的授权后，用相同参数与 `--confirm <confirmation_code>` 执行一次 → 查询我的券核对结果。不得将“可领”说成“已领取”。

## 到店、外送和下单

1. 明确人数、预算、履约方式。到店查 `query-nearby-stores`；外送先查已有地址和可送门店。需要新增地址时，单独预览/确认 `delivery-create-address`。
2. 使用真实返回的门店和业务编码。到店 `beType=1` / `orderType=1` 不传 `beCode`；得来速 `beType=5` / `orderType=1`、外送 `beType=2` / `orderType=2`、团餐 `beType=6` / `orderType=2` 使用门店返回的 `beCode`。团餐可查 `query-meal-assistance`、`query-promotions`。
3. 查菜单、套餐默认组成和特调、可用券，然后整单 `calculate-price`。从返回的 `takeWayList` 选择真实 `takeWayCode`；外送核对地址、餐具、备注与配送费。
4. `mcp-action create-order --arguments @.mcd/order.json` 会实时核价并展示完整参数、整数分总价与确认码。向用户说明具体餐品、份数、总额、门店与履约方式。
5. 该具体订单获授权后，使用同一参数和确认码执行；CLI 再次核价，金额或参数变化会拒绝旧确认。创建订单不等于付款，仅向当前用户返回官方支付信息。
6. 超时导致结果不明时，先查询订单，不自动重试创建。取消订单使用真实订单号和有效原因码，经预览/授权后执行 `cancel-order`。

## 商城、抽奖、主题活动

- 商城：查积分 → 商品列表 → 详情与规格 → 向用户说明积分/现金成本、数量、有效期和实物地址 → 预览 `mall-create-order` → 具体兑换获授权后执行。通用 CLI 预览只显示请求参数与影响，不代替积分成本核对。
- 抽奖：`query-lottery-info` 查规则和消耗，`query-my-prizes` 查奖品。用户知晓消耗并选择参加后才预览/执行 `draw-lottery`。不循环抽奖。
- 主题活动：`query-party-city` → `query-party-store` → `query-party-store-date` → `query-party-store-session`，用真实商品、城市、门店和场次预览/执行 `party-order-create`。以实时工具名为准，旧指南拼写可能不同。
- 订单奖券：用用户提供或订单查询返回的订单号调用 `query-survey-coupon`，只解释实际返回的摘要。

## 执行约定

28 个查询走 `mcp-call`。7 个账户变更走 `mcp-action`：默认仅预览，按实时 Schema 检查类型、必填字段和枚举。确认码绑定工具、服务器、完整参数，以及餐品订单核价金额。

确认码本身不代表人类同意。Agent 仅在该具体操作及影响已获授权后提交确认码；确认码约 5 分钟有效且只能执行一次，过期或重复使用必须重新预览。创建订单会在执行前重新调用 `calculate-price`，价格变化即拒绝旧确认。一次执行只调用一次写工具；网络异常后先查询状态。

通用查询 CLI 向当前本地用户返回真实账户数据。Token、手机号、地址、券清单、订单号与支付链接不进入公开文档、录屏或小票。账户参数文件留在忽略目录 `.mcd/`。
