"""Translate chat text between English and Spanish for bilingual storage.

Every message, title, and summary is stored in both languages (see chat_db
schema). The original text is kept verbatim in its own language column; this
helper produces the copy for the other language, reusing the same OpenAI client
and model the rest of the chat stack uses.
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
    except Exception as e:  # noqa: BLE001 - never block a save on translation
        print(f"[translate_text] error: {e}")
        return text


def make_bilingual(text: str | None, source_lang: str) -> tuple[str, str]:
    """Return (english_text, spanish_text) for `text` written in `source_lang`.

    The source-language slot holds the original verbatim; the other is translated.
    """
    source_lang = "es" if source_lang == "es" else "en"
    if source_lang == "es":
        return translate_text(text, "en"), (text or "")
    return (text or ""), translate_text(text, "es")
