"""Translate chat text between English and Spanish (lazy, on-demand).

The main chat call already returns the assistant reply in both languages, so no
translation happens per turn. This helper is used only for the *lazy* backfill:
the first time a session is viewed in a language a row wasn't written in (the
user's typed message, a short templated reply, a renamed title, or a legacy
row), the missing side is translated once and cached in the DB. Reuses the same
OpenAI client and model as the rest of the chat stack.
"""

from .hyperparameters import LLM_MODEL
from .llm_caller import openai_client


_LANG_NAME = {"en": "English", "es": "Spanish"}

_SYSTEM_PROMPT = (
    "You are a professional translator for a Puerto Rico mental-health "
    "dashboard chat assistant. Translate the user's text into {target}. "
    "Preserve meaning, tone, Markdown formatting, numbers, and proper nouns "
    "(municipality names, indicator names) exactly. Do not add, remove, or "
    "explain anything. Return only the translated text."
)


def translate_text(text: str | None, target_lang: str) -> str:
    """Return `text` translated into `target_lang` ('en' or 'es').

    Empty input returns "" unchanged. On any API error the original text is
    returned so a translation failure never blocks saving a message.
    """
    if not text or not text.strip():
        return text or ""
    target = _LANG_NAME.get(target_lang, "English")
    try:
        response = openai_client.responses.create(
            model=LLM_MODEL,
            instructions=_SYSTEM_PROMPT.format(target=target),
            input=text,
        )
        translated = (response.output_text or "").strip()
        return translated or text
    except Exception as e:  # noqa: BLE001 - never block a read on translation
        print(f"[translate_text] error: {e}")
        return text
