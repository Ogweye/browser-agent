import time

from browser import (
    get_quiz,
    wait_for_next_question,
)

from ai import choose_gemini_answer


print()
print("=" * 60)
print("PLAYSABBE AI ASSIST")
print("=" * 60)
print("Edge is running.")
print("Answer the quiz yourself.")
print("Gemini will provide the answer.")
print()


last_state = None
question_number = 0


while True:

    try:

        # ------------------------------------------------
        # GET CURRENT QUESTION
        # ------------------------------------------------

        quiz = get_quiz()

        if quiz is None:
            time.sleep(0.05)
            continue


        question = quiz["question"]
        options = quiz["options"]


        # ------------------------------------------------
        # BUILD QUESTION STATE
        # ------------------------------------------------

        current_state = (
            question,
            tuple(
                option["text"]
                for option in options
            )
        )


        # ------------------------------------------------
        # IGNORE SAME QUESTION
        # ------------------------------------------------

        if current_state == last_state:

            time.sleep(0.05)
            continue


        question_number += 1
        last_state = current_state


        # ------------------------------------------------
        # DISPLAY QUESTION
        # ------------------------------------------------

        print()
        print("=" * 60)

        print(
            f"QUESTION #{question_number}"
        )

        print()
        print(question)

        print()
        print("OPTIONS:")

        for option in options:

            print(
                f"{option['letter']}. "
                f"{option['text']}"
            )

        print("=" * 60)


        # ------------------------------------------------
        # ASK GEMINI
        # ------------------------------------------------

        start = time.perf_counter()

        result = choose_gemini_answer(
            question,
            options
        )

        elapsed = (
            time.perf_counter()
            - start
        )


        # ------------------------------------------------
        # DISPLAY ANSWER
        # ------------------------------------------------

        if result:

            letter = result["answer"]
            model = result["model"]


            matching_option = None

            for option in options:

                if option["letter"] == letter:

                    matching_option = option
                    break


            print()

            # ------------------------------------------------
            # PROMINENT ANSWER DISPLAY
            # ------------------------------------------------

            print("\033[1;97;44m")

            print()
            print(
                " " * 8 +
                "████████████████████████████"
            )

            print(
                " " * 8 +
                "█       GEMINI ANSWER       █"
            )

            print(
                " " * 8 +
                "████████████████████████████"
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
                f"        MODEL: {model}"
            )

            print(
                f"        TIME: {elapsed:.2f}s"
            )

            print()

            print(
                " " * 8 +
                "████████████████████████████"
            )

            print()

            print("\033[0m")


        else:

            print()

            print("\033[1;97;41m")

            print(
                "        NO VALID GEMINI RESPONSE"
            )

            print("\033[0m")


        # ------------------------------------------------
        # YOU ANSWER MANUALLY
        # ------------------------------------------------

        print()
        print(
            "Answer manually, then waiting "
            "for next question..."
        )


        # ------------------------------------------------
        # WAIT FOR NEXT QUESTION
        # ------------------------------------------------

        next_quiz = wait_for_next_question(
            old_question=question,
            timeout_ms=30000,
        )


        if next_quiz:

            print(
                "Next question detected."
            )

        else:

            print(
                "Still waiting for the next question..."
            )


    except KeyboardInterrupt:

        print()
        print("Stopping...")
        break


    except Exception as e:

        print()
        print(
            "MAIN ERROR:",
            repr(e)
        )

        time.sleep(0.25)