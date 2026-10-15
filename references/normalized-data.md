# Normalized input formats

The local planner intentionally does not parse arbitrary live MCP payloads. The agent first inspects the current schema and writes a small normalized menu file:

```json
{
  "source": "mcd-mcp/query-meals",
  "store_code": "code returned by MCP",
  "retrieved_at": "ISO-8601 timestamp",
  "items": [
    {
      "code": "product code returned by MCP",
      "name": "display name returned by MCP",
      "price_cents": 3290,
      "serves": 1,
      "role": "combo",
      "tags": ["burger", "drink"],
      "available": true
    }
  ]
}
```

`price_cents` is only a candidate-generation hint. The final total must come from `calculate-price` and be supplied to the receipt command with `--quoted-total`.

The Git analyzer writes a release context JSON. By default contributor identities are salted-looking local labels derived from hashes; the shareable SVG only displays the contributor count.
