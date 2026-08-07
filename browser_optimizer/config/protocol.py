"""
MCP Protocol Constants — 2026-07-28 Specification
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Defines protocol-level constants, result types, and caching defaults
mandated by the MCP 2026-07-28 stateless specification.
"""

from enum import Enum


# ─────────────────────────────────────────────────────────────
# Protocol Version
# ─────────────────────────────────────────────────────────────
MCP_PROTOCOL_VERSION = "2026-07-28"


# ─────────────────────────────────────────────────────────────
# Result Types (MRTR — Multi Round-Trip Requests)
# ─────────────────────────────────────────────────────────────
class ResultType(str, Enum):
    """Every MCP result must carry a resultType in its _meta field."""
    COMPLETE = "complete"
    INPUT_REQUIRED = "input_required"


# ─────────────────────────────────────────────────────────────
# Cache Scope
# ─────────────────────────────────────────────────────────────
class CacheScope(str, Enum):
    """
    Caching scope hints for list responses.
    PUBLIC  — response can be cached by shared intermediaries.
    PRIVATE — response contains user-specific data, client-only cache.
    """
    PUBLIC = "public"
    PRIVATE = "private"


# ─────────────────────────────────────────────────────────────
# Default TTL values (milliseconds)
# ─────────────────────────────────────────────────────────────
DEFAULT_TOOLS_LIST_TTL_MS = 300_000     # 5 minutes
DEFAULT_PROMPTS_LIST_TTL_MS = 300_000   # 5 minutes
DEFAULT_RESOURCES_LIST_TTL_MS = 60_000  # 1 minute

# ─────────────────────────────────────────────────────────────
# Default Cache Scopes
# ─────────────────────────────────────────────────────────────
DEFAULT_TOOLS_LIST_CACHE_SCOPE = CacheScope.PUBLIC
DEFAULT_PROMPTS_LIST_CACHE_SCOPE = CacheScope.PUBLIC
DEFAULT_RESOURCES_LIST_CACHE_SCOPE = CacheScope.PRIVATE
