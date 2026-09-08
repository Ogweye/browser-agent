import threading

from quizbounty.browser import page
from quizbounty.ai import choose_answer

print("Waiting for the quiz to start...")

last_state = None

# ----------------------------------------------
# EVENT-DRIVEN STATE (replaces polling)
# ----------------------------------------------

question_ready = threading.Event()
latest_state = {}
state_lock = threading.Lock()

# Confirmed against a saved snapshot of the live quiz DOM: the
# question is a plain <h2>, options are plain <button> elements — no
# .question-text/.answer-option/.answer-text classes exist on this
# site (that was a wrong guess from an earlier round). The page also
# renders 4 empty, aria-hidden, opacity:0 decoy buttons ahead of the
# 4 real ones, so those are excluded explicitly rather than relying
# on the empty-text check alone.

WATCHER_JS = """
() => {
    if (window.__quizWatcherAttached) return;
    window.__quizWatcherAttached = true;

    const emit = () => {

        const question = document.querySelector('h2');
        if (!question) return;

        const qs = getComputedStyle(question);
        if (
            qs.display === "none" ||
            qs.visibility === "hidden" ||
            question.offsetParent === null
        ) return;

        const options = [...document.querySelectorAll('button')]
            .filter(option => {
                if (option.getAttribute('aria-hidden') === 'true') return false;
                const s = getComputedStyle(option);
                return (
                    s.display !== "none" &&
                    s.visibility !== "hidden" &&
                    parseFloat(s.opacity) > 0 &&
                    option.offsetParent !== null
                );
            })
            .map((option, index) => {
                const value = option.innerText.trim();
                if (!value) return null;
                return { index, text: value };
            })
            .filter(Boolean);

        const questionText = question.innerText.trim();
        if (!questionText || !options.length) return;

        window.onQuestionChange({
            question: questionText,
            answers: options
        });
    };

    const observer = new MutationObserver(emit);
    observer.observe(document.documentElement, {
        childList: true,
        subtree: true,
        characterData: true
    });

    // Catch a question that's already on screen at attach time
    emit();
}
"""

# Standalone, on-demand version of the same extraction — used during
# AI retries so a stuck question doesn't depend on waiting for another
# DOM mutation that may never come.
EXTRACT_JS = """
() => {
    const question = document.querySelector('h2');
    if (!question) return null;

    const qs = getComputedStyle(question);
    if (
        qs.display === "none" ||
        qs.visibility === "hidden" ||
        question.offsetParent === null
    ) return null;

    const options = [...document.querySelectorAll('button')]
        .filter(option => {
            if (option.getAttribute('aria-hidden') === 'true') return false;
            const s = getComputedStyle(option);
            return (
                s.display !== "none" &&
                s.visibility !== "hidden" &&
                parseFloat(s.opacity) > 0 &&
                option.offsetParent !== null
            );
        })
        .map((option, index) => {
            const value = option.innerText.trim();
            if (!value) return null;
            return { index, text: value };
        })
        .filter(Boolean);

    const questionText = question.innerText.trim();
    if (!questionText || !options.length) return null;

    return { question: questionText, answers: options };
}
"""


def _on_question_change(state):
    with state_lock:
        latest_state.clear()
        latest_state.update(state)
    question_ready.set()


def attach_watcher():
    """(Re)inject the MutationObserver watcher into the page."""
    try:
        page.evaluate(WATCHER_JS)
        print("[i] Watcher attached/confirmed on:", page.url)
    except Exception as e:
        print("\n[!] Failed to attach watcher:", repr(e))


def extract_state():
    """On-demand synchronous state read — independent of the observer."""
    try:
        return page.evaluate(EXTRACT_JS)
    except Exception:
        return None


def find_answer_index(selected, answers):
    """Exact match first, then a loose contains-match fallback so small
    formatting differences don't burn extra AI calls."""
    for i, option in enumerate(answers):
        if option["text"].strip().lower() == selected:
            return i

    for i, option in enumerate(answers):
        opt_text = option["text"].strip().lower()
        if selected in opt_text or opt_text in selected:
            return i

    return -1


# Expose the callback once — survives navigations
print("[i] Registering onQuestionChange binding...")
page.expose_function("onQuestionChange", _on_question_change)
print("[i] Binding registered.")

# Re-attach the watcher every time the page (re)loads, e.g. on a full
# navigation the old MutationObserver would otherwise die with it
page.on("load", lambda: attach_watcher())

# Also re-attach on client-side route changes (Next.js pushState-style
# navigation doesn't fire "load", but does fire this)
page.on(
    "framenavigated",
    lambda frame: attach_watcher() if frame == page.main_frame else None
)
print("[i] Event listeners registered.")

# Initial attach
print("[i] Current page URL:", page.url)
print("[i] Waiting for load state...")
try:
    page.wait_for_load_state(timeout=10000)
    print("[i] Load state reached.")
except Exception as e:
    print("[i] wait_for_load_state timed out/errored (continuing):", repr(e))

print("[i] Calling attach_watcher()...")
attach_watcher()
print("[i] Setup complete, entering main loop.")


while True:

    try:

        # ----------------------------------------------
        # WAIT FOR NEW QUESTION (event-driven, no polling)
        # ----------------------------------------------

        while True:

            got_event = question_ready.wait(timeout=0.3)

            if got_event:
                question_ready.clear()
                with state_lock:
                    if not latest_state:
                        continue
                    state = dict(latest_state)
            else:
                # Safety net: no mutation event in the last 300ms.
                # Check the DOM directly so a missed/failed observer
                # attach can't stall the script forever.
                state = extract_state()
                if not state:
                    continue

            question = state["question"]
            answers = state["answers"]

            current_state = (
                question,
                tuple(answer["text"] for answer in answers)
            )

            # Same question fired again (unrelated mutation) = keep waiting
            if current_state == last_state:
                continue

            break


        # ----------------------------------------------
        # DISPLAY QUESTION
        # ----------------------------------------------

        print("\n" + "=" * 60)
        print("QUESTION:")
        print(question)

        print("\nOPTIONS:")
        for i, option in enumerate(answers):
            print(f"{chr(65 + i)}. {option['text']}")

        print("=" * 60)


        # ----------------------------------------------
        # ASK AI — retries without depending on another DOM
        # mutation firing; checks the live DOM directly instead
        # ----------------------------------------------

        answer_index = -1

        while answer_index == -1:

            # Bail if the page has moved on to a different question
            # (e.g. it was answered another way) instead of retrying
            # forever against a question that's already gone.
            fresh = extract_state()
            if fresh:
                fresh_key = (
                    fresh["question"],
                    tuple(a["text"] for a in fresh["answers"])
                )
                if fresh_key != current_state:
                    print("\nQuestion changed underneath us — moving on.")
                    break

            try:
                decision = choose_answer(question, answers)

                print("\nRAW AI RESPONSE:")
                print(repr(decision))

                if not decision:
                    print("Empty AI response. Retrying...")
                    page.wait_for_timeout(50)
                    continue

                selected = str(decision.get("answer", "")).strip().lower()
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
            # Question changed under us before we got a match
            last_state = current_state
            continue


        # ----------------------------------------------
        # A/B/C/D + 1/2/3/4
        # ----------------------------------------------

        letter = chr(65 + answer_index)
        number = answer_index + 1
        answer_text = answers[answer_index]["text"]


        # ----------------------------------------------
        # DISPLAY ANSWER
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
        print("[!] Retrying in 3s without closing browser...")
        page.wait_for_timeout(3000)
# from browser import page
# from ai import choose_answer

# print("Waiting for the quiz to start...")

# last_state = None

# while True:

#     try:

#         while True:

#             question_locator = page.locator("h2:visible")
#             buttons = page.locator("button:visible")

#             if question_locator.count() == 0:
#                 page.wait_for_timeout(25)
#                 continue

#             question = question_locator.first.inner_text().strip()

#             if not question:
#                 page.wait_for_timeout(25)
#                 continue

#             texts = buttons.all_inner_texts()

#             answers = []

#             for text in texts:

#                 text = text.strip()

#                 if text:
#                     answers.append({
#                         "text": text
#                     })

#             if not answers:
#                 page.wait_for_timeout(25)
#                 continue

#             current_state = (
#                 question,
#                 tuple(answer["text"] for answer in answers)
#             )

#             # Same question = keep waiting
#             if current_state == last_state:
#                 page.wait_for_timeout(25)
#                 continue

#             break


#         # -----------------------------------------------
#         # DISPLAY QUESTION
#         # -----------------------------------------------

#         print("\n" + "=" * 70)

#         print("QUESTION:")
#         print(question)

#         print("\nOPTIONS:")

#         for i, option in enumerate(answers):

#             tag = chr(65 + i)

#             print(f"{tag}. {option['text']}")


#         # -----------------------------------------------
#         # ASK AI
#         # -----------------------------------------------

#         decision = choose_answer(question, answers)

#         selected_answer = decision.get("answer", "").strip().lower()

#         answer_tag = "?"

#         for i, option in enumerate(answers):

#             if option["text"].strip().lower() == selected_answer:

#                 answer_tag = chr(65 + i)

#                 break


#         # -----------------------------------------------
#         # DISPLAY ANSWER
#         # -----------------------------------------------

#         print("\n" + "=" * 70)

#         print("\033[1;97;44m")
#         print(f"   ANSWER: {answer_tag}")
#         print("\033[0m")

#         print("=" * 70)


#         # Remember this exact question/options combination
#         last_state = current_state

#     except Exception as e:
#         print(f"\n[!] Error during quiz loop: {e}")
#         print("[!] Retrying in 3s without closing browser...")
#         page.wait_for_timeout(3000)
#         continue
# from browser import driver
# from ai import choose_answer
# import time

# print("Waiting for the quiz to start...")

# last_state = None

# while True:

#     try:

#         while True:

#             # Find visible question
#             questions = driver.find_elements("h2")

#             visible_questions = [
#                 q for q in questions
#                 if q.is_displayed()
#             ]

#             if not visible_questions:
#                 time.sleep(0.05)
#                 continue

#             question = visible_questions[0].text.strip()

#             if not question:
#                 time.sleep(0.05)
#                 continue

#             # Find visible buttons
#             all_buttons = driver.find_elements("button")

#             visible_buttons = [
#                 button for button in all_buttons
#                 if button.is_displayed()
#             ]

#             answers = []

#             for button in visible_buttons:

#                 text = button.text.strip()

#                 if text:
#                     answers.append({
#                         "text": text,
#                         "element": button
#                     })

#             if not answers:
#                 time.sleep(0.05)
#                 continue

#             current_state = (
#                 question,
#                 tuple(answer["text"] for answer in answers)
#             )

#             # Same question
#             if current_state == last_state:
#                 time.sleep(0.05)
#                 continue

#             break

#         # -----------------------------------------------
#         # DISPLAY QUESTION
#         # -----------------------------------------------

#         print("\n" + "=" * 70)

#         print("QUESTION:")
#         print(question)

#         print("\nOPTIONS:")

#         for i, option in enumerate(answers):

#             tag = chr(65 + i)

#             print(f"{tag}. {option['text']}")

#         print("=" * 70)

#         # -----------------------------------------------
#         # ASK AI
#         # -----------------------------------------------

#         decision = choose_answer(question, answers)

#         selected_answer = decision.get("answer", "").strip().lower()

#         answer_tag = "?"

#         selected_button = None

#         for i, option in enumerate(answers):

#             if option["text"].strip().lower() == selected_answer:

#                 answer_tag = chr(65 + i)
#                 selected_button = option["element"]

#                 break

#         # -----------------------------------------------
#         # DISPLAY ANSWER
#         # -----------------------------------------------

#         print("\n" + "=" * 70)

#         print("\033[1;97;44m")
#         print(f"   ANSWER: {answer_tag}")
#         print("\033[0m")

#         print("=" * 70)

#         # -----------------------------------------------
#         # CLICK ANSWER
#         # -----------------------------------------------

#         if selected_button:

#             selected_button.click()

#             print(f"[+] Clicked answer {answer_tag}")

#         else:

#             print("[!] AI answer did not match any option")

#         # Remember question
#         last_state = current_state

#         time.sleep(0.2)

#     except Exception as e:

#         print(f"\n[!] Error during quiz loop: {e}")
#         print("[!] Retrying in 3s without closing browser...")

#         time.sleep(3)
# from browser import driver
# from ai import choose_answer
# from concurrent.futures import ThreadPoolExecutor

# print("Waiting for the quiz to start...")

# last_state = None

# executor = ThreadPoolExecutor(max_workers=1)

# while True:

#     try:

#         while True:

#             question_locator = page.locator("h2:visible")
#             buttons = page.locator("button:visible")

#             if question_locator.count() == 0:
#                 page.wait_for_timeout(25)
#                 continue

#             question = question_locator.first.inner_text().strip()

#             if not question:
#                 page.wait_for_timeout(25)
#                 continue

#             texts = buttons.all_inner_texts()

#             answers = []

#             for text in texts:
#                 text = text.strip()

#                 if text:
#                     answers.append({
#                         "text": text
#                     })

#             if not answers:
#                 page.wait_for_timeout(25)
#                 continue

#             current_state = (
#                 question,
#                 tuple(answer["text"] for answer in answers)
#             )

#             if current_state == last_state:
#                 page.wait_for_timeout(25)
#                 continue

#             break

#         # -----------------------------------------------
#         # DISPLAY QUESTION IMMEDIATELY
#         # -----------------------------------------------

#         print("\n" + "=" * 70)
#         print("QUESTION:")
#         print(question)

#         print("\nOPTIONS:")

#         for i, option in enumerate(answers):
#             tag = chr(65 + i)
#             print(f"{tag}. {option['text']}")

#         print("=" * 70)

#         # -----------------------------------------------
#         # SEND TO AI
#         # -----------------------------------------------

#         future = executor.submit(
#             choose_answer,
#             question,
#             answers
#         )

#         # Wait for this particular AI request
#         decision = future.result()

#         # -----------------------------------------------
#         # PROCESS ANSWER
#         # -----------------------------------------------

#         selected_answer = decision.get("answer", "").strip().lower()

#         answer_tag = "?"

#         for i, option in enumerate(answers):

#             if option["text"].strip().lower() == selected_answer:
#                 answer_tag = chr(65 + i)
#                 break

#         # -----------------------------------------------
#         # DISPLAY ANSWER
#         # -----------------------------------------------

#         print("\n" + "=" * 70)
#         print("\033[1;97;44m")
#         print(f"   ANSWER: {answer_tag}")
#         print("\033[0m")
#         print("=" * 70)

#         last_state = current_state

#     except Exception as e:

#         print(f"\n[!] Error during quiz loop: {e}")
#         print("[!] Retrying in 3s without closing browser...")

#         page.wait_for_timeout(3000)
#         continue

# # # from browser import page
# # # from ai import choose_answer

# # # print("Waiting for the quiz to start...")

# # # last_state = None

# # # while True:

# # #     while True:

# # #         question_locator = page.locator("h2:visible")
# # #         buttons = page.locator("button:visible")

# # #         if question_locator.count() == 0:
# # #             page.wait_for_timeout(25)
# # #             continue

# # #         question = question_locator.first.inner_text().strip()

# # #         if not question:
# # #             page.wait_for_timeout(25)
# # #             continue

# # #         texts = buttons.all_inner_texts()

# # #         answers = []

# # #         for text in texts:

# # #             text = text.strip()

# # #             if text:
# # #                 answers.append({
# # #                     "text": text
# # #                 })

# # #         if not answers:
# # #             page.wait_for_timeout(25)
# # #             continue

# # #         current_state = (
# # #             question,
# # #             tuple(answer["text"] for answer in answers)
# # #         )

# # #         # Same question = keep waiting
# # #         if current_state == last_state:
# # #             page.wait_for_timeout(25)
# # #             continue

# # #         break


# # #     # -----------------------------------------------
# # #     # DISPLAY QUESTION
# # #     # -----------------------------------------------

# # #     print("\n" + "=" * 70)

# # #     print("QUESTION:")
# # #     print(question)

# # #     print("\nOPTIONS:")

# # #     for i, option in enumerate(answers):

# # #         tag = chr(65 + i)

# # #         print(f"{tag}. {option['text']}")


# # #     # -----------------------------------------------
# # #     # ASK AI
# # #     # -----------------------------------------------

# # #     decision = choose_answer(question, answers)

# # #     selected_answer = decision["answer"].strip().lower()

# # #     answer_tag = "?"

# # #     for i, option in enumerate(answers):

# # #         if option["text"].strip().lower() == selected_answer:

# # #             answer_tag = chr(65 + i)

# # #             break


# # #     # -----------------------------------------------
# # #     # DISPLAY ANSWER
# # #     # -----------------------------------------------

# # #     print("\n" + "=" * 70)

# # #     print("\033[1;97;44m")
# # #     print(f"   ANSWER: {answer_tag}")
# # #     print("\033[0m")

# # #     print("=" * 70)


# # #     # Remember this exact question/options combination
# # #     last_state = current_state
# # # from browser import page
# # # from ai import choose_answer


# # # print("Waiting for the quiz to start...")


# # # # Wait until a question and visible answer options actually exist
# # # while True:

# # #     question_locator = page.locator("h2:visible")
# # #     buttons = page.locator("button:visible")

# # #     if question_locator.count() > 0 and buttons.count() > 0:

# # #         question = question_locator.first.inner_text().strip()

# # #         if question:
# # #             break

# # #     page.wait_for_timeout(200)


# # # print("Quiz detected.")
# # # print("Waiting for questions...\n")


# # # last_state = None


# # # while True:

# # #     # --------------------------------------------------
# # #     # WAIT FOR A NEW QUESTION
# # #     # --------------------------------------------------

# # #     while True:

# # #         question_locator = page.locator("h2:visible")
# # #         buttons = page.locator("button:visible")

# # #         if question_locator.count() == 0:
# # #             page.wait_for_timeout(200)
# # #             continue

# # #         question = question_locator.first.inner_text().strip()

# # #         if not question:
# # #             page.wait_for_timeout(200)
# # #             continue

# # #         answers = []

# # #         for i in range(buttons.count()):

# # #             button = buttons.nth(i)

# # #             if not button.is_visible():
# # #                 continue

# # #             if not button.is_enabled():
# # #                 continue

# # #             text = button.inner_text().strip()

# # #             if not text:
# # #                 continue

# # #             answers.append({
# # #                 "text": text
# # #             })

# # #         if not answers:
# # #             page.wait_for_timeout(200)
# # #             continue

# # #         current_state = (
# # #             question,
# # #             tuple(answer["text"] for answer in answers)
# # #         )

# # #         # Ignore the previous question
# # #         if current_state == last_state:
# # #             page.wait_for_timeout(200)
# # #             continue

# # #         # Allow the page to finish rendering
# # #         page.wait_for_timeout(150)

# # #         # Re-read everything before sending it to the AI
# # #         verify_question_locator = page.locator("h2:visible")
# # #         verify_buttons = page.locator("button:visible")

# # #         if verify_question_locator.count() == 0:
# # #             continue

# # #         verify_question = (
# # #             verify_question_locator.first.inner_text().strip()
# # #         )

# # #         verify_answers = []

# # #         for i in range(verify_buttons.count()):

# # #             button = verify_buttons.nth(i)

# # #             if not button.is_visible():
# # #                 continue

# # #             if not button.is_enabled():
# # #                 continue

# # #             text = button.inner_text().strip()

# # #             if text:
# # #                 verify_answers.append(text)

# # #         verify_state = (
# # #             verify_question,
# # #             tuple(verify_answers)
# # #         )

# # #         # Something changed while the page was rendering.
# # #         # Don't send an unstable question to the AI.
# # #         if verify_state != current_state:
# # #             print("Page changed while loading. Rechecking...")
# # #             continue

# # #         break


# # #     # --------------------------------------------------
# # #     # DISPLAY QUESTION
# # #     # --------------------------------------------------

# # #     print("\n" + "=" * 70)
# # #     print("QUESTION:")
# # #     print(question)

# # #     print("\nOPTIONS:")

# # #     for option in answers:
# # #         print("•", option["text"])


# # #     # --------------------------------------------------
# # #     # ASK AI
# # #     # --------------------------------------------------

# # #     decision = choose_answer(question, answers)

# # #     answer = decision["answer"].strip()


# # #     # --------------------------------------------------
# # #     # DISPLAY ANSWER
# # #     # --------------------------------------------------

# # #     print("\n" + "=" * 70)

# # #     print("\033[1;97;44m")
# # #     print("   ANSWER: " + answer.upper() + "   ")
# # #     print("\033[0m")

# # #     print("=" * 70)


    
# # #     last_state = current_state

# # # # from browser import page
# # # # from ai import choose_answer

# # # # input("Log in manually, then press Enter...")

# # # # page.wait_for_selector("h2", timeout=0)

# # # # last_question = ""

# # # # while True:

# # # #     # Wait until a NEW question appears
# # # #     page.wait_for_function(
# # # #         """
# # # #         (oldQuestion) => {
# # # #             const q = document.querySelector("h2");
# # # #             return q && q.innerText.trim() !== oldQuestion;
# # # #         }
# # # #         """,
# # # #         last_question,
# # # #         timeout=0
# # # #     )

# # # #     question = page.locator("h2").first.inner_text().strip()
# # # #     last_question = question

# # # #     buttons = page.locator("button:visible")

# # # #     answers = []

# # # #     for i in range(buttons.count()):

# # # #         button = buttons.nth(i)

# # # #         if not button.is_visible():
# # # #             continue

# # # #         if not button.is_enabled():
# # # #             continue

# # # #         text = button.inner_text().strip()

# # # #         if text == "":
# # # #             continue

# # # #         answers.append({
# # # #             "text": text,
# # # #             "button": button
# # # #         })

# # # #     print("\nQuestion:")
# # # #     print(question)

# # # #     print("\nOptions:")
# # # #     for option in answers:
# # # #         print("-", option["text"])

# # # #     decision = choose_answer(question, answers)

# # # #     print("\nAI:", decision)

# # # #     answer = decision["answer"].strip().lower()

# # # #     # Make sure we're still on the same question
# # # #     current_question = page.locator("h2").first.inner_text().strip()

# # # #     if current_question != question:
# # # #         print("Question changed before clicking. Skipping...")
# # # #         continue

# # # #     clicked = False

# # # #     for option in answers:

# # # #         if option["text"].strip().lower() == answer:

# # # #             if option["button"].is_visible() and option["button"].is_enabled():

# # # #                 option["button"].click()

# # # #                 clicked = True

# # # #                 print("Clicked:", option["text"])

# # # #             else:

# # # #                 print("Matching answer is no longer visible.")

# # # #             break

# # # #     if not clicked:
# # # #         print("No matching answer found.")

# # # #     input("\nPress Enter for next question...")