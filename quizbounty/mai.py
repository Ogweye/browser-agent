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
# CLICK SELECTED OPTION
# =========================================================

CLICK_OPTION_JS = """
(selectedText) => {

    const options = [
        ...document.querySelectorAll(
            '.answer-option'
        )
    ];

    for (const option of options) {

        const text = option.querySelector(
            '.answer-text'
        );

        if (!text) {
            continue;
        }

        const optionText =
            text.innerText.trim();

        if (
            optionText.toLowerCase()
            ===
            selectedText.trim().toLowerCase()
        ) {

            option.scrollIntoView({
                behavior: 'instant',
                block: 'center'
            });

            option.click();

            return true;
        }
    }

    return false;
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

POLL_INTERVAL_MS = 100
CONFIRM_DELAY_MS = 100


# =========================================================
# WAIT FOR DIFFERENT QUIZ STATE
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

                page.wait_for_timeout(
                    CONFIRM_DELAY_MS
                )

                confirmed = extract_state()

                if confirmed:

                    confirmed_key = (
                        make_state_key(
                            confirmed
                        )
                    )

                    if confirmed_key == new_key:
                        return confirmed

        page.wait_for_timeout(
            POLL_INTERVAL_MS
        )


# =========================================================
# WAIT FOR FIRST QUESTION
# =========================================================

def wait_for_first_question():

    while True:

        state = extract_state()

        if state:
            return state

        page.wait_for_timeout(
            POLL_INTERVAL_MS
        )


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
        # DUPLICATE PROTECTION
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
        # ASK GROQ
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
        # PROCESS RESULT
        # -------------------------------------------------

        if result:

            selected = (
                str(result["answer"])
                .strip()
            )


            # -------------------------------------------------
            # FIND MATCHING LETTER
            # -------------------------------------------------

            matching_letter = None

            for i, answer in enumerate(answers):

                if (
                    answer["text"].strip().lower()
                    ==
                    selected.lower()
                ):

                    matching_letter = (
                        chr(65 + i)
                    )

                    break


            # -------------------------------------------------
            # DISPLAY ANSWER
            # -------------------------------------------------

            print()

            print(
                "\033[1;97;44m"
            )

            print()

            print(
                "        ████████████████████████████"
            )

            print(
                "        █         GROQ ANSWER       █"
            )

            print(
                "        ████████████████████████████"
            )

            print()

            if matching_letter:

                print(
                    f"        ANSWER: {matching_letter}"
                )

            print(
                f"        {selected}"
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


            # -------------------------------------------------
            # CLICK ANSWER
            # -------------------------------------------------

            print(
                "Clicking answer..."
            )

            clicked = page.evaluate(
                CLICK_OPTION_JS,
                selected
            )


            if clicked:

                print(
                    "[+] Answer clicked successfully."
                )

            else:

                print(
                    "[!] Could not find matching "
                    "answer button."
                )


        else:

            print()

            print(
                "\033[1;97;41m"
            )

            print(
                "        NO VALID GROQ RESPONSE"
            )

            print(
                "\033[0m"
            )


        # -------------------------------------------------
        # SAVE PROCESSED STATE
        # -------------------------------------------------

        last_key = current_key


        # -------------------------------------------------
        # WAIT FOR NEXT QUESTION
        # -------------------------------------------------

        print()

        print(
            "Waiting for next question..."
        )


    # =====================================================
    # STOP
    # =====================================================

    except KeyboardInterrupt:

        print()
        print("Stopping...")
        break


    # =====================================================
    # ERROR HANDLING
    # =====================================================

    except Exception as e:

        print()

        print(
            "[!] ERROR:",
            repr(e)
        )

        page.wait_for_timeout(100)