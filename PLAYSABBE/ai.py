import os
import re

from dotenv import load_dotenv
from google import genai


load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing from .env"
    )


gemini = genai.Client(
    api_key=GEMINI_API_KEY
)

MODEL = "gemini-3.5-flash-lite"


def build_prompt(question, options):

    option_text = "\n".join(
        f"{option['letter']}. {option['text']}"
        for option in options
    )

    return f"""
You are answering a multiple-choice quiz question.

Question:
{question}

Options:
{option_text}

Choose the single best answer.

Return ONLY the letter:
A
B
C
or D

Do not explain.
Do not return the option text.
"""


def normalize_answer(text):

    if not text:
        return None

    text = str(text).strip().upper()

    if text in {"A", "B", "C", "D"}:
        return text

    match = re.search(
        r"(?:^|[\s:(])([ABCD])(?:[\s.):]|$)",
        text
    )

    if match:
        return match.group(1)

    return None


def choose_gemini_answer(question, options):

    try:

        prompt = build_prompt(
            question,
            options
        )

        response = gemini.interactions.create(
            model=MODEL,
            input=prompt,
        )

        raw = response.output_text or ""

        answer = normalize_answer(raw)

        print("\nRAW AI RESPONSE:")
        print(repr(raw))

        if not answer:
            return None

        print("[+] Gemini selected:", answer)

        return {
            "model": "Gemini",
            "answer": answer,
            "raw": raw,
        }

    except Exception as e:

        print("\n[!] Gemini error:")
        print(repr(e))

        return None