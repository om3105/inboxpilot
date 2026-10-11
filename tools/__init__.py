"""
tools/ — Individual, typed, validated tool implementations.

Each tool is a pure function (or thin async wrapper) with:
- Typed input/output via Pydantic models
- Clear error messages
- No implicit global state

This isolation makes each tool independently testable and swappable
(e.g. replacing lookup_record with an MCP server in Phase 8).
"""
