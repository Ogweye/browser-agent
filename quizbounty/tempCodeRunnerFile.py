from quizbounty.browser import page
from quizbounty.ai import choose_answer

print("Waiting for quiz...")

last_state = None


def extract_state():
    return page.evaluate("""
    () => {

        const question = document.querySelector(
            '.question-text'
        );

        if (!question) return null;

        const style = getComputedStyle(question);

        if (
            style.display === 'none' ||
            style.visibility === 'hidden' ||
            question.offsetParent === null
        ) {
            return null;
        }

        const options = [
            ...document.querySelectorAll('.answer-option')
        ]
        .filter(option => {

            const style = getComputedStyle(option);

            return (
                style.display !== 'none' &&
                style.visibility !== 'hidden' &&
                option.offsetParent !== null
            );

        })
        .map((option, index) => {

            const text = option.querySelector(
                '.answer-text'
            );

            if (!text) return null;

            const value = text.innerText.trim();

            if (!value) return null;

            return {
                index: index,
                text: value
            };

        })
        .filter(Boolean);

        if (
            !question.innerText.trim() ||
            !options.length
        ) {
            return null;
        }

        return {
            question: question.innerText.trim(),
            answers: options
        };
    }
    """)


def find_answer_index(selected, answers):
    """Exact match first, then a loose contains-match fallback
    so small formatting differences don't burn extra AI calls."""

    for i, option in enumerate(answers):
        if option["text"].strip().lower() == selected:
            return i

    for i, option in enumerate(answers):
        opt_text = option["text"].strip().lower()
        if selected in opt_text or opt_text in selected:
            return i

    return -1


while True:

    try:

        # ----------------------------------------------
        # GET NEW QUESTION
        # ----------------------------------------------

        while True:

            state = extract_state()

            if not state:
                page.wait_for_timeout(25)
                continue

            question = state["question"]
            answers = state["answers"]

            current_state = (
                question,
                tuple(a["text"] for a in answers)
            )

            if current_state == last_state:
                page.wait_for_timeout(25)
                continue

            break


        # ----------------------------------------------
        # DISPLAY
        # ----------------------------------------------

        print("\n" + "=" * 60)
        print("QUESTION:")
        print(question)

        print("\nOPTIONS:")

        for i, option in enumerate(answers):
            print(
                f"{chr(65 + i)}. {option['text']}"
            )


        # ----------------------------------------------
        # ASK AI (retries here, without re-fetching the DOM,
        # as long as the question on screen hasn't changed)
        # ----------------------------------------------

        answer_index = -1

        while answer_index == -1:

            # Bail out of this question if the page has moved on
            # (e.g. someone answered it manually) instead of
            # hammering the AI for a question that's gone.
            fresh_state = extract_state()
            if fresh_state:
                fresh_key = (
                    fresh_state["question"],
                    tuple(a["text"] for a in fresh_state["answers"])
                )
                if fresh_key != current_state:
                    print("\nQuestion changed underneath us — moving on.")
                    break

            try:

                decision = choose_answer(
                    question,
                    answers
                )

                print("\nRAW AI RESPONSE:")
                print(repr(decision))

                if not decision:
                    print("Empty AI response. Retrying...")
                    page.wait_for_timeout(50)
                    continue

                selected = str(
                    decision.get("answer", "")
                ).strip().lower()

                print("SELECTED:", repr(selected))

                if not selected:
                    print("AI answer is empty. Retrying...")
                    page.wait_for_timeout(50)
                    continue

            except Exception as e:
                print("\nAI ERROR:")
                print(repr(e))
                print("Retrying...")
                page.wait_for_timeout(50)
                continue

            answer_index = find_answer_index(selected, answers)

            if answer_index == -1:
                print("\nAI answer does not match an option.")
                print("AI:", repr(selected))
                print("Retrying...")
                page.wait_for_timeout(50)

        if answer_index == -1:
            # Question changed under us — skip straight to next loop
            last_state = current_state
            continue


        # ----------------------------------------------
        # A/B/C/D + 1/2/3/4
        # ----------------------------------------------

        letter = chr(65 + answer_index)
        number = answer_index + 1
        answer_text = answers[answer_index]["text"]


        # ----------------------------------------------
        # DISPLAY
        # ----------------------------------------------

        print("\n" + "=" * 60)

        print("\033[1;97;44m")
        print(f"        ANSWER: {letter} / {number}")
        print(f"        {answer_text}")
        print("\033[0m")

        print("=" * 60)


        # ----------------------------------------------
        # SAVE QUESTION
        # ----------------------------------------------

        last_state = current_state


    except Exception as e:

        print("\n[!] ERROR:")
        print(repr(e))

        print(
            "[!] Retrying in 3s "
            "without closing browser..."
        )

        page.wait_for_timeout(3000)