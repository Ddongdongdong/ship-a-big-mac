---
name: ship-a-big-mac
description: Turn a local Git release into a budgeted McDonald's team celebration plan using the official McDonald's China MCP, with verified pricing and a privacy-safe release receipt. Use for release meals, launch celebrations, sprint wrap-ups, or team food planning tied to repository activity.
---

# Ship a Big Mac

Convert a software release into a practical celebration meal. Keep Git analysis local, obtain menu and price facts from the live McDonald's MCP, and clearly separate verified facts from demo or locally estimated values.

## Workflow

1. Ask only for missing operational inputs: people count, total budget, city/landmark, and pickup or delivery preference.
2. Run `python -m ship_a_big_mac analyze --repo <path> --output release-context.json`. Do not use `--include-names` unless the user wants names in local output.
3. Read [references/mcp-workflow.md](references/mcp-workflow.md), then inspect the live MCP tool schemas before making calls. Tool arguments are defined by the server, not by this Skill.
4. Resolve a store, fetch its currently sellable menu, and normalize candidate items into the format in [references/normalized-data.md](references/normalized-data.md).
5. Generate up to three local candidates with `python -m ship_a_big_mac plan`. Submit every candidate to `calculate-price`; discard candidates the MCP cannot quote.
6. Present the verified total, store, fulfillment mode, items, savings reported by MCP, assumptions, and trade-offs. Never describe a menu-price sum as a quote.
7. After the user selects a plan, render the receipt with `python -m ship_a_big_mac receipt --quoted-total <yuan>`. The receipt must not contain contributor names, commit subjects, emails, addresses, order IDs, or tokens.

## Safety and truthfulness

- Treat `ship_a_big_mac/data/*.synthetic.json` as invented demonstration data. Never mix it with live results.
- Never infer product codes, coupon IDs, prices, availability, store capabilities, or fulfillment codes.
- Re-run `calculate-price` if the items, store, coupon, fulfillment mode, or appointment time changes.
- This version plans and verifies a feast but does not call `create-order`. If a host offers ordering separately, obtain explicit user confirmation after showing the final MCP quote.
- Do not place MCP tokens in arguments, generated files, logs, screenshots, or repository content.
- If a hard constraint cannot be verified, label it unresolved rather than silently relaxing it.
