"""hello_hermes.py – erster Testaufruf des Qwen-Modells über die USTP-API."""
import os
import sys

from openai import OpenAI

BASE_URL = "https://api.ai.ustp.host/v1"
MODEL = os.environ.get("MARS_MODEL", "vllm/Qwen3.8-27B-FP8")

# 1) API-Key aus der Umgebungsvariable lesen (nie in den Code schreiben!)
api_key = os.environ.get("VLLM_API_KEY")
if not api_key:
    sys.exit("Fehler: Umgebungsvariable VLLM_API_KEY ist nicht gesetzt.")

# 2) Client erstellen, der auf den USTP-Server statt auf OpenAI zeigt
client = OpenAI(base_url=BASE_URL, api_key=api_key)

# 3) Nachricht an das Modell schicken
response = client.chat.completions.create(
    model=MODEL,
    messages=[
        {"role": "system",
         "content": "Du bist Hermes, der Bordcomputer einer Marskolonie. Antworte kurz."},
        {"role": "user",
         "content": "Hallo Hermes! Melde den Status der Kolonie in einem Satz."},
    ],
    max_tokens=500,
    temperature=0.7,
    # Qwen3-Denkmodus ausschalten -> Antwort kommt direkt in "content"
    extra_body={"chat_template_kwargs": {"enable_thinking": False}},
)

# 4) Antwort und Diagnose ausgeben
choice = response.choices[0]
print(f"Modell: {MODEL}")
print(choice.message.content)
print(f"\n[Ende-Grund: {choice.finish_reason} | Tokens: {response.usage.total_tokens}]")
