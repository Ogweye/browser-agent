import os
import json
import time
import re

from dotenv import load_dotenv

from groq import Groq
from groq import (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
)


# =========================================================
# ENVIRONMENT
# =========================================================

load_dotenv()


# =========================================================
# GROQ CLIENT
# =========================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY is missing from .env"
    )


MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-120b"
)


client = Groq(
    api_key=GROQ_API_KEY,
    timeout=10.0,
    max_retries=0,
)


# =========================================================
# SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT = """
You answer multiple-choice questions.

Choose exactly ONE option.

Return ONLY the exact text of the selected option.

Do NOT return:
- A, B, C, or D
- explanations
- reasoning
- markdown
- JSON
- extra words

The answer MUST be copied exactly from the provided options.
"""


# =========================================================
# FIND MATCHING OPTION
# =========================================================

def find_option(answer_text, answers):
    """
    Match the AI response against the supplied options.

    Matching order:
    1. Exact match
    2. Case-insensitive exact match
    3. Option letter such as A/B/C/D
    4. "A. Answer text" format
    5. Loose containment match
    """

    if not answer_text:
        return None

    answer = str(answer_text).strip()

    # -----------------------------------------------------
    # 1. EXACT MATCH
    # -----------------------------------------------------

    for option in answers:

        text = option["text"].strip()

        if answer == text:
            return text


    # -----------------------------------------------------
    # 2. CASE-INSENSITIVE EXACT MATCH
    # -----------------------------------------------------

    answer_lower = answer.lower()

    for option in answers:

        text = option["text"].strip()

        if answer_lower == text.lower():
            return text


    # -----------------------------------------------------
    # 3. HANDLE A/B/C/D
    # -----------------------------------------------------

    letter_match = re.match(
        r"^\s*(?:option\s*)?([A-D])\s*[.):\-]?\s*$",
        answer,
        re.IGNORECASE
    )

    if letter_match:

        index = (
            ord(letter_match.group(1).upper())
            - ord("A")
        )

        if 0 <= index < len(answers):

            return answers[index]["text"].strip()


    # -----------------------------------------------------
    # 4. HANDLE "A. Answer text"
    # -----------------------------------------------------

    letter_match = re.match(
        r"^\s*([A-D])\s*[.):\-]\s*(.+)$",
        answer,
        re.IGNORECASE
    )

    if letter_match:

        possible_text = (
            letter_match.group(2)
            .strip()
            .lower()
        )

        for option in answers:

            text = option["text"].strip()

            if possible_text == text.lower():

                return text


    # -----------------------------------------------------
    # 5. LOOSE CONTAINMENT MATCH
    # -----------------------------------------------------

    for option in answers:

        text = option["text"].strip()

        text_lower = text.lower()

        if answer_lower in text_lower:

            return text

        if text_lower in answer_lower:

            return text


    # -----------------------------------------------------
    # NO MATCH
    # -----------------------------------------------------

    return None


# =========================================================
# CHOOSE ANSWER
# =========================================================

def choose_answer(
    question,
    answers,
    retry_delay=0.5,
    max_retry_delay=5
):
    """
    Send the question and options to Groq.

    Returns:

        {
            "answer": "exact option text"
        }

    The function keeps retrying if:
    - Groq returns an empty response
    - The response doesn't match an option
    - A temporary API/network error occurs
    """

    payload = {
        "question": question,
        "options": [
            answer["text"]
            for answer in answers
        ],
    }


    delay = retry_delay


    # =====================================================
    # RETRY LOOP
    # =====================================================

    while True:

        try:

            # -------------------------------------------------
            # GROQ REQUEST
            # -------------------------------------------------

            response = client.chat.completions.create(

                model=MODEL,

                temperature=0,

                # GPT-OSS uses completion tokens for
                # both reasoning and final output.
                max_completion_tokens=150,

                reasoning_effort="low",

                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            payload,
                            ensure_ascii=False
                        ),
                    },
                ],
            )


            # -------------------------------------------------
            # GET RESPONSE
            # -------------------------------------------------

            if not response.choices:

                print(
                    "\n[!] Groq returned no choices."
                )

                print(
                    f"Retrying in {delay}s..."
                )

                time.sleep(delay)

                delay = min(
                    delay * 2,
                    max_retry_delay
                )

                continue


            message = response.choices[0].message

            content = message.content


            # -------------------------------------------------
            # RAW RESPONSE
            # -------------------------------------------------

            print("\nRAW AI RESPONSE:")

            print(
                repr(content)
            )


            # -------------------------------------------------
            # EMPTY RESPONSE
            # -------------------------------------------------

            if not content:

                print(
                    "\n[!] Empty AI response."
                )

                print(
                    "Finish reason:",
                    response.choices[0].finish_reason
                )

                print(
                    "Usage:",
                    response.usage
                )

                print(
                    f"Retrying in {delay}s..."
                )

                time.sleep(delay)

                delay = min(
                    delay * 2,
                    max_retry_delay
                )

                continue


            content = content.strip()


            # -------------------------------------------------
            # MATCH RESPONSE TO OPTION
            # -------------------------------------------------

            selected = find_option(
                content,
                answers
            )


            # -------------------------------------------------
            # INVALID RESPONSE
            # -------------------------------------------------

            if selected is None:

                print(
                    "\n[!] AI response did not match "
                    "any available option."
                )

                print(
                    "AI:",
                    repr(content)
                )

                print(
                    "Options:"
                )

                for option in answers:

                    print(
                        "-",
                        option["text"]
                    )

                print(
                    f"Retrying in {delay}s..."
                )

                time.sleep(delay)

                delay = min(
                    delay * 2,
                    max_retry_delay
                )

                continue


            # -------------------------------------------------
            # SUCCESS
            # -------------------------------------------------

            print(
                "\n[+] AI selected:",
                selected
            )


            # Reset retry delay after successful request.
            delay = retry_delay


            return {
                "answer": selected
            }


        # =====================================================
        # NETWORK / API ERRORS
        # =====================================================

        except (
            APIConnectionError,
            APITimeoutError,
            InternalServerError
        ) as e:

            print(
                f"\n[!] Network/API issue: {e}"
            )

            print(
                f"Retrying in {delay}s..."
            )

            time.sleep(delay)

            delay = min(
                delay * 2,
                max_retry_delay
            )


        # =====================================================
        # RATE LIMIT
        # =====================================================

        except RateLimitError as e:

            print(
                f"\n[!] Groq rate limited: {e}"
            )

            print(
                f"Retrying in {delay}s..."
            )

            time.sleep(delay)

            delay = min(
                delay * 2,
                max_retry_delay
            )


        # =====================================================
        # OTHER ERRORS
        # =====================================================

        except Exception as e:

            print(
                f"\n[!] Unexpected Groq error: {e}"
            )

            print(
                f"Retrying in {delay}s..."
            )

            time.sleep(delay)

            delay = min(
                delay * 2,
                max_retry_delay
            )
# import os
# import re

# from dotenv import load_dotenv
# from openai import OpenAI


# # --------------------------------------------------
# # ENVIRONMENT
# # --------------------------------------------------

# load_dotenv()

# OPENROUTER_API_KEY = os.getenv(
#     "OPENROUTER_API_KEY"
# )

# MODEL = os.getenv(
#     "OPENROUTER_MODEL",
#     "google/gemini-2.5-flash"
#     # "google/gemini-2.5-flash:online"
# )

# if not OPENROUTER_API_KEY:
#     raise RuntimeError(
#         "OPENROUTER_API_KEY is missing from .env"
#     )


# # --------------------------------------------------
# # OPENROUTER CLIENT
# # --------------------------------------------------

# client = OpenAI(
#     api_key=OPENROUTER_API_KEY,
#     base_url="https://openrouter.ai/api/v1",
#     max_retries=0,
#     timeout=10.0,
# )


# # --------------------------------------------------
# # PROMPT
# # --------------------------------------------------

# def build_prompt(question, options):

#     option_text = "\n".join(
#         f"{chr(65 + i)}. {option['text']}"
#         for i, option in enumerate(options)
#     )

#     return f"""Choose the single correct answer.

# Question:
# {question}

# Options:
# {option_text}

# Return ONLY one letter: A, B, C, or D.

# Do not explain your answer.
# Do not return the option text.
# """


# # --------------------------------------------------
# # NORMALIZE ANSWER
# # --------------------------------------------------

# def normalize_answer(text):

#     if not text:
#         return None

#     text = str(text).strip().upper()

#     # Exact answer
#     if text in {"A", "B", "C", "D"}:
#         return text

#     # Find A/B/C/D inside a response
#     match = re.search(
#         r"(?:^|[\s:(])([ABCD])(?:[\s.):]|$)",
#         text
#     )

#     if match:
#         return match.group(1)

#     return None


# # --------------------------------------------------
# # ASK OPENROUTER
# # --------------------------------------------------

# def choose_answer(question, options):

#     prompt = build_prompt(
#         question,
#         options
#     )

#     try:

#         response = client.chat.completions.create(
#             model=MODEL,

#             messages=[
#                 {
#                     "role": "user",
#                     "content": prompt
#                 }
#             ],

#             temperature=0,

#             # Enough for Gemini to answer,
#             # while keeping the response short.
#             max_tokens=20,

#             # Disable Gemini's reasoning for this
#             # simple A/B/C/D classification task.
#             extra_body={
#                 "reasoning": {
#                     "max_tokens": 0
#                 }
#             }
#         )


#         # --------------------------------------------------
#         # GET RESPONSE
#         # --------------------------------------------------

#         raw = ""

#         if response.choices:

#             raw = (
#                 response
#                 .choices[0]
#                 .message
#                 .content
#                 or ""
#             )


#         # --------------------------------------------------
#         # DEBUG
#         # --------------------------------------------------

#         print("\nRAW OPENROUTER RESPONSE:")
#         print(repr(raw))


#         # --------------------------------------------------
#         # NORMALIZE
#         # --------------------------------------------------

#         answer = normalize_answer(raw)

#         if not answer:

#             print(
#                 "[!] OpenRouter returned no valid A/B/C/D answer."
#             )

#             return None


#         print(
#             "[+] OpenRouter selected:",
#             answer
#         )


#         # --------------------------------------------------
#         # RETURN SAME FORMAT AS YOUR GEMINI ai.py
#         # --------------------------------------------------

#         return {
#             "model": "OpenRouter - Gemini 2.5 Flash",
#             "answer": answer,
#             "raw": raw
#         }


#     except Exception as e:

#         print(
#             "\n[!] OPENROUTER ERROR:"
#         )

#         print(
#             repr(e)
#         )

#         return None
