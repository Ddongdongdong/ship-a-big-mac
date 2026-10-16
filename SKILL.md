---
name: ship-a-big-mac
description: Turn a Git release, hotfix, sprint or recovered build into a celebration meal and shareable achievement card, using McDonald's China MCP for live menu and budget checks. Also handle nutrition, activities, coupons, delivery, points and order queries or explicitly authorized account actions.
---

# Ship a Big Mac

Convert a software release into a practical celebration meal. Keep Git analysis local, obtain menu and price facts from the live McDonald's MCP, and clearly separate verified facts from demo or locally estimated values.

## Route the request

For nutrition, activities, coupons, points, delivery addresses, orders, lottery, or party bookings, read [references/capabilities.md](references/capabilities.md). Do not require a Git repository for these requests. `python -m ship_a_big_mac features` lists the 35 supported tools; inspect live schemas before supplying arguments.

## Release feast workflow

For the guided pickup workflow, run `python -m ship_a_big_mac celebrate`. It gathers missing inputs, reads Git locally, selects a store, builds candidates from live menu details, and quotes each candidate. Use `--demo` for an offline preview and `--help` for scriptable options. This produces a receipt, an achievement SVG and a local HTML preview with PNG export. Let the user choose `major`, `hotfix`, `sprint` or `comeback`; commit volume does not decide the theme or how much the team should eat. Individual dietary constraints need a separate verified assignment workflow; the nominal serving count is not an allergy or nutrition guarantee.

Read [references/celebrate.md](references/celebrate.md) for scripted celebration inputs, release-range arguments, output files and live menu/coupon verification boundaries.

For delivery, custom meal selection or a workflow requiring more control:

1. Ask only for missing operational inputs: people count, total budget, city/landmark, and pickup or delivery preference.
2. Run `python -m ship_a_big_mac analyze --repo <path> --output release-context.json`. Do not use `--include-names` unless the user wants names in local output.
3. Read [references/mcp-workflow.md](references/mcp-workflow.md), then inspect the live MCP tool schemas before making calls. Tool arguments are defined by the server, not by this Skill.
4. Resolve a store, fetch its currently sellable menu, and normalize candidate items into the format in [references/normalized-data.md](references/normalized-data.md).
5. Generate up to three local candidates with `python -m ship_a_big_mac plan`. Submit every candidate to `calculate-price`; discard candidates the MCP cannot quote.
6. Present the verified total, store, fulfillment mode, items, savings reported by MCP, assumptions, and trade-offs. Never describe a menu-price sum as a quote.
7. After the user selects a plan, render the receipt with `python -m ship_a_big_mac receipt --context <context.json> --plan <plans.json> --index <n> --quote-arguments <arguments.json>`. This re-quotes the exact selected products and quantities, checks the live result and budget, and only then marks it MCP VERIFIED. A manually entered `--quoted-total` is USER REPORTED. Keep argument files under local `.mcd/`; shared outputs must not contain contributor names, commit subjects, emails, addresses, order IDs, tokens or coupon details. A card may include the chosen repository name and aggregate statistics; preview before publishing.

## Safety and truthfulness

- Treat `ship_a_big_mac/data/*.synthetic.json` as invented demonstration data. Never mix it with live results.
- Never infer product codes, coupon IDs, prices, availability, store capabilities, or fulfillment codes.
- Re-run `calculate-price` if the items, store, coupon, fulfillment mode, or appointment time changes.
- Reject quotes over the user's budget and revise the candidate; menu discounts may not apply to the whole order. Describe the budget strategy as minimum menu cost within the selected menu, not a global coupon optimum.
- Release planning does not create orders. For requested account changes, use `mcp-action` to preview the concrete operation and execute only when that operation and its effects are authorized. A generated confirmation code is not user authorization; it expires after about five minutes and is single-use. Creating an order re-quotes before execution and rejects a changed price. A timeout is an unknown outcome: query the order before any follow-up.
- Do not place MCP tokens in arguments, generated files, logs, screenshots, or repository content.
- If a hard constraint cannot be verified, label it unresolved rather than silently relaxing it.
