# 麦当劳 MCP 集成说明

## 项目为什么需要 MCP

Ship a Big Mac 把一次软件发版转换成团队庆功餐。Git 提交数和参与人数只能决定“庆祝规模”，无法回答当前门店卖什么、套餐包含什么、优惠是否适用以及整单实付金额。上述事实全部交给麦当劳中国官方 MCP 返回，本地代码不维护真实菜单或价格库。

## Server 与鉴权

- Server：`https://mcp.mcd.cn`
- 协议：Streamable HTTP
- 鉴权：`Authorization: Bearer ${MCD_MCP_TOKEN}`
- 凭据：只从本机环境变量读取，不写入项目文件

仓库中的 `mcp-config.example.json` 仅包含环境变量占位符。

## 使用的 Tools

| Tool | 用途 | 状态影响 |
|---|---|---|
| `now-time-info` | 确定官方服务时间和餐段 | 只读 |
| `query-nearby-stores` | 按城市和地标选择门店 | 只读 |
| `query-meals` | 获取所选门店当前可售菜单与商品编码 | 只读 |
| `query-meal-detail` | 核验套餐组成和可选项 | 只读 |
| `query-store-coupons` | 查询当前门店可用优惠 | 只读 |
| `calculate-price` | 对每个完整候选方案真实整单核价 | 只读 |

默认流程不调用 `create-order`、`auto-bind-coupons`、`draw-lottery`、地址创建、订单取消或积分兑换等写工具。

CLI 的 `mcp-call` 也使用固定只读白名单，只允许上表 6 个 Tool。审核者可以通过 `mcp-inspect <tool>` 查看服务器实时 Schema，再通过 `mcp-call <tool> --arguments @file.json` 复核真实返回；任何未列入白名单的 Tool 都会在网络请求前被拒绝。

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

本地菜单价加总只标记为 `MENU_SUM_NOT_MCP_QUOTED`，不能对用户宣称为实付价。只有 `calculate-price` 成功返回后，输出才标记为 `MCD_MCP_CALCULATE_PRICE`。商品、门店、优惠券、履约方式或预约时间任一变化，都必须重新核价。

## Demo 与真实模式隔离

`ship_a_big_mac/data/demo-menu.synthetic.json` 中的名称、编码和价格全部为虚构数据，文件名、内容和终端输出均明确标注 synthetic/demo。Demo 不读取 Token、不联网，也不存在下单路径。真实模式由 `SKILL.md` 指挥宿主 Agent 调用 MCP，再把规范化数据交给本地规划器。

## 当前验证状态

- 离线规划、Git 分析、SVG 生成及 MCP 协议客户端由自动化测试覆盖。
- 官方 MCP 工具清单和流程依据官方 `M-China/mcd-mcp-server` 文档实现。
- 提交比赛前必须使用已轮换的新 Token 执行 `python -m ship_a_big_mac mcp-tools`，并至少完成一次真实只读菜单查询与 `calculate-price` 核价；未完成前不得声称实时链路已验收。

## 业务价值

普通发版庆祝往往靠群聊临时凑单，预算、份数和真实价格反复确认。项目把“代码里发生了多大的发布”转换成“几个人、多少预算、当前门店可以买到什么”的可执行计划，同时把报价证据和隐私边界写进产物。Release 小票只显示聚合工程指标与餐品，不公开代码、提交标题、作者邮箱、地址或订单信息。
