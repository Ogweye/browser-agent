import time

from browser import page
from ai import choose_answer


print()
print("=" * 60)
print("QUIZ AI ASSIST")
print("=" * 60)
print("Edge is running.")
print("Waiting for quiz...")
print("=" * 60)


# =========================================================
# EXTRACT CURRENT QUIZ
# =========================================================

EXTRACT_JS = """
() => {

    const question = document.querySelector(
        '.question-text'
    );

    if (!question) {
        return null;
    }

    const questionStyle =
        getComputedStyle(question);

    if (
        questionStyle.display === 'none' ||
        questionStyle.visibility === 'hidden' ||
        parseFloat(questionStyle.opacity) === 0 ||
        question.offsetParent === null
    ) {
        return null;
    }


    const options = [
        ...document.querySelectorAll(
            '.answer-option'
        )
    ]
    .filter(option => {

        const style =
            getComputedStyle(option);

        return (
            style.display !== 'none' &&
            style.visibility !== 'hidden' &&
            parseFloat(style.opacity) > 0 &&
            option.offsetParent !== null
        );

    })
    .map((option, index) => {

        const text = option.querySelector(
            '.answer-text'
        );

        if (!text) {
            return null;
        }

        const value =
            text.innerText.trim();

        if (!value) {
            return null;
        }

        return {
            index: index,
            text: value
        };

    })
    .filter(Boolean);


    const questionText =
        question.innerText.trim();


    if (
        !questionText ||
        options.length < 4
    ) {
        return null;
    }


    return {
        question: questionText,
        answers: options.slice(0, 4)
    };
}
"""


# =========================================================
# SAFE EXTRACTION
# =========================================================

def extract_state():

    try:

        return page.evaluate(EXTRACT_JS)

    except Exception as e:

        message = str(e)

        if (
            "Execution context was destroyed"
            in message
            or
            "Cannot find context with specified id"
            in message
        ):
            return None

        return None


# =========================================================
# CREATE UNIQUE STATE KEY
# =========================================================

def make_state_key(state):

    if not state:
        return None

    return (
        state["question"],
        tuple(
            answer["text"]
            for answer in state["answers"]
        )
    )


# =========================================================
# POLLING INTERVALS
# =========================================================
# Bumped from 25ms/50ms to 100ms. The quiz UI doesn't need
# sub-frame precision, and this cuts evaluate() calls (each
# of which forces a style/layout recalc for every option) by
# 4x+ with no real hit to perceived responsiveness — your
# actual bottleneck is the AI call, not this loop.

POLL_INTERVAL_MS = 100
CONFIRM_DELAY_MS = 100


# =========================================================
# WAIT FOR A DIFFERENT QUIZ STATE
# =========================================================

def wait_for_new_state(
    old_key,
    timeout_ms=30000
):

    start = time.perf_counter()

    while True:

        elapsed = (
            time.perf_counter() - start
        ) * 1000

        if elapsed >= timeout_ms:
            return None


        state = extract_state()

        if state:

            new_key = make_state_key(state)

            if new_key != old_key:

                # Make sure the new state is stable.
                # Non-blocking (was a blocking time.sleep before).
                page.wait_for_timeout(CONFIRM_DELAY_MS)

                confirmed = extract_state()

                if confirmed:

                    confirmed_key = (
                        make_state_key(
                            confirmed
                        )
                    )

                    if confirmed_key == new_key:
                        return confirmed


        page.wait_for_timeout(POLL_INTERVAL_MS)


# =========================================================
# WAIT FOR FIRST QUESTION
# =========================================================

def wait_for_first_question():

    while True:

        state = extract_state()

        if state:
            return state

        page.wait_for_timeout(POLL_INTERVAL_MS)


# =========================================================
# MAIN LOOP
# =========================================================

question_number = 0
last_key = None


while True:

    try:

        # -------------------------------------------------
        # FIRST QUESTION OR NEXT QUESTION
        # -------------------------------------------------

        if last_key is None:

            state = wait_for_first_question()

        else:

            state = wait_for_new_state(
                old_key=last_key,
                timeout_ms=30000
            )

            if state is None:

                print(
                    "\nWaiting for next question..."
                )

                continue


        # -------------------------------------------------
        # GET DATA
        # -------------------------------------------------

        question = state["question"]
        answers = state["answers"]

        current_key = make_state_key(state)


        # -------------------------------------------------
        # EXTRA DUPLICATE PROTECTION
        # -------------------------------------------------

        if current_key == last_key:

            continue


        question_number += 1


        # -------------------------------------------------
        # DISPLAY QUESTION
        # -------------------------------------------------

        print()
        print("=" * 60)
        print(
            f"QUESTION #{question_number}"
        )
        print("=" * 60)

        print()
        print(question)

        print()
        print("OPTIONS:")

        for i, answer in enumerate(answers):

            letter = chr(65 + i)

            print(
                f"{letter}. "
                f"{answer['text']}"
            )

        print("=" * 60)


        # -------------------------------------------------
        # ASK GEMINI
        # -------------------------------------------------

        start = time.perf_counter()

        result = choose_answer(
            question,
            answers
        )

        elapsed = (
            time.perf_counter()
            - start
        )


        # -------------------------------------------------
        # DISPLAY RESULT
        # -------------------------------------------------

        if result:

            letter = (
                str(result["answer"])
                .strip()
                .upper()
            )


            matching_option = None


            for i, answer in enumerate(answers):

                if chr(65 + i) == letter:

                    matching_option = answer
                    break


            print()

            print(
                "\033[1;97;44m"
            )

            print()
            print(
                "        ████████████████████████████"
            )
            print(
                "        █       GEMINI ANSWER       █"
            )
            print(
                "        ████████████████████████████"
            )

            print()

            print(
                f"        ANSWER: {letter}"
            )


            if matching_option:

                print(
                    f"        {matching_option['text']}"
                )


            print()

            print(
                f"        TIME: {elapsed:.2f}s"
            )

            print()

            print(
                "        ████████████████████████████"
            )

            print()

            print(
                "\033[0m"
            )


        else:

            print()

            print(
                "\033[1;97;41m"
            )

            print(
                "        NO VALID GEMINI RESPONSE"
            )

            print(
                "\033[0m"
            )


        # -------------------------------------------------
        # SAVE EXACT STATE THAT WAS PROCESSED
        # -------------------------------------------------

        last_key = current_key


        # -------------------------------------------------
        # MANUAL ANSWER
        # -------------------------------------------------

        print()
        print(
            "Answer manually."
        )

        print(
            "Waiting for next question..."
        )


    except KeyboardInterrupt:

        print()
        print("Stopping...")
        break


    except Exception as e:

        print()
        print(
            "[!] ERROR:",
            repr(e)
        )

        page.wait_for_timeout(100)