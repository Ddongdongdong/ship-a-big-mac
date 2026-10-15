# 一键庆祝

安装后执行 `ship-a-big-mac celebrate --demo` 可体验离线配餐；`ship-a-big-mac celebrate` 会连接自己的 MCP 账户并引导选择取餐门店。需要在 Git 仓库中运行，或传 `--repo /path/to/repo`。正常终端会询问缺少的参数，重定向输入或 `--non-interactive` 时使用提供的参数和默认值。

```bash
ship-a-big-mac celebrate --demo --scene comeback --people 5 --budget 180 --version v3.0.0 --non-interactive --open
```

```bash
ship-a-big-mac celebrate --repo . --scene major --people 5 --budget 180 --city 上海 --keyword 徐家汇 --store-code 1450323 --non-interactive --output-dir .mcd/my-feast
```

真实命令中的城市、地标和门店是公开示例，须换成实际需求。门店必须来自本次附近门店结果，不能凭空指定。默认选择列表中的第一个营业门店和第一个成功核价的方案；`--store-code`、`--select 2` 可以明确选择。`--version` 自定义卡片版本标签；主题支持 `major / hotfix / sprint / comeback`，不改变配餐价格。

默认输出目录为 `celebration/`，已加入 `.gitignore`。生成 `release-achievement.svg`、`release-receipt.svg`、`celebration.html` 和 `celebration.json`；打开 HTML 可下载 PNG，或使用 `--open` 自动打开预览。摘要中包含仓库名、聚合 Git 统计、餐品和报价上下文摘要，不包含原始核价参数、券码、门店、地址、作者姓名或提交内容。

首版真实流程使用到店取餐和官方默认套餐组成。当前支持的单人套餐名称为：巨无霸三件套、麦辣鸡腿汉堡三件套、双层吉士汉堡套餐、板烧鸡腿堡套餐、麦香鱼套餐、麦香鸡套餐。只选当前门店实际返回的餐品，代码和价格来自实时菜单；缺货、更名或不能验证默认组成的套餐会跳过。这个明确的菜单子集避免把双人分享餐直接当作单人份，但仍不代表个体营养或饱腹保证。

所有候选都须通过整单核价和预算检查才会展示；每个候选绑定本次完整核价参数。没有合格方案时给出错误，不回退为未经核价的“已验证”方案。优惠券只查询，不自动套券。外送、自选餐品、套餐选项和逐人口味需求使用 [MCP 工作流](mcp-workflow.md) 处理，不会在一键流程中悄悄忽略约束。
