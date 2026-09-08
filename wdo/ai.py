import os
import json
import time
import re

from groq import Groq
from groq import (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
)
from dotenv import load_dotenv


load_dotenv()


# --------------------------------------------------
# GROQ CLIENT
# --------------------------------------------------

client = Groq(
    api_key=os.getenv("GROQ_API_KEY"),
    timeout=10.0,
    max_retries=0,
)


MODEL = "openai/gpt-oss-120b"


# --------------------------------------------------
# SYSTEM PROMPT
# --------------------------------------------------

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


# --------------------------------------------------
# FIND MATCHING OPTION
# --------------------------------------------------

def find_option(answer_text, answers):
    """
    Match the model's response against the supplied options.

    Matching order:
    1. Exact match
    2. Case-insensitive exact match
    3. Option letter such as A/B/C/D
    4. Containment match
    """

    if not answer_text:
        return None

    answer = str(answer_text).strip()

    # ----------------------------------------------
    # 1. Exact match
    # ----------------------------------------------

    for option in answers:

        text = option["text"].strip()

        if answer == text:
            return text

    # ----------------------------------------------
    # 2. Case-insensitive exact match
    # ----------------------------------------------

    answer_lower = answer.lower()

    for option in answers:

        text = option["text"].strip()

        if answer_lower == text.lower():
            return text

    # ----------------------------------------------
    # 3. Handle A/B/C/D responses
    # ----------------------------------------------

    letter_match = re.match(
        r"^\s*(?:option\s*)?([A-D])\s*[\.\:\-\)]?\s*$",
        answer,
        re.IGNORECASE
    )

    if letter_match:

        index = ord(letter_match.group(1).upper()) - ord("A")

        if 0 <= index < len(answers):

            return answers[index]["text"].strip()

    # ----------------------------------------------
    # 4. Handle "A. Answer text"
    # ----------------------------------------------

    letter_match = re.match(
        r"^\s*([A-D])\s*[\.\:\-\)]\s*(.+)$",
        answer,
        re.IGNORECASE
    )

    if letter_match:

        possible_text = letter_match.group(2).strip().lower()

        for option in answers:

            text = option["text"].strip()

            if possible_text == text.lower():
                return text

    # ----------------------------------------------
    # 5. Loose containment match
    # ----------------------------------------------

    for option in answers:

        text = option["text"].strip()

        text_lower = text.lower()

        if answer_lower in text_lower:
            return text

        if text_lower in answer_lower:
            return text

    return None


# --------------------------------------------------
# CHOOSE ANSWER
# --------------------------------------------------

def choose_answer(
    question,
    answers,
    retry_delay=0.5,
    max_retry_delay=5
):

    payload = {
        "question": question,
        "options": [
            answer["text"]
            for answer in answers
        ],
    }

    delay = retry_delay

    while True:

        try:

            response = client.chat.completions.create(
                model=MODEL,

                temperature=0,

                # IMPORTANT:
                # reasoning tokens are included here
                max_completion_tokens=150,

                reasoning_effort="low",

                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": json.dumps(payload),
                    },
                ],
            )


            # --------------------------------------
            # GET RESPONSE
            # --------------------------------------

            message = response.choices[0].message

            content = message.content


            print("\nRAW AI RESPONSE:")

            print(
                repr(content)
            )


            # --------------------------------------
            # EMPTY RESPONSE
            # --------------------------------------

            if not content:

                print(
                    "Empty AI response."
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


            # --------------------------------------
            # MATCH OPTION
            # --------------------------------------

            selected = find_option(
                content,
                answers
            )


            if selected is None:

                print(
                    "\nAI response did not match "
                    "any available option."
                )

                print(
                    "AI:",
                    repr(content)
                )

                print("Options:")

                for option in answers:

                    print(
                        "-",
                        option["text"]
                    )

                print(
                    f"Retrying in {delay}s..."
                )

                time.sleep(delay)

                continue


            # --------------------------------------
            # SUCCESS
            # --------------------------------------

            print(
                "[+] AI selected:",
                selected
            )

            return {
                "answer": selected
            }


        # ------------------------------------------
        # NETWORK ERRORS
        # ------------------------------------------

        except (
            APIConnectionError,
            APITimeoutError,
            InternalServerError
        ) as e:

            print(
                f"\nNetwork/API issue: {e}"
            )

            print(
                f"Retrying in {delay}s..."
            )

            time.sleep(delay)

            delay = min(
                delay * 2,
                max_retry_delay
            )


        # ------------------------------------------
        # RATE LIMIT
        # ------------------------------------------

        except RateLimitError as e:

            print(
                f"\nRate limited: {e}"
            )

            print(
                f"Retrying in {delay}s..."
            )

            time.sleep(delay)

            delay = min(
                delay * 2,
                max_retry_delay
            )


        # ------------------------------------------
        # OTHER ERRORS
        # ------------------------------------------

        except Exception as e:

            print(
                f"\nUnexpected error: {e}"
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
# import json
# from dotenv import load_dotenv
# from openai import OpenAI

# load_dotenv()

# client = OpenAI(
#     api_key=os.getenv("GROQ_API_KEY"),
#     base_url="https://api.groq.com/openai/v1",
# )

# SYSTEM_PROMPT = """
# You are an expert multiple-choice quiz assistant.

# Rules:
# - Read the question carefully.
# - Choose ONLY from the provided options.
# - Return ONLY valid JSON.
# - Never explain your answer.
# - Never invent an option.

# Format:

# {
#   "answer": "exact option text"
# }
# """

# def choose_answer(question, answers):

#     prompt = f"""
# Question:
# {question}

# Options:
# {json.dumps([a["text"] for a in answers], indent=2)}
# """

#     response = client.chat.completions.create(
#         model="openai/gpt-oss-120b",
#         temperature=0,
#         messages=[
#             {
#                 "role": "system",
#                 "content": SYSTEM_PROMPT
#             },
#             {
#                 "role": "user",
#                 "content": prompt
#             }
#         ]
#     )

#     return json.loads(response.choices[0].message.content)


# # import os
# # import json
# # from dotenv import load_dotenv
# # from openai import OpenAI

# # load_dotenv()

# # client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# # SYSTEM_PROMPT = """
# # You are an expert quiz assistant.

# # Rules:
# # - Choose ONLY one of the provided options.
# # - Think carefully.
# # - Return ONLY valid JSON.

# # Example:
# # {"answer":"The exact option text"}
# # """

# # def choose_answer(question, answers):

# #     options = "\n".join(
# #         f"- {a['text']}" for a in answers
# #     )

# #     prompt = f"""
# # Question:
# # {question}

# # Options:
# # {options}
# # """

# #     response = client.responses.create(
# #         model="gpt-5.4-mini",
# #         input=[
# #             {
# #                 "role": "system",
# #                 "content": SYSTEM_PROMPT
# #             },
# #             {
# #                 "role": "user",
# #                 "content": prompt
# #             }
# #         ]
# #     )

# #     return json.loads(response.output_text)