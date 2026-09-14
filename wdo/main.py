import threading

from browser import page
from ai import choose_answer

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
