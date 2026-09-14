import os
import time
import re

from dotenv import load_dotenv
from openai import OpenAI


# =========================================================
# ENVIRONMENT
# =========================================================

load_dotenv()


# =========================================================
# OPENROUTER CONFIG
# =========================================================

OPENROUTER_API_KEY = os.getenv(
    "OPENROUTER_API_KEY"
)

if not OPENROUTER_API_KEY:
    raise RuntimeError(
        "OPENROUTER_API_KEY is missing from .env"
    )


MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "openai/gpt-5.6"
)


# =========================================================
# OPENROUTER CLIENT
# =========================================================

client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
    timeout=30.0,
    max_retries=0,
)


# =========================================================
# FIND MATCHING OPTION
# =========================================================

def find_option(answer_text, answers):

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
            ord(
                letter_match.group(1).upper()
            )
            - ord("A")
        )

        if 0 <= index < len(answers):

            return answers[
                index
            ]["text"].strip()


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

    delay = retry_delay


    # =====================================================
    # RETRY LOOP
    # =====================================================

    while True:

        try:

            start = time.perf_counter()


            # -------------------------------------------------
            # OPENROUTER REQUEST
            # -------------------------------------------------

            response = client.chat.completions.create(

                model=MODEL,

                messages=[
                    {
                        "role": "system",
                        "content": """
You are an extremely accurate multiple-choice quiz answerer.

Choose exactly ONE correct answer from the four options.

For difficult, obscure, uncertain, current, Nigerian,
entertainment, historical, political, company, or factual
questions, use web search when necessary to verify the answer.

Return ONLY the exact text of the selected option.

Do not return:
- A, B, C, or D
- explanations
- reasoning
- markdown
- JSON
- citations
- extra words
                    """,
                    },

                    {
                        "role": "user",
                        "content": f"""
QUESTION:

{question}

OPTIONS:

A. {answers[0]["text"]}
B. {answers[1]["text"]}
C. {answers[2]["text"]}
D. {answers[3]["text"]}

Select exactly ONE correct option.

Return ONLY the exact option text.
                    """,
                    },
                ],

                temperature=0,

                max_tokens=50,
            )


            elapsed = (
                time.perf_counter()
                - start
            )


            # -------------------------------------------------
            # NO CHOICES
            # -------------------------------------------------

            if not response.choices:

                print(
                    "\n[!] OpenRouter returned no choices."
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
            # GET RESPONSE
            # -------------------------------------------------

            message = response.choices[0].message

            content = (
                message.content
                or ""
            )


            # -------------------------------------------------
            # RAW RESPONSE
            # -------------------------------------------------

            print()

            print(
                "RAW OPENROUTER RESPONSE:"
            )

            print(
                repr(content)
            )


            print(
                f"AI REQUEST TIME: {elapsed:.2f}s"
            )


            # -------------------------------------------------
            # EMPTY RESPONSE
            # -------------------------------------------------

            if not content.strip():

                print(
                    "\n[!] OpenRouter returned "
                    "an empty response."
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
                "\n[+] OpenRouter selected:",
                selected
            )


            delay = retry_delay


            return {
                "answer": selected
            }


        # =====================================================
        # ERROR HANDLING
        # =====================================================

        except Exception as e:

            print()

            print(
                "[!] OpenRouter error:"
            )

            print(
                repr(e)
            )

            print(
                f"Retrying in {delay}s..."
            )

            time.sleep(delay)

            delay = min(
                delay * 2,
                max_retry_delay
            )
