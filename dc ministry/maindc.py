from browserdc import page
from aidc import choose_answer

while True:

    input("\nPress Enter to answer the next question (Ctrl+C to stop)...")

    # Wait until the quiz question is visible
    page.wait_for_selector("h1", timeout=0)

    question = page.locator("h1").inner_text().strip()

    buttons = page.locator("button")

    answers = []

    for i in range(buttons.count()):

        button = buttons.nth(i)

        full_text = button.inner_text().strip()

        # Ignore close buttons or empty buttons
        if full_text == "×" or full_text == "":
            continue

        # Remove A., B., C., etc.
        if "." in full_text:
            option_text = full_text.split(".", 1)[1].strip()
        else:
            option_text = full_text

        answers.append({
            "index": i,
            "text": option_text
        })

    print("\nQuestion:")
    print(question)

    print("\nAnswers:")
    for a in answers:
        print(a)


    # Ask AI
    decision = choose_answer(question, answers)

    print("\nAI Decision:")
    print(decision)


    selected = decision["answer"].strip().lower()

    clicked = False


    # Click matching answer
    for answer in answers:

        if answer["text"].lower() == selected:

            print("Clicking:", answer["text"])

            buttons.nth(answer["index"]).click()

            clicked = True
            break


    if not clicked:
        print("Couldn't find:", decision["answer"])


    print("\nAnswer completed.")