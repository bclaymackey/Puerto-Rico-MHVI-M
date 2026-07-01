"""Single control panel for chat tuning parameters.

Change behavior here, not scattered across modules. Only behaviour-tuning knobs
live here (windows, limits, model, the context-token budget). Pure cosmetics
(PDF colors, fixed strings) stay in their own files.

Token note: we estimate ~4 characters per token (good enough for budgeting).
"""

# ── Model ────────────────────────────────────────────────────────────────────
LLM_MODEL = "gpt-5-nano"

# ── Layer 2: current-session history ─────────────────────────────────────────
# Most recent messages (user+assistant) sent to the LLM each turn.
HISTORY_WINDOW = 20

# ── Layer 3: rolling session summary ─────────────────────────────────────────
SUMMARY_TRIGGER_MESSAGES = 6      # only re-summarize after this many new msgs
SUMMARY_WORD_LIMIT = 120          # keep the running summary this short

# ── Layer 4: cross-session memory (lexical_search) ───────────────────────────
CROSS_SESSION_MESSAGE_WINDOW = 40   # max messages pulled into memory context
RECENT_OTHER_SESSION_WINDOW = 12    # how many other sessions to scan
MAX_LEXICAL_TERMS = 8
MAX_EXPANDED_TERMS_PER_BASE = 3
MAX_SESSION_PAIRS = 5
MAX_DEFINITION_MEMORY_PAIRS = 3
MEMORY_TEXT_LIMIT = 280             # per-message truncation in memory blocks
CANDIDATE_LIMIT_MULTIPLIER = 6
ENTITY_BOOST = 20                   # +score when a pair mentions an active entity
STALL_PENALTY = 40                 # -score for "I'll fetch later" non-answers

# ── Entity carry-over (conversation_state) ───────────────────────────────────
CARRY_OVER_SCAN_LIMIT = 12         # recent msgs scanned to recover named regions

# ── Ranking ("most vulnerable …") ────────────────────────────────────────────
RANKING_TOP_N = 5

# ── Context token budget ─────────────────────────────────────────────────────
# Hard ceiling on the whole assembled prompt. gpt-5-nano allows far more; this
# is a hygiene cap so old memory can't crowd out the current data.
MAX_CONTEXT_TOKENS = 100_000
CHARS_PER_TOKEN = 4

# How the *variable* layers share the budget (after the fixed system prompt).
# Higher-authority layers get more room; cross-session memory gets the least.
# Weights are relative; they don't need to sum to 1.
CONTEXT_BUDGET_WEIGHTS = {
    "data_context": 0.40,      # the numbers — most authoritative
    "history": 0.30,           # current-session turns
    "summary_context": 0.10,   # rolling summary (already tiny)
    "memory_context": 0.20,    # cross-session memory — least authoritative
}
