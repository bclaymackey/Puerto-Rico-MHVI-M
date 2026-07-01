import os

from dotenv import load_dotenv
from openai import OpenAI

from .hyperparameters import LLM_MODEL
from .prompt import SYSTEM_PROMPT


load_dotenv()

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _language_directive(language: str) -> str:
    if language == "es":
        return (
            "Respond entirely in Spanish. Never mix languages in the same "
            "response unless the user explicitly asks."
        )
    return (
        "Respond entirely in English. Never mix languages in the same "
        "response unless the user explicitly asks."
    )


def call_llm(
    chat_history_context: list[dict],
    data_context: str,
    language: str = "en",
    user_name: str | None = None,
    memory_context: str = "",
    summary_context: str = "",
) -> str:
    name_directive = (
        f"The user's preferred name is {user_name}. Use it very sparingly — at "
        "most an occasional greeting or a warm moment. Do NOT begin replies with "
        "their name and do NOT repeat it in every message; like a normal "
        "assistant, you usually answer without naming them at all."
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
        f"{_language_directive(language)}\n\n"
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
        response = openai_client.responses.create(
            model=LLM_MODEL,
            instructions=instructions,
            input=chat_history_context,
        )
        return response.output_text
    except Exception as e:
        print(e)
        return "The AI assistant is currently unavailable."
