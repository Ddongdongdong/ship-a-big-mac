<div align="center">

<img src="assets/banner.svg" width="100%" alt="Ship a Big Mac — 把一次发版变成一桌有真实报价依据的庆功餐">

# Ship a Big Mac｜发版就吃巨无霸

**读取本地 Git Release 的规模，用麦当劳中国官方 MCP 的当前门店菜单和整单核价，生成团队庆功餐与可分享的 Release 小票。**

[![tests](https://github.com/Ddongdongdong/ship-a-big-mac/actions/workflows/tests.yml/badge.svg)](https://github.com/Ddongdongdong/ship-a-big-mac/actions/workflows/tests.yml)
[![release](https://img.shields.io/github/v/release/Ddongdongdong/ship-a-big-mac?color=ffdf59)](https://github.com/Ddongdongdong/ship-a-big-mac/releases/latest)
[![stars](https://img.shields.io/github/stars/Ddongdongdong/ship-a-big-mac?style=social)](https://github.com/Ddongdongdong/ship-a-big-mac)

[在线试玩](https://ddongdongdong.github.io/ship-a-big-mac/) · [30 秒 CLI Demo](#30-秒-demo无需-token) · [真实工作流](#真实工作流) · [安全边界](#安全边界) · [MCP 集成](MCP_INTEGRATION.md)

如果你也觉得“发版值得一顿真正算清预算的庆功餐”，欢迎点一颗 ⭐；它会帮助这个开源作品进入麦当劳程序员创意开发大赛排行榜。

</div>

---

发版后的经典对话通常是：“几个人？”“预算多少？”“这家店现在卖什么？”“券到底能不能用？”

Ship a Big Mac 把它变成一条可核验的流水线：

```text
本地 Git 活动 → 庆祝规模 → 当前门店菜单 → 三套候选 → 每套 MCP 真实核价 → Release 小票
```

代码、提交标题和作者邮箱不会发送给麦当劳 MCP。MCP 只接收点餐所需的门店、商品与优惠参数。

## 30 秒 Demo（无需 Token）

需要 Python 3.9+，零第三方依赖：

```bash
git clone https://github.com/Ddongdongdong/ship-a-big-mac.git
cd ship-a-big-mac
python -m ship_a_big_mac demo
```

Demo 会打印三种庆功餐策略，并在当前目录生成 `release-receipt.svg`：

```text
SHIP A BIG MAC · SYNTHETIC DEMO
Release: rocket-checkout v2.4.0 · 24 commits

[均衡] 6 人份 · ¥171.60
  示例·双人发版桶 × 2       ¥99.80
  示例·无糖饮料 × 1          ¥9.00
  示例·经典汉堡套餐 × 1     ¥32.90
  示例·香辣鸡腿套餐 × 1     ¥29.90
  报价状态: MENU_SUM_NOT_MCP_QUOTED

[省预算] 5 人份 · ¥129.70
  示例·双人发版桶 × 2       ¥99.80
  示例·香辣鸡腿套餐 × 1     ¥29.90
  报价状态: MENU_SUM_NOT_MCP_QUOTED
```

<p align="center"><img src="assets/demo-release-receipt.svg" width="620" alt="合成数据生成的 Release 小票"></p>

> Demo 中的名称、价格和商品编码均为虚构数据。真实模式只有经过 `calculate-price` 的结果才能标记为 MCP VERIFIED。

## 它解决什么

普通点餐助手从“想吃什么”开始；Ship a Big Mac 从“我们刚刚完成了什么”开始。

| 发版事实 | 庆祝决策 |
|---|---|
| 提交数、文件数、改动量 | hotfix / regular / major 庆祝强度 |
| 本地贡献者数量 | 默认建议用餐人数 |
| 用户预算 | 每个候选方案的硬上限 |
| 当前门店菜单 | 真正可买到的商品池 |
| `calculate-price` | 唯一的最终价格依据 |

它不读取源代码内容；默认也不公开贡献者姓名。分享卡只显示提交数、文件数、贡献者数量和餐品。

### 目标用户

- 刚完成版本发布、Hotfix 或 Sprint 的研发团队
- 需要在固定总预算内安排多人餐的 Tech Lead、项目经理和行政伙伴
- 想让 Agent 使用实时菜单与官方核价，而不是猜商品和价格的 MCP 开发者

## 真实工作流

### 1. 安装

```bash
python -m pip install -e .
```

### 2. 在本机分析 Release

```bash
ship-a-big-mac analyze --repo /path/to/repository --days 14 --output release-context.json
```

默认贡献者会显示为匿名标签。只有你明确需要本机姓名输出时才使用 `--include-names`。

### 3. 配置官方 MCP

先到 <https://open.mcd.cn/mcp> 申请并妥善保存 Token，然后在支持 Streamable HTTP 的客户端中使用 [`mcp-config.example.json`](mcp-config.example.json)。真实 Token 只能放在本机环境变量：

```bash
export MCD_MCP_TOKEN='你的新 Token'
ship-a-big-mac mcp-tools
```

不要把 Token 写进 JSON、README、Issue、截图或 Git 历史。

连接成功后，可以先查看官方实时参数结构，再调用本项目限定的只读工具：

```bash
ship-a-big-mac mcp-inspect query-nearby-stores
ship-a-big-mac mcp-call now-time-info
ship-a-big-mac mcp-call query-nearby-stores --arguments @nearby-store-arguments.json
```

`mcp-call` 只允许本项目使用的 6 个只读 Tool；`create-order`、领券、抽奖、积分兑换及地址创建等写操作会在本地直接拒绝。调用参数以 `mcp-inspect` 返回的实时 Schema 为准。

### 4. 让 Agent 使用 Skill

将本仓库作为 Skill 加载，然后说：

> 我们刚发完 v2.4.0，5 个人，预算 180 元，在上海徐家汇附近到店取餐，帮我安排一桌发版庆功餐。

Agent 会按照 [`SKILL.md`](SKILL.md) 调用：

```text
now-time-info
→ query-nearby-stores
→ query-meals / query-meal-detail
→ query-store-coupons
→ calculate-price（每个候选分别核价）
```

本地规划器只负责在预算内产生候选，不把菜单价加总冒充实付价。真实金额以 `calculate-price` 返回为准。

### 5. 生成 MCP VERIFIED 小票

Agent 根据实时 Schema 准备所选方案的核价参数文件；商品编码、数量与套餐选项必须来自真实菜单。生成小票时再次联网核价：

```bash
ship-a-big-mac receipt \
  --context release-context.json \
  --plan release-plan.json \
  --quote-arguments .mcd/price-arguments.json \
  --output release-receipt.svg
```

程序校验官方业务返回成功、商品与数量一致、金额未超预算后，才显示 `MCP VERIFIED`。手工输入 `--quoted-total` 仅显示 `USER REPORTED`；从 JSON 导入的验证标签不会被信任。参数文件可能含账户优惠信息，请留在本地 `.mcd/` 目录。

已完成一次真实只读验收：5 人、180 元预算，两套候选核价为 171 元和 167.50 元。详见[实测记录](LIVE_VALIDATION.md)，价格仅代表该次测试。

## 为什么不是另一个 Git 点餐工具

- Git 只是本地“庆祝规模传感器”，不是点餐命令皮肤。
- 核心对象是多人 Release Feast，而不是个人购物车。
- 核心产物是一张能复核报价来源、又不泄露代码和个人信息的 Release 小票。
- 默认只读、只规划、只核价；当前版本不自动创建订单。

## 安全边界

- **凭据不落盘：** Token 仅从 `MCD_MCP_TOKEN` 读取。
- **价格不猜：** 菜单加总标记为 `MENU_SUM_NOT_MCP_QUOTED`，手工金额标记为 `USER_REPORTED_TOTAL`，均不能生成已验证标记。
- **Demo 强隔离：** fixture 文件名和输出均标记 `synthetic`，且不联网。
- **分享不泄密：** SVG 不包含源码、提交标题、作者邮箱、地址、门店、订单号或支付链接。
- **默认无写操作：** 不领券、不抽奖、不兑换积分、不建地址、不下单、不取消订单。

## 项目结构

```text
SKILL.md                         Agent 工作流与安全规则
MCP_INTEGRATION.md               MCP Tool、调用链和业务价值
mcp-config.example.json          脱敏连接示例
ship_a_big_mac/                  Git 分析、规划、协议客户端、SVG 渲染
ship_a_big_mac/data/*.synthetic.json  明确标记的虚构 Demo 数据
references/                      Skill 按需读取的实时流程与数据格式
tests/                           标准库 unittest 测试
CONTEST_DECLARATION.md           官方参赛声明原文
```

## 验证

```bash
python -m unittest discover -s tests -v
python -m ship_a_big_mac demo --output /tmp/release-receipt.svg
```

## 参赛信息

- 赛事：麦当劳程序员创意开发大赛
- 官方能力：麦当劳中国 MCP Server
- 项目 Owner：[@Ddongdongdong](https://github.com/Ddongdongdong)
- 状态：已完成真实只读菜单与整单核价验收，正在提交官方报名。

本项目为非官方参赛作品。餐品、价格、优惠与供应状态以麦当劳官方实时结果为准。
