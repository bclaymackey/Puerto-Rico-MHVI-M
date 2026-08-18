from types import SimpleNamespace

from chat import llm_caller


def test_ollama_text_call_preserves_instructions_and_input(monkeypatch):
    captured = {}

    def fake_chat(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(message=SimpleNamespace(content="local reply"))

    monkeypatch.setattr(llm_caller, "LLM_PROVIDER", "ollama")
    monkeypatch.setattr(llm_caller, "LLM_MODEL", "qwen3.5:9b")
    monkeypatch.setattr(llm_caller, "ollama_chat", fake_chat)

    result = llm_caller.call_text_llm("same instructions", "same input")

    assert result == "local reply"
    assert captured["model"] == "qwen3.5:9b"
    assert captured["messages"] == [
        {"role": "system", "content": "same instructions"},
        {"role": "user", "content": "same input"},
    ]


def test_ollama_bilingual_call_parses_structured_content(monkeypatch):
    content = (
        '{"query":"Hello","query_en":"Hello","query_es":"Hola",'
        '"en":"Welcome","es":"Bienvenido","title_en":"Test chat",'
        '"title_es":"Chat de prueba"}'
    )

    def fake_chat(**kwargs):
        assert kwargs["format"] == llm_caller.BilingualReply.model_json_schema()
        return SimpleNamespace(message=SimpleNamespace(content=content))

    monkeypatch.setattr(llm_caller, "LLM_PROVIDER", "ollama")
    monkeypatch.setattr(llm_caller, "LLM_MODEL", "qwen3.5:9b")
    monkeypatch.setattr(llm_caller, "ollama_chat", fake_chat)

    reply = llm_caller._call_bilingual_llm(
        "same instructions", [{"role": "user", "content": "Hello"}]
    )

    assert reply.en == "Welcome"
    assert reply.es == "Bienvenido"


def test_openai_text_call_uses_configured_model(monkeypatch):
    captured = {}

    class FakeResponses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(output_text="openai reply")

    fake_client = SimpleNamespace(responses=FakeResponses())
    monkeypatch.setattr(llm_caller, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(llm_caller, "LLM_MODEL", "gpt-5.6-luna")
    monkeypatch.setattr(llm_caller, "openai_client", fake_client)

    result = llm_caller.call_text_llm("same instructions", "same input")

    assert result == "openai reply"
    assert captured == {
        "model": "gpt-5.6-luna",
        "instructions": "same instructions",
        "input": "same input",
    }


def test_invalid_ollama_json_uses_existing_chat_fallback(monkeypatch):
    def fake_chat(**kwargs):
        return SimpleNamespace(message=SimpleNamespace(content="not json"))

    monkeypatch.setattr(llm_caller, "LLM_PROVIDER", "ollama")
    monkeypatch.setattr(llm_caller, "ollama_chat", fake_chat)

    reply = llm_caller.call_llm(
        [{"role": "user", "content": "Hello"}],
        data_context="",
    )

    assert reply["en"] == "The AI assistant is currently unavailable."
    assert reply["es"] == "El asistente de IA no está disponible en este momento."
