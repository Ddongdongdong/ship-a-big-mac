---
name: ship-a-big-mac
description: Plan a Git release celebration meal with verified McDonald's China MCP pricing and a shareable receipt. Also handle McDonald's nutrition, activities, coupons, delivery, points redemption, and order queries or explicitly authorized account actions.
---

# Ship a Big Mac

Convert a software release into a practical celebration meal. Keep Git analysis local, obtain menu and price facts from the live McDonald's MCP, and clearly separate verified facts from demo or locally estimated values.

## Route the request

For nutrition, activities, coupons, points, delivery addresses, orders, lottery, or party bookings, read [references/capabilities.md](references/capabilities.md). Do not require a Git repository for these requests. `python -m ship_a_big_mac features` lists the 35 supported tools; inspect live schemas before supplying arguments.

## Release feast workflow

1. Ask only for missing operational inputs: people count, total budget, city/landmark, and pickup or delivery preference.
2. Run `python -m ship_a_big_mac analyze --repo <path> --output release-context.json`. Do not use `--include-names` unless the user wants names in local output.
3. Read [references/mcp-workflow.md](references/mcp-workflow.md), then inspect the live MCP tool schemas before making calls. Tool arguments are defined by the server, not by this Skill.
4. Resolve a store, fetch its currently sellable menu, and normalize candidate items into the format in [references/normalized-data.md](references/normalized-data.md).
5. Generate up to three local candidates with `python -m ship_a_big_mac plan`. Submit every candidate to `calculate-price`; discard candidates the MCP cannot quote.
6. Present the verified total, store, fulfillment mode, items, savings reported by MCP, assumptions, and trade-offs. Never describe a menu-price sum as a quote.
7. After the user selects a plan, render the receipt with `python -m ship_a_big_mac receipt --context <context.json> --plan <plans.json> --index <n> --quote-arguments <arguments.json>`. This re-quotes the exact selected products and quantities, checks the live result and budget, and only then marks it MCP VERIFIED. A manually entered `--quoted-total` is USER REPORTED. Keep argument files under local `.mcd/`; the receipt must not contain contributor names, commit subjects, emails, addresses, order IDs, or tokens.

## Safety and truthfulness

- Treat `ship_a_big_mac/data/*.synthetic.json` as invented demonstration data. Never mix it with live results.
- Never infer product codes, coupon IDs, prices, availability, store capabilities, or fulfillment codes.
- Re-run `calculate-price` if the items, store, coupon, fulfillment mode, or appointment time changes.
- Reject quotes over the user's budget and revise the candidate; menu discounts may not apply to the whole order. Describe the budget strategy as minimum menu cost within the selected menu, not a global coupon optimum.
- Release planning does not create orders. For requested account changes, use `mcp-action` to preview the concrete operation and execute only when that operation and its effects are authorized. A generated confirmation code is not user authorization. Creating an order re-quotes before execution and rejects a changed price.
- Do not place MCP tokens in arguments, generated files, logs, screenshots, or repository content.
- If a hard constraint cannot be verified, label it unresolved rather than silently relaxing it.
