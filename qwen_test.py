import os
from time import perf_counter

from dotenv import load_dotenv
from ollama import ChatResponse, chat
from openai import OpenAI


load_dotenv()


english_started_at = perf_counter()
english_response: ChatResponse = chat(
    model="qwen3.5:9b",
    messages=[{"role": "user", "content": "Hello!"}],
)
english_latency = perf_counter() - english_started_at
print(english_response.message.content)
print(f"English response latency: {english_latency:.2f} seconds")

spanish_started_at = perf_counter()
spanish_response: ChatResponse = chat(
    model="qwen3.5:9b",
    messages=[{"role": "user", "content": "¡Hola! Responde brevemente en español."}],
)
spanish_latency = perf_counter() - spanish_started_at
print(spanish_response.message.content)
print(f"Spanish response latency: {spanish_latency:.2f} seconds")

openai_model = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
client = OpenAI()

openai_started_at = perf_counter()
openai_response = client.responses.create(
    model=openai_model,
    input="Write a short bedtime story about a unicorn.",
)
openai_latency = perf_counter() - openai_started_at
print(openai_response.output_text)
print(f"OpenAI ({openai_model}) response latency: {openai_latency:.2f} seconds")
