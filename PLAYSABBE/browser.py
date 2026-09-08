from pathlib import Path

from playwright.sync_api import sync_playwright


URL = "https://play.isabeeapp.com/"

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

PROFILE_DIR = Path(__file__).parent / "edge_profile"


playwright = sync_playwright().start()

context = playwright.chromium.launch_persistent_context(
    user_data_dir=str(PROFILE_DIR),
    executable_path=EDGE_PATH,
    headless=False,
    viewport={
    "width": 800,
    "height": 900,
    },
)

if context.pages:
    page = context.pages[0]
else:
    page = context.new_page()


page.goto(
    URL,
    wait_until="domcontentloaded",
)


def get_quiz():
    """
    Read the currently visible question and four options.
    """

    return page.evaluate(
        """
        () => {

            const questionEl =
                document.querySelector(".q-text-large");

            if (!questionEl) {
                return null;
            }

            const buttons = [
                ...document.querySelectorAll(".quiz-opt-btn")
            ];

            if (buttons.length !== 4) {
                return null;
            }

            const question =
                questionEl.innerText.trim();

            if (!question) {
                return null;
            }

            const options = buttons.map(
                (button, index) => {

                    const letterEl =
                        button.querySelector(
                            ".opt-letter-circle"
                        );

                    const textEl =
                        button.querySelector(
                            ".opt-text"
                        );

                    return {
                        index: index,
                        letter: letterEl
                            ? letterEl.innerText.trim()
                            : "",
                        text: textEl
                            ? textEl.innerText.trim()
                            : ""
                    };
                }
            );

            if (
                options.some(
                    option =>
                        !option.letter ||
                        !option.text
                )
            ) {
                return null;
            }

            return {
                question: question,
                options: options
            };
        }
        """
    )


def wait_for_next_question(
    old_question,
    timeout_ms=30000
):
    """
    Wait until the visible question changes.

    The function returns the new quiz data.
    """

    try:

        page.wait_for_function(
            """
            oldQuestion => {

                const el =
                    document.querySelector(
                        ".q-text-large"
                    );

                if (!el) {
                    return false;
                }

                const current =
                    el.innerText.trim();

                return (
                    current &&
                    current !== oldQuestion
                );
            }
            """,
            old_question,
            timeout=timeout_ms,
        )

        return get_quiz()

    except Exception:
        return None