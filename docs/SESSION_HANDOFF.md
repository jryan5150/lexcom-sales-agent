# Session Handoff — Lexcom Sales Agent

## What happened

### Session 1 (original)
- Started as "Lexcom Edge Intelligence" — Heaton Environment Agent + TD Synnex adapter
- Heaton agent was a shadow-mode monitoring system to prove AI could replace two sysadmins
- TD Synnex StreamOne Ion V3 client + MCP server scaffolded from API reference PDF
- Full Jetson setup guide written

### Session 2 (pivot)
- Pivoted from Heaton monitoring to **Lexcom Inside Sales Agent**
- Jace already has a 73-tool CW MCP server (jryan5150/cw-mcp-server, TypeScript)
- Deleted `heaton_agent/` entirely — different domain, different repo if needed later
- Built `sales_agent/` — MCP server with 6 composite tools bridging CW + TD Synnex:
  1. `customer_profile` — aggregate CW company data + TD Synnex subs
  2. `suggest_upsells` — stack gap analysis → catalog search
  3. `price_comparison` — distributor cost vs sell price margin
  4. `build_quote` — TD Synnex cart as draft quote
  5. `renewal_radar` — upcoming CW agreement + TD Synnex subscription expirations
  6. `opportunity_enrichment` — CW opportunity + customer stack + catalog matches
- Wrote thin Python CW client mirroring auth pattern from the TS MCP server
- Kept `tdsynnex/` as-is — already solid

## Key Decisions
- **Sales agent calls CW REST API directly** — not MCP-to-MCP (that's awkward)
- **TD Synnex client imported directly** — shared dependency, not a network call
- **No embedded LLM for now** — Claude IS the intelligence layer via MCP. Ollama reserved for future headless operations
- **Workflows are pure async functions** — MCP server is thin dispatch layer
- **build_quote creates draft carts only** — never auto-checkout

## Files
```
lexcom-edge/
├── CLAUDE.md                          # Project context
├── README.md                          # Setup + usage
├── .env.example                       # Credential template
├── requirements.txt                   # Python deps
├── docs/
│   ├── JETSON_SETUP.md               # Jetson setup guide (still valid)
│   ├── SESSION_HANDOFF.md            # This file
│   └── API_Reference_Guide_TDSynnex_v_0_1.pdf
├── sales_agent/
│   ├── clients/
│   │   └── connectwise.py            # Async CW client
│   ├── workflows/
│   │   ├── customer.py               # customer_profile
│   │   ├── quoting.py                # build_quote + price_comparison
│   │   ├── renewals.py               # renewal_radar
│   │   └── opportunities.py          # opportunity_enrichment + suggest_upsells
│   ├── mcp/
│   │   ├── server.py                 # MCP server (6 composite tools)
│   │   └── __main__.py               # python -m entry point
│   └── config/
│       └── settings.py               # Pydantic settings
└── tdsynnex/
    ├── client/
    │   └── streamone.py              # StreamOne Ion V3 full API client
    └── mcp/
        ├── server.py                 # MCP server (15 direct tools)
        └── __main__.py               # python -m entry point
```

## Next Steps
1. Fill `.env` with real credentials
2. Test `python -m sales_agent.mcp.server` locally
3. Add to Claude Code `.mcp.json`
4. Run `customer_profile` against a real company
5. Run `renewal_radar` to find low-hanging sales fruit
6. Verify TD Synnex cart API paths against the PDF (cart endpoints use different base path)
