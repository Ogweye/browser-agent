import os
import re

from dotenv import load_dotenv
from openai import OpenAI


# --------------------------------------------------
# ENVIRONMENT
# --------------------------------------------------

load_dotenv()

OPENROUTER_API_KEY = os.getenv(
    "OPENROUTER_API_KEY"
)

MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "google/gemini-2.5-flash:online"
)

if not OPENROUTER_API_KEY:
    raise RuntimeError(
        "OPENROUTER_API_KEY is missing from .env"
    )


# --------------------------------------------------
# OPENROUTER CLIENT
# --------------------------------------------------

client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
    max_retries=0,
    timeout=10.0,
)


# --------------------------------------------------
# PROMPT
# --------------------------------------------------

def build_prompt(question, options):

    option_text = "\n".join(
        f"{chr(65 + i)}. {option['text']}"
        for i, option in enumerate(options)
    )

    return f"""Choose the single correct answer.

Question:
{question}

Options:
{option_text}

Return ONLY one letter: A, B, C, or D.

Do not explain your answer.
Do not return the option text.
"""


# --------------------------------------------------
# NORMALIZE ANSWER
# --------------------------------------------------

def normalize_answer(text):

    if not text:
        return None

    text = str(text).strip().upper()

    # Exact answer
    if text in {"A", "B", "C", "D"}:
        return text

    # Find A/B/C/D inside a response
    match = re.search(
        r"(?:^|[\s:(])([ABCD])(?:[\s.):]|$)",
        text
    )

    if match:
        return match.group(1)

    return None


# --------------------------------------------------
# ASK OPENROUTER
# --------------------------------------------------

def choose_answer(question, options):

    prompt = build_prompt(
        question,
        options
    )

    try:

        response = client.chat.completions.create(
            model=MODEL,

            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],

            temperature=0,

            # Enough for Gemini to answer,
            # while keeping the response short.
            max_tokens=20,

            # Disable Gemini's reasoning for this
            # simple A/B/C/D classification task.
            extra_body={
                "reasoning": {
                    "max_tokens": 0
                }
            }
        )


        # --------------------------------------------------
        # GET RESPONSE
        # --------------------------------------------------

        raw = ""

        if response.choices:

            raw = (
                response
                .choices[0]
                .message
                .content
                or ""
            )


        # --------------------------------------------------
        # DEBUG
        # --------------------------------------------------

        print("\nRAW OPENROUTER RESPONSE:")
        print(repr(raw))


        # --------------------------------------------------
        # NORMALIZE
        # --------------------------------------------------

        answer = normalize_answer(raw)

        if not answer:

            print(
                "[!] OpenRouter returned no valid A/B/C/D answer."
            )

            return None


        print(
            "[+] OpenRouter selected:",
            answer
        )


        # --------------------------------------------------
        # RETURN SAME FORMAT AS YOUR GEMINI ai.py
        # --------------------------------------------------

        return {
            "model": "OpenRouter - Gemini 2.5 Flash",
            "answer": answer,
            "raw": raw
        }


    except Exception as e:

        print(
            "\n[!] OPENROUTER ERROR:"
        )

        print(
            repr(e)
        )

        return None
# import os
# import re

# from dotenv import load_dotenv
# from google import genai


# # --------------------------------------------------
# # ENVIRONMENT
# # --------------------------------------------------

# load_dotenv()

# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# MODEL = os.getenv(
#     "GEMINI_MODEL",
#     "gemini-3.1-flash-lite"
# )

# if not GEMINI_API_KEY:
#     raise RuntimeError(
#         "GEMINI_API_KEY is missing from .env"
#     )


# # --------------------------------------------------
# # GEMINI CLIENT
# # --------------------------------------------------

# client = genai.Client(
#     api_key=GEMINI_API_KEY
# )


# # --------------------------------------------------
# # TOOLS
# # --------------------------------------------------
# # Google Search grounding: lets the model check the real answer
# # instead of guessing from memory. This is what closes the
# # accuracy gap you were seeing vs. checking manually.
# # The model decides per-question whether a search is actually
# # needed, so easy questions still answer fast.

# SEARCH_TOOL = [{"type": "google_search"}]


# # --------------------------------------------------
# # PROMPT
# # --------------------------------------------------

# def build_prompt(question, options):

#     option_text = "\n".join(
#         f"{chr(65 + i)}. {option['text']}"
#         for i, option in enumerate(options)
#     )

#     return f"""
# Choose the single correct answer.

# Question:
# {question}

# Options:
# {option_text}

# Return ONLY one letter:
# A
# B
# C
# or D

# Do not explain.
# Do not return the option text.
# """


# # --------------------------------------------------
# # NORMALIZE ANSWER
# # --------------------------------------------------

# def normalize_answer(text):

#     if not text:
#         return None

#     text = str(text).strip().upper()

#     if text in {"A", "B", "C", "D"}:
#         return text

#     match = re.search(
#         r"(?:^|[\s:(])([ABCD])(?:[\s.):]|$)",
#         text
#     )

#     if match:
#         return match.group(1)

#     return None


# # --------------------------------------------------
# # ASK GEMINI
# # --------------------------------------------------

# def choose_answer(question, options):

#     prompt = build_prompt(
#         question,
#         options
#     )

#     try:

#         response = client.interactions.create(
#             model=MODEL,
#             input=prompt,
#             generation_config={
#                 "thinking_level": "minimal",
#                 # NOTE: verify this key name against the current
#                 # Interactions API docs for your SDK version — it
#                 # caps generation length so the model can't ramble
#                 # past "do not explain" and add tail latency.
#                 "max_output_tokens": 5,
#             },
#             tools=SEARCH_TOOL,
#         )

#         raw = response.output_text or ""

#         print("\nRAW GEMINI RESPONSE:")
#         print(repr(raw))

#         answer = normalize_answer(raw)

#         if not answer:

#             print(
#                 "[!] Gemini returned no valid A/B/C/D answer."
#             )

#             return None

#         print(
#             "[+] Gemini selected:",
#             answer
#         )

#         return {
#             "model": "Gemini",
#             "answer": answer,
#             "raw": raw
#         }

#     except Exception as e:

#         print(
#             "\n[!] GEMINI ERROR:"
#         )
#         print(
#             repr(e)
#         )

#         return None