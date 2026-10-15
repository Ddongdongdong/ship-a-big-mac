# Live MCP workflow

Read this reference only for a live, non-demo plan.

The official server is `https://mcp.mcd.cn` over Streamable HTTP. Authenticate locally with `Authorization: Bearer ${MCD_MCP_TOKEN}`. Inspect `tools/list` in the current session because schemas may change.

Suggested read-only chain:

1. `now-time-info`: establish the service date and meal period.
2. `query-nearby-stores`: resolve the user's city and landmark to a store for pickup. For delivery, follow the address/store tools exposed by the live schemas.
3. `query-meals`: fetch the selected store's currently sellable menu and product codes.
4. `query-meal-detail`: verify combo composition or replaceable choices when a candidate contains a combo.
5. `query-store-coupons`: retrieve coupons applicable at that store.
6. `calculate-price`: quote each complete candidate. Treat this response as the sole price authority.

Use no write tool during planning. For requested coupon claims, ordering, address changes, cancellation, lottery, points redemption, or party booking, follow [capabilities.md](capabilities.md) and the `mcp-action` preview/confirmation path.

Keep an evidence note for each final plan:

- store code and display name;
- menu retrieval time;
- exact product codes and quantities;
- coupon ID if one was quoted;
- `calculate-price` total and any returned discount;
- unresolved assumptions.

Do not persist personal addresses, phone numbers, payment links, coupon inventories, or order identifiers.
