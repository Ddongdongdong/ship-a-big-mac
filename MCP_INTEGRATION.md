# 麦当劳 MCP 集成说明

## 项目为什么需要 MCP

Ship a Big Mac 把一次软件发版转换成团队庆功餐。Git 提交数和参与人数只能决定“庆祝规模”，无法回答当前门店卖什么、套餐包含什么、优惠是否适用以及整单实付金额。上述事实全部交给麦当劳中国官方 MCP 返回，本地代码不维护真实菜单或价格库。

## Server 与鉴权

- Server：`https://mcp.mcd.cn`
- 协议：Streamable HTTP，客户端协议版本 `2025-03-26`（在用户提供的服务上限 `2025-06-18` 以内，已实测连接）
- 鉴权：`Authorization: Bearer ${MCD_MCP_TOKEN}`
- 凭据：只从本机环境变量读取，不写入项目文件

仓库中的 `mcp-config.example.json` 仅包含环境变量占位符。

## 使用的 Tools

已扩展到实时服务器的 **35 个工具：28 个查询、7 个需确认操作**。下表是发版配餐链路；其余场景包括营养、活动、领券、积分商城、外送地址、订单、抽奖与主题活动，完整工具目录用 `python -m ship_a_big_mac features` 查看，流程见 [references/capabilities.md](references/capabilities.md)。

| Tool | 用途 | 状态影响 |
|---|---|---|
| `now-time-info` | 确定官方服务时间和餐段 | 只读 |
| `query-nearby-stores` | 按城市和地标选择门店 | 只读 |
| `query-meals` | 获取所选门店当前可售菜单与商品编码 | 只读 |
| `query-meal-detail` | 核验套餐组成和可选项 | 只读 |
| `query-store-coupons` | 查询当前门店可用优惠 | 只读 |
| `calculate-price` | 对每个完整候选方案真实整单核价 | 只读 |

发版规划流程不改变账户。需要领券、创建订单、取消订单、新增地址、积分兑换、抽奖或预约主题活动时，通过 `mcp-action` 预览并在具体操作获授权后执行。

CLI 的 `mcp-call` 使用 28 个查询工具的固定白名单。审核者可以通过 `mcp-inspect <tool>` 查看实时 Schema，再通过 `mcp-call <tool> --arguments @file.json` 复核。新工具不会自动获得执行权限。

`mcp-action <tool> --arguments @file.json` 默认仅预览，检查实时 Schema 并返回绑定工具、服务器和完整参数的确认码；使用 `--confirm <code>` 才执行一次写调用，不自动重试。`create-order` 在预览和执行阶段都会重新核价，价格变化将使确认失效。积分兑换的成本由 Skill 先查询商品详情并向用户呈现，通用预览不会推算积分成本。

快捷命令：`nutrition`、`calendar`、`coupons`、`available-coupons`、`points`、`mall`、`orders`、`addresses`。查询结果可能包含当前账户信息，不能直接用于公开录屏。

## 调用流程

```text
本地 Git 仓库
  │ analyze（代码与提交信息不离开本机）
  ▼
ReleaseContext：提交数、文件数、贡献者数量、发版强度
  │
  ├─ now-time-info
  ├─ query-nearby-stores → 用户选择门店
  ├─ query-meals / query-meal-detail
  ├─ query-store-coupons
  ▼
本地确定性规划器：生成至多 3 个候选组合
  │ 每个候选都必须分别调用
  ▼
calculate-price
  │ 只保留可成功核价的方案
  ▼
用户选择 → 生成不含个人信息的 Release 小票 SVG
```

## 价格纪律

本地菜单价加总只标记为 `MENU_SUM_NOT_MCP_QUOTED`，不能对用户宣称为实付价。`receipt --quote-arguments` 在当前运行中调用 `calculate-price`，检查业务成功、商品数量一致、整数分金额与预算后，才标记为 `MCD_MCP_CALCULATE_PRICE`。手工 `--quoted-total` 只标记为 `USER_REPORTED_TOTAL`，导入 JSON 中的验证标签不会被信任。商品、门店、优惠券、履约方式或预约时间任一变化，都必须重新核价。

## Demo 与真实模式隔离

`ship_a_big_mac/data/demo-menu.synthetic.json` 中的名称、编码和价格全部为虚构数据，文件名、内容和终端输出均明确标注 synthetic/demo。Demo 不读取 Token、不联网，也不存在下单路径。真实模式由 `SKILL.md` 指挥宿主 Agent 调用 MCP，再把规范化数据交给本地规划器。

## 当前验证状态

- 离线规划、Git 分析、SVG 生成及 MCP 协议客户端由自动化测试覆盖。
- 官方 MCP 工具清单和流程依据官方 `M-China/mcd-mcp-server` 文档实现。
- 2026-10-15 已使用真实 Token 完成 6 个只读工具的联网验收，包含套餐默认选项及两套整单核价；详见 [LIVE_VALIDATION.md](LIVE_VALIDATION.md)。Token 未写入仓库。该记录不代表所有门店、履约方式及券组合都已测试。
- 同日新增 11 个查询接口联网验收全部成功：营养、活动、可领券、我的券、积分、商城商品、餐品历史订单、配送地址、抽奖信息、我的奖品、商城订单。领券预览验证未执行账户变更。写操作采用模拟测试，未实际下单、领券、兑换、取消、抽奖或预约；工具目录覆盖不等于所有业务分支已真实执行。

## 业务价值

普通发版庆祝往往靠群聊临时凑单，预算、份数和真实价格反复确认。项目把“代码里发生了多大的发布”转换成“几个人、多少预算、当前门店可以买到什么”的可执行计划，同时把报价证据和隐私边界写进产物。Release 小票只显示聚合工程指标与餐品，不公开代码、提交标题、作者邮箱、地址或订单信息。
