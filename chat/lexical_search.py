from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import re

from .chat_db import get_chat_db_connection


_RECENT_OTHER_SESSION_WINDOW = 12
_MAX_LEXICAL_TERMS = 8
_MAX_EXPANDED_TERMS_PER_BASE = 3
_MAX_SESSION_PAIRS = 5
_MAX_DEFINITION_MEMORY_PAIRS = 3
_MEMORY_TEXT_LIMIT = 280
_CANDIDATE_LIMIT_MULTIPLIER = 6
_LEXICAL_STOPWORDS = {
    "a", "about", "again", "an", "and", "are", "at", "can", "como", "con",
    "cual", "de", "del", "do", "does", "el", "en", "es", "explain", "for",
    "give", "got", "gotta", "hay", "hello", "help", "hola", "how", "i", "is",
    "it", "la", "las", "list", "los", "mas", "mean", "means", "me", "more",
    "my", "need", "no", "of", "on", "or", "please", "por", "que", "quiero",
    "score", "show", "tell", "thanks", "than", "that", "the", "this", "to",
    "un", "una", "want", "what", "when", "which", "why", "with", "you",
}
_DEFINITION_PATTERN = re.compile(
    r"\b(stands for|means|refers to|captures|measures|maps to)\b",
    flags=re.IGNORECASE,
)
_DEFINITION_QUERY_PATTERN = re.compile(
    r"^(what(?:['’]s| is)?|what does|define|meaning of|stands for|expand)\b",
    flags=re.IGNORECASE,
)
_NEGATION_PATTERN = re.compile(
    r"\b("
    r"isn[’']?t a term|"
    r"isn[’']?t a metric|"
    r"isn[’']?t (?:listed|used)|"
    r"not listed|"
    r"not in (?:this )?dashboard|"
    r"not part of the dashboard indicators|"
    r"don[’']?t see|"
    r"there isn[’']?t a standard|"
    r"official (?:metrics|indicators) (?:here )?are|"
    r"this dashboard uses categories|"
    r"uses categories like|"
    r"those acronyms aren[’']?t part of the dashboard indicators"
    r")\b",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class SearchTermSpec:
    term: str
    weight: int
    source: str


@dataclass(frozen=True)
class MessageHit:
    message_id: int
    session_id: str
    role: str
    event_at: str
    content: str
    score: int


@dataclass(frozen=True)
class MemoryPair:
    session_id: str
    event_at: str
    source_message_id: int
    source_role: str
    source_score: int
    pair_score: int
    user_message_id: int | None
    assistant_message_id: int | None
    user_text: str
    assistant_text: str
    query_signature: str
    is_definition: bool
    is_negative: bool


@dataclass(frozen=True)
class LexicalSearchResult:
    raw_query: str
    normalized_query: str
    terms: list[str]
    expanded_terms: list[str]
    recent_other_sessions: list[str]
    db_hits: list[MessageHit]
    selected_pairs: list[MemoryPair]
    memory_context: str
    reason: str | None = None

    def search_payload(self) -> dict:
        payload = {
            "raw_query": self.raw_query,
            "normalized_query": self.normalized_query,
            "terms": self.terms,
            "expanded_terms": self.expanded_terms,
            "recent_other_sessions": self.recent_other_sessions,
            "candidate_count": len(self.db_hits),
            "selected_pair_count": len(self.selected_pairs),
        }
        if self.reason:
            payload["reason"] = self.reason
        return payload

    def db_hits_payload(self, limit: int = 12) -> list[dict]:
        return [
            {
                "message_id": hit.message_id,
                "session_id": hit.session_id,
                "role": hit.role,
                "event_at": hit.event_at,
                "score": hit.score,
                "content_preview": truncate_for_memory(hit.content, 160),
            }
            for hit in self.db_hits[:limit]
        ]

    def selected_pairs_payload(self) -> list[dict]:
        return [
            {
                "session_id": pair.session_id,
                "event_at": pair.event_at,
                "source_message_id": pair.source_message_id,
                "source_role": pair.source_role,
                "source_score": pair.source_score,
                "pair_score": pair.pair_score,
                "user_message_id": pair.user_message_id,
                "assistant_message_id": pair.assistant_message_id,
                "query_signature": pair.query_signature,
                "is_definition": pair.is_definition,
                "is_negative": pair.is_negative,
                "user_preview": truncate_for_memory(pair.user_text, 140),
                "assistant_preview": truncate_for_memory(pair.assistant_text, 140),
            }
            for pair in self.selected_pairs
        ]


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def truncate_for_memory(text: str, limit: int = _MEMORY_TEXT_LIMIT) -> str:
    normalized = normalize_space(text)
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def normalize_lexical_text(text: str) -> str:
    normalized = normalize_space(text).lower()
    normalized = re.sub(r"[^a-z0-9_-]+", " ", normalized)
    return normalize_space(normalized)


def extract_lexical_terms(text: str) -> list[str]:
    seen = set()
    terms = []
    for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]*", text or ""):
        lowered = token.lower()
        if lowered in seen or lowered in _LEXICAL_STOPWORDS:
            continue
        if len(lowered) < 3 and not lowered.isdigit():
            continue
        seen.add(lowered)
        terms.append(lowered)
        if len(terms) >= _MAX_LEXICAL_TERMS:
            break
    return terms


def _contains_term(content: str, term: str) -> bool:
    return bool(
        re.search(
            rf"(?<![a-z0-9_-]){re.escape(term)}(?![a-z0-9_-])",
            normalize_lexical_text(content),
        )
    )


def _contains_any_term(content: str, terms: list[str]) -> bool:
    return any(_contains_term(content, term) for term in terms if term)


def _assistant_has_definition(text: str) -> bool:
    return bool(_DEFINITION_PATTERN.search(text or ""))


def _assistant_has_negation(text: str) -> bool:
    return bool(_NEGATION_PATTERN.search(text or ""))


def _is_definition_query(text: str) -> bool:
    return bool(_DEFINITION_QUERY_PATTERN.search(text or ""))


def _format_memory_term(term: str) -> str:
    if term.isalpha() and len(term) <= 6:
        return term.upper()
    return term


def _extract_preferred_answer(text: str) -> str:
    normalized = normalize_space(text)
    if not normalized:
        return ""
    trimmed = re.split(
        r"\b(Would you like|Do you want|If you want|Tell me if)\b",
        normalized,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].rstrip(" .")
    return truncate_for_memory(trimmed + ".", 360)


def _is_edit_distance_at_most_one(a: str, b: str) -> bool:
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False

    if len(a) > len(b):
        a, b = b, a

    i = 0
    j = 0
    edits = 0
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            i += 1
            j += 1
            continue
        edits += 1
        if edits > 1:
            return False
        if len(a) == len(b):
            i += 1
            j += 1
        else:
            j += 1

    if j < len(b) or i < len(a):
        edits += 1
    return edits <= 1


def _collect_recent_session_ids(
    conn,
    session_id: str,
    user_id: str,
    limit: int = _RECENT_OTHER_SESSION_WINDOW,
) -> list[str]:
    rows = conn.execute(
        """
        SELECT id
        FROM sessions
        WHERE user_id = ? AND id != ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (user_id, session_id, limit),
    ).fetchall()
    return [row[0] for row in rows]


def _collect_session_messages(conn, session_ids: list[str]) -> dict[str, list[dict]]:
    if not session_ids:
        return {}
    placeholders = ",".join("?" for _ in session_ids)
    rows = conn.execute(
        f"""
        SELECT
            m.id,
            m.session_id,
            m.role,
            COALESCE(m.timestamp, s.created_at) AS event_at,
            m.content
        FROM messages AS m
        JOIN sessions AS s ON s.id = m.session_id
        WHERE m.session_id IN ({placeholders})
        ORDER BY m.session_id, m.id
        """,
        session_ids,
    ).fetchall()
    messages_by_session: dict[str, list[dict]] = defaultdict(list)
    for message_id, matched_session_id, role, event_at, content in rows:
        messages_by_session[matched_session_id].append(
            {
                "id": message_id,
                "session_id": matched_session_id,
                "role": role,
                "event_at": event_at,
                "content": content or "",
            }
        )
    return dict(messages_by_session)


def _collect_recent_vocabulary_tokens(messages_by_session: dict[str, list[dict]]) -> set[str]:
    vocabulary = set()
    for messages in messages_by_session.values():
        for message in messages:
            for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]*", message["content"]):
                lowered = token.lower()
                if lowered in _LEXICAL_STOPWORDS or len(lowered) < 3:
                    continue
                vocabulary.add(lowered)
    return vocabulary


def _expand_terms_with_recent_vocabulary(
    terms: list[str],
    vocabulary: set[str],
) -> list[str]:
    expanded: list[str] = []
    for term in terms:
        matches = []
        for candidate in sorted(vocabulary):
            if candidate == term:
                continue
            if abs(len(candidate) - len(term)) > 1:
                continue
            if candidate[0] != term[0]:
                continue
            if not _is_edit_distance_at_most_one(term, candidate):
                continue
            matches.append(candidate)
            if len(matches) >= _MAX_EXPANDED_TERMS_PER_BASE:
                break
        expanded.extend(matches)

    deduped: list[str] = []
    seen = set(terms)
    for term in expanded:
        if term in seen:
            continue
        seen.add(term)
        deduped.append(term)
    return deduped


def _build_term_specs(terms: list[str], expanded_terms: list[str]) -> list[SearchTermSpec]:
    specs: list[SearchTermSpec] = []
    for index, term in enumerate(terms):
        specs.append(SearchTermSpec(term=term, weight=max(18, 22 - index * 2), source="base"))
    for index, term in enumerate(expanded_terms):
        specs.append(
            SearchTermSpec(term=term, weight=max(14, 18 - index), source="expanded")
        )
    return specs


def _serialize_term_specs(specs: list[SearchTermSpec]) -> str:
    return "\n".join(f"{spec.term}\t{spec.weight}\t{spec.source}" for spec in specs)


def _parse_term_specs(spec_blob: str) -> list[SearchTermSpec]:
    specs: list[SearchTermSpec] = []
    for line in (spec_blob or "").split("\n"):
        if not line:
            continue
        term, weight, source = line.split("\t", 2)
        specs.append(SearchTermSpec(term=term, weight=int(weight), source=source))
    return specs


def _lexical_score(content: str | None, normalized_query: str, spec_blob: str) -> int:
    normalized_content = normalize_lexical_text(content or "")
    if not normalized_content:
        return 0

    score = 0
    if normalized_query and normalized_content == normalized_query:
        score += 24
    if normalized_query and len(normalized_query) >= 6 and normalized_query in normalized_content:
        score += 10

    for spec in _parse_term_specs(spec_blob):
        if re.search(
            rf"(?<![a-z0-9_-]){re.escape(spec.term)}(?![a-z0-9_-])",
            normalized_content,
        ):
            score += spec.weight
    return score


def _pair_bonus(
    user_text: str,
    assistant_text: str,
    hit: MessageHit,
    term_specs: list[SearchTermSpec],
) -> int:
    bonus = 0
    assistant_normalized = normalize_lexical_text(assistant_text)
    combined_text = f"{user_text}\n{assistant_text}"

    if hit.role == "assistant":
        bonus += 4
    if assistant_text:
        bonus += 8
        if len(normalize_space(assistant_text).split()) >= 12:
            bonus += 4
        if _assistant_has_definition(assistant_text):
            bonus += 14
        if _assistant_has_negation(assistant_text):
            bonus -= 10

    for spec in term_specs:
        if spec.source == "expanded" and _contains_term(combined_text, spec.term):
            bonus += 16
            if _contains_term(assistant_text, spec.term):
                bonus += 10
        if spec.source == "base" and _contains_term(assistant_normalized, spec.term):
            bonus += 4

    return bonus


def _build_memory_pair(
    hit: MessageHit,
    messages_by_session: dict[str, list[dict]],
    term_specs: list[SearchTermSpec],
) -> MemoryPair | None:
    messages = messages_by_session.get(hit.session_id, [])
    index_by_id = {message["id"]: idx for idx, message in enumerate(messages)}
    message_index = index_by_id.get(hit.message_id)
    if message_index is None:
        return None

    user_message = None
    assistant_message = None

    if hit.role == "assistant":
        for idx in range(message_index - 1, -1, -1):
            if messages[idx]["role"] == "user":
                user_message = messages[idx]
                break
        assistant_message = messages[message_index]
    else:
        user_message = messages[message_index]
        for idx in range(message_index + 1, len(messages)):
            if messages[idx]["role"] == "assistant":
                assistant_message = messages[idx]
                break

    user_text = user_message["content"] if user_message else ""
    assistant_text = assistant_message["content"] if assistant_message else ""
    if not user_text and not assistant_text:
        return None

    pair_score = hit.score + _pair_bonus(user_text, assistant_text, hit, term_specs)
    event_at = assistant_message["event_at"] if assistant_message else hit.event_at
    query_signature = normalize_lexical_text(user_text)
    is_definition = _assistant_has_definition(assistant_text)
    is_negative = _assistant_has_negation(assistant_text)

    return MemoryPair(
        session_id=hit.session_id,
        event_at=event_at,
        source_message_id=hit.message_id,
        source_role=hit.role,
        source_score=hit.score,
        pair_score=pair_score,
        user_message_id=user_message["id"] if user_message else None,
        assistant_message_id=assistant_message["id"] if assistant_message else None,
        user_text=user_text,
        assistant_text=assistant_text,
        query_signature=query_signature,
        is_definition=is_definition,
        is_negative=is_negative,
    )


def _pair_to_memory_block(pair: MemoryPair) -> str:
    timestamp = pair.event_at[:16].replace("T", " ")
    lines = []
    if pair.user_text:
        lines.append(f"[{timestamp}] User: {truncate_for_memory(pair.user_text)}")
    if pair.assistant_text:
        lines.append(f"Assistant: {truncate_for_memory(pair.assistant_text)}")
    return "\n".join(lines)


def _filter_pair_candidates(
    pair_candidates: list[MemoryPair],
    normalized_query: str,
    terms: list[str],
    expanded_terms: list[str],
) -> list[MemoryPair]:
    relevance_terms = [*terms, *expanded_terms]
    definition_query = _is_definition_query(normalized_query)
    resolved_definition_pairs = [
        pair
        for pair in pair_candidates
        if pair.is_definition and _contains_any_term(pair.assistant_text, relevance_terms)
    ]
    has_resolved_memory = bool(resolved_definition_pairs)

    if definition_query and has_resolved_memory:
        curated_pairs = []
        seen_signatures = set()
        for pair in resolved_definition_pairs:
            signature = pair.query_signature or f"{pair.session_id}:{pair.source_message_id}"
            if signature in seen_signatures:
                continue
            curated_pairs.append(pair)
            seen_signatures.add(signature)
            if len(curated_pairs) >= _MAX_DEFINITION_MEMORY_PAIRS:
                break
        return curated_pairs

    has_resolved_memory = any(
        pair.is_definition and _contains_any_term(pair.assistant_text, relevance_terms)
        for pair in pair_candidates
    )

    filtered_pairs = []
    for pair in pair_candidates:
        if has_resolved_memory and pair.is_negative:
            negative_matches_query = (
                pair.query_signature == normalized_query
                or _contains_any_term(pair.user_text, relevance_terms)
                or _contains_any_term(pair.assistant_text, relevance_terms)
            )
            if negative_matches_query:
                continue
        filtered_pairs.append(pair)

    deduped_pairs = []
    seen_signatures = set()
    for pair in filtered_pairs:
        signature = pair.query_signature or f"{pair.session_id}:{pair.source_message_id}"
        if signature in seen_signatures and not pair.is_definition:
            continue
        deduped_pairs.append(pair)
        seen_signatures.add(signature)

    return deduped_pairs


def _pick_preferred_term(
    assistant_text: str,
    terms: list[str],
    expanded_terms: list[str],
) -> str:
    for term in [*expanded_terms, *terms]:
        if _contains_term(assistant_text, term):
            return term
    for term in [*expanded_terms, *terms]:
        if term:
            return term
    return ""


def _build_resolved_memory_summary(
    selected_pairs: list[MemoryPair],
    normalized_query: str,
    terms: list[str],
    expanded_terms: list[str],
) -> str:
    if not selected_pairs or not _is_definition_query(normalized_query):
        return ""

    top_pair = selected_pairs[0]
    if not top_pair.is_definition:
        return ""

    query_term = terms[0] if terms else ""
    preferred_term = _pick_preferred_term(top_pair.assistant_text, terms, expanded_terms)
    lines = ["Resolved same-user memory for this query:"]
    if query_term and preferred_term and query_term != preferred_term:
        lines.append(
            "- Likely intended term: "
            f"{_format_memory_term(preferred_term)} "
            f"(close lexical match for {_format_memory_term(query_term)})."
        )
    elif preferred_term:
        lines.append(f"- Preferred term: {_format_memory_term(preferred_term)}.")
    lines.append(
        f"- Preferred answer: {_extract_preferred_answer(top_pair.assistant_text)}"
    )
    return "\n".join(lines)


def search_cross_session_memory(
    session_id: str,
    user_id: str | None,
    user_message: str,
    max_messages: int,
) -> LexicalSearchResult:
    normalized_query = normalize_lexical_text(user_message)
    terms = extract_lexical_terms(user_message)
    if not user_id or not terms:
        return LexicalSearchResult(
            raw_query=user_message,
            normalized_query=normalized_query,
            terms=terms,
            expanded_terms=[],
            recent_other_sessions=[],
            db_hits=[],
            selected_pairs=[],
            memory_context="",
            reason="skipped_no_user_or_terms",
        )

    conn = get_chat_db_connection()
    try:
        recent_other_sessions = _collect_recent_session_ids(conn, session_id, user_id)
        if not recent_other_sessions:
            return LexicalSearchResult(
                raw_query=user_message,
                normalized_query=normalized_query,
                terms=terms,
                expanded_terms=[],
                recent_other_sessions=[],
                db_hits=[],
                selected_pairs=[],
                memory_context="",
                reason="no_other_sessions",
            )

        messages_by_session = _collect_session_messages(conn, recent_other_sessions)
        vocabulary = _collect_recent_vocabulary_tokens(messages_by_session)
        expanded_terms = _expand_terms_with_recent_vocabulary(terms, vocabulary)
        term_specs = _build_term_specs(terms, expanded_terms)
        conn.create_function("lexical_score", 3, _lexical_score)

        placeholders = ",".join("?" for _ in recent_other_sessions)
        spec_blob = _serialize_term_specs(term_specs)
        candidate_limit = max(24, max_messages * _CANDIDATE_LIMIT_MULTIPLIER)
        rows = conn.execute(
            f"""
            SELECT
                m.id AS message_id,
                m.session_id,
                m.role,
                COALESCE(m.timestamp, s.created_at) AS event_at,
                m.content,
                lexical_score(m.content, ?, ?) AS score
            FROM messages AS m
            JOIN sessions AS s ON s.id = m.session_id
            WHERE s.user_id = ?
              AND m.session_id != ?
              AND m.session_id IN ({placeholders})
            ORDER BY
                score DESC,
                CASE WHEN m.role = 'assistant' THEN 1 ELSE 0 END DESC,
                event_at DESC,
                m.id DESC
            LIMIT ?
            """,
            [
                normalized_query,
                spec_blob,
                user_id,
                session_id,
                *recent_other_sessions,
                candidate_limit,
            ],
        ).fetchall()

        db_hits = [
            MessageHit(
                message_id=message_id,
                session_id=matched_session_id,
                role=role,
                event_at=event_at,
                content=content or "",
                score=score,
            )
            for message_id, matched_session_id, role, event_at, content, score in rows
            if score > 0
        ]

        pair_candidates: list[MemoryPair] = []
        seen_pair_keys = set()
        for hit in db_hits:
            pair = _build_memory_pair(hit, messages_by_session, term_specs)
            if not pair:
                continue
            pair_key = (pair.session_id, pair.user_message_id, pair.assistant_message_id)
            if pair_key in seen_pair_keys:
                continue
            seen_pair_keys.add(pair_key)
            pair_candidates.append(pair)

        pair_candidates.sort(
            key=lambda pair: (
                pair.is_definition,
                not pair.is_negative,
                pair.pair_score,
                pair.event_at,
                pair.source_message_id,
            ),
            reverse=True,
        )
        pair_candidates = _filter_pair_candidates(
            pair_candidates,
            normalized_query=normalized_query,
            terms=terms,
            expanded_terms=expanded_terms,
        )

        selected_pairs: list[MemoryPair] = []
        selected_message_ids = set()
        session_pair_counts: dict[str, int] = defaultdict(int)
        memory_message_count = 0
        for pair in pair_candidates:
            if session_pair_counts[pair.session_id] >= _MAX_SESSION_PAIRS:
                continue

            message_ids = {
                message_id
                for message_id in (pair.user_message_id, pair.assistant_message_id)
                if message_id is not None
            }
            if message_ids and message_ids.issubset(selected_message_ids):
                continue

            pair_message_count = len(message_ids)
            if memory_message_count + pair_message_count > max_messages:
                continue

            selected_pairs.append(pair)
            selected_message_ids.update(message_ids)
            session_pair_counts[pair.session_id] += 1
            memory_message_count += pair_message_count

            if memory_message_count >= max_messages:
                break

        memory_blocks = "\n\n".join(
            block for block in (_pair_to_memory_block(pair) for pair in selected_pairs) if block
        )
        resolved_summary = _build_resolved_memory_summary(
            selected_pairs=selected_pairs,
            normalized_query=normalized_query,
            terms=terms,
            expanded_terms=expanded_terms,
        )
        if resolved_summary and memory_blocks:
            memory_context = (
                f"{resolved_summary}\n\n"
                f"Supporting retrieved history:\n{memory_blocks}"
            )
        else:
            memory_context = resolved_summary or memory_blocks
        return LexicalSearchResult(
            raw_query=user_message,
            normalized_query=normalized_query,
            terms=terms,
            expanded_terms=expanded_terms,
            recent_other_sessions=recent_other_sessions,
            db_hits=db_hits,
            selected_pairs=selected_pairs,
            memory_context=memory_context,
        )
    finally:
        conn.close()
