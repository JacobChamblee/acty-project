# Context Mode Routing Instructions

> **VS Code Copilot + MCP Server**  
> These instructions route important tool calls to the context-mode MCP server, reducing context window bloat by 95-98% while preserving session continuity.

## MCP Server Tools

Context Mode provides 6 sandboxing tools that process output in isolation:

- **`ctx_execute`** — Run code (Python, JS, Node, Bash, Go, Rust, etc.) securely. Stdout only enters context
- **`ctx_execute_file`** — Process files without loading raw content. Returns summary only
- **`ctx_batch_execute`** — Run multiple commands or queries in one call (more efficient)
- **`ctx_index`** — Index markdown or code into FTS5 knowledge base
- **`ctx_search`** — Query indexed content with semantic ranking
- **`ctx_fetch_and_index`** — Fetch URL, convert to markdown, index, then search. 24h cache

## Routing Rules

### When to use ctx_execute (instead of terminal commands)

Use `ctx_execute` for:

- Running Python scripts to analyze data or logs
- JavaScript/Node.js code execution
- Quick shell commands that produce verbose output
- Commands that might output credentials or secrets (they're isolated)
- Any script where you only need the final result, not line-by-line terminal view

Example:

```
User: "Analyze this git log for top contributors"
→ Use: ctx_batch_execute with Git history analysis script
→ Output: 1.2 KB (raw: 11.6 KB, 90% saved)
```

### When to use ctx_index + ctx_search (instead of dumping content)

Use `ctx_index` + `ctx_search` for:

- Indexing documentation before querying
- Processing large Markdown files (60KB+ → searchable)
- Building knowledge bases from API responses
- URL content (web pages, API docs)
- Avoiding dump-and-search pattern (wasteful)

Example:

```
User: "Fetch React docs and find the cleanup pattern"
→ Use: ctx_fetch_and_index for the URL
→ Use: ctx_search for queries
→ Output: 1.8 KB (raw: 60KB, 97% saved)
```

### When to use ctx_fetch_and_index (instead of raw curl)

Use `ctx_fetch_and_index` for:

- Fetching web pages (auto HTML→markdown conversion)
- API documentation URLs
- GitHub issue/PR content (render as markdown)
- Repeated URLs (24h cache = free re-queries)

**Never** dump raw HTML or JSON into context — always index first.

## Session Continuity

Context Mode tracks 4 events automatically:

- **PostToolUse** — Captures tool results
- **PreCompact** — Snapshots session state (tasks, files, decisions)
- **SessionStart** — Restores state after compaction or `--continue`
- **UserPromptSubmit** — Records your feedback and corrections

If context compacts (context window fills), the model will **automatically restore**:

- Which files you were editing
- What tasks are in progress
- What errors were resolved
- Your last prompt and decision

**No re-prompting needed.** Just keep typing — the session continues seamlessly.

## Utility Commands

Type these in the chat:

```
ctx stats       → Show context savings, token counts, cache hits
ctx doctor      → Diagnose runtimes, hooks, FTS5, plugin health
ctx upgrade     → Update to latest GitHub version
```

## Security & Permissions

Context Mode respects your project's permission rules. Add to `.claude/settings.json`:

```json
{
  "permissions": {
    "deny": ["Bash(sudo *)", "Bash(rm -rf /*)", "Read(.env)"],
    "allow": ["Bash(git:*)", "Bash(npm:*)"]
  }
}
```

All rules are tool-agnostic — they apply to `ctx_execute`, `ctx_batch_execute`, and terminal commands equally.

## Examples

### Example 1: Research a Large Repository

**Without Context Mode:** 986 KB raw output → leaves 40% of context empty  
**With Context Mode:** 986 KB → 62 KB (94% saved) via `ctx_batch_execute` + `ctx_search`

```
User: "Research https://github.com/modelcontextprotocol/servers —
architecture, tech stack, top contributors, recent issues"

→ ctx_batch_execute: Clone, analyze git log, list top (space-efficient)
→ ctx_index: Full README into knowledge base
→ ctx_search: Query for architecture, contributors, issues
→ Result: 62 KB context, full session duration extends 3x
```

### Example 2: Analyze CSV or Log Files

**Without Context Mode:** 45 KB access log → clogs context  
**With Context Mode:** 45 KB → 155 B (99% saved) via `ctx_execute_file`

```
User: "Analyze this 500-request access log for slowest endpoints"

→ ctx_execute_file: Load CSV, aggregate by endpoint, compute p95 latency
→ Result: 155 B summary, no raw log in context
```

### Example 3: Documentation Lookup

**Without Context Mode:** Fetch page (60 KB) → search manually → lose context  
**With Context Mode:** 60 KB → 261 B (96% saved) via `ctx_fetch_and_index`

```
User: "Fetch React docs, find the cleanup function pattern with examples"

→ ctx_fetch_and_index: URL → markdown → index into FTS5
→ ctx_search: "cleanup effect pattern code example"
→ Get: Relevant snippet only, 261 B, searchable for follow-ups
→ Bonus: Cache hit on repeat — 0.3 KB instead of re-fetching
```

## Troubleshooting

If a tool call feels slow:

- Check `ctx stats` for cache performance (is this a cache miss?)
- For large outputs (>5 KB), verify an `intent` is provided for filtering
- Batch multiple commands: `ctx_batch_execute` saves overhead

If session doesn't restore after compaction:

- Run `ctx doctor` to verify SessionStart hook is active
- Check that `copilot-instructions.md` exists in project root
- VS Code Copilot requires hooks auto-enabled (no manual setup)

## References

- **Repo:** https://github.com/mksglu/context-mode
- **MCP Protocol:** https://modelcontextprotocol.io/
- **Full Platform Docs:** https://github.com/mksglu/context-mode/blob/main/docs/platform-support.md

---

**Last Updated:** March 28, 2026  
**Status:** Active — MCP server running  
**Hook Support:** Full (PostToolUse, PreCompact, SessionStart, UserPromptSubmit)
