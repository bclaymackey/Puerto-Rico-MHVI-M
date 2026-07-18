import os

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

from .hyperparameters import LLM_MODEL
from .prompt import SYSTEM_PROMPT


load_dotenv()

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class BilingualReply(BaseModel):
    """Structured reply: the answer plus a session title, both bilingual.

    The single generation call returns everything the UI shows — the assistant
    message and the conversation's title — in both languages, so no extra
    translation or title-generation call is ever needed. `query` echoes the most
    recent user message for logging/clarity only (it is never used to overwrite
    stored history).
    """

    query: str
    query_en: str
    query_es: str
    en: str
    es: str
    title_en: str
    title_es: str


# The answer and a short session title are produced in both languages in one
# call. Whatever the user sees in the chat must exist in both languages.
_BILINGUAL_DIRECTIVE = (
    "First, echo the user's most recent message verbatim in the 'query' field "
    "(for logging), and provide that same user message translated into English "
    "in 'query_en' and into Spanish in 'query_es' (a faithful translation, "
    "nothing added or removed). Then answer the SAME content twice, once per "
    "language:\n"
    "- 'en' MUST be written entirely in English.\n"
    "- 'es' MUST be written entirely in Spanish (español). Never put English "
    "text in the 'es' field — translate it fully, including short greetings and "
    "one-line replies (e.g. 'Hello!' → '¡Hola!'). If you catch yourself writing "
    "English in 'es', translate it before returning.\n"
    "The two answers must carry identical content — nothing added, dropped, or "
    "reordered — with Markdown, numbers, and proper nouns (municipality and "
    "indicator names) kept identical. Also return a short 3–6 word title "
    "summarizing what THIS conversation is about, in 'title_en' (English) and "
    "'title_es' (Spanish, español); the two titles must mean the same thing and "
    "each must be in its own language."
)


def call_llm(
    chat_history_context: list[dict],
    data_context: str,
    language: str = "en",
    user_name: str | None = None,
    memory_context: str = "",
    summary_context: str = "",
) -> dict:
    """Return the answer, title, and user query — all bilingual — from one call.

    Shape: {"query", "query_en", "query_es", "en", "es", "title_en",
    "title_es"}. `query` is the raw echo of the latest user message (logging);
    `query_en`/`query_es` are that message translated, so the user turn is stored
    bilingually with no extra call.
    """
    name_directive = (
        f"The user's preferred name is {user_name}. When THIS is the first "
        "assistant reply of the conversation (the history has no prior assistant "
        "turn), greet them warmly by name, e.g. 'Hi {name}!' / '¡Hola, {name}!'. "
        "After that opening greeting, use the name only sparingly (an occasional "
        "warm moment); do not begin every later reply with their name or repeat "
        "it in every message."
        if user_name
        else ""
    )
    memory_directive = (
        "Earlier same-user memory from other recent sessions "
        "(lexically retrieved; use only if directly relevant, and ignore it if "
        "it conflicts with the current session or the data context).\n"
        "If a 'Resolved same-user memory for this query' block is present, treat it as the "
        "preferred carry-over answer unless the current session or data context explicitly "
        "overrides it.\n"
        "If this memory contains a direct resolved definition, mapping, or acronym expansion "
        "for the user's current term or a close typo variant, use that resolved answer.\n"
        "Correct obvious close typos when the retrieved memory makes the intended dashboard "
        "term clear.\n"
        "If older memory chunks are uncertain, negative, or say the term was unknown, but a "
        "clearer defining memory is also present, prefer the defining memory and ignore the older uncertainty.\n"
        "Do not repeat stale 'not a term' responses when the retrieved memory already contains a better answer.\n\n"
        "Earlier same-user memory:\n"
        f"{memory_context}"
        if memory_context
        else ""
    )
    summary_directive = (
        "Conversation summary so far (rolling memory of this session; use it to "
        "stay on the active municipality, category, and comparison context, and "
        "to avoid re-asking resolved facts):\n"
        f"{summary_context}"
        if summary_context
        else ""
    )
    instructions = (
        f"{SYSTEM_PROMPT}\n\n"
        f"{_BILINGUAL_DIRECTIVE}\n\n"
        f"{name_directive}\n\n"
        f"{summary_directive}\n\n"
        f"{memory_directive}\n\n"
        "Data context (use exactly if relevant; may be empty for follow-ups):\n"
        f"{data_context}"
    )

    try:
        print("[call_llm input]", chat_history_context)
        print("[call_llm data_context]", data_context or "<empty>")
        print("[call_llm summary_context]", summary_context or "<empty>")
        print("[call_llm memory_context]", memory_context or "<empty>")
        response = openai_client.responses.parse(
            model=LLM_MODEL,
            instructions=instructions,
            input=chat_history_context,
            text_format=BilingualReply,
        )
        reply = response.output_parsed
        if reply is None:
            raise ValueError("no parsed output")
        # Print the raw structured response to the console the moment it returns.
        print("[call_llm raw response]", reply.model_dump_json(indent=2))
        return {
            "query": reply.query,
            "query_en": reply.query_en,
            "query_es": reply.query_es,
            "en": reply.en,
            "es": reply.es,
            "title_en": reply.title_en,
            "title_es": reply.title_es,
        }
    except Exception as e:
        print(e)
        unavailable = "The AI assistant is currently unavailable."
        unavailable_es = "El asistente de IA no está disponible en este momento."
        return {
            "query": "",
            "query_en": "",
            "query_es": "",
            "en": unavailable,
            "es": unavailable_es,
            "title_en": "",
            "title_es": "",
        }
