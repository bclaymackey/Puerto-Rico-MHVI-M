import os

from dotenv import load_dotenv
from openai import OpenAI

from prompt import SYSTEM_PROMPT


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
) -> str:
    instructions = (
        f"{SYSTEM_PROMPT}\n\n"
        f"{_language_directive(language)}\n\n"
        "Data context (use exactly if relevant; may be empty for follow-ups):\n"
        f"{data_context}"
    )

    try:
        print("[call_llm input]", chat_history_context)
        response = openai_client.responses.create(
            model="gpt-5-nano",
            instructions=instructions,
            input=chat_history_context,
        )
        return response.output_text
    except Exception as e:
        print(e)
        return "The AI assistant is currently unavailable."
