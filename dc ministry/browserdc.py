from playwright.sync_api import sync_playwright

playwright = sync_playwright().start()

context = playwright.chromium.launch_persistent_context(
    user_data_dir="./profile",
    headless=False,
    viewport=None,
    args=[
        "--start-maximized",
        "--disable-blink-features=AutomationControlled"
    ]
)

page = context.new_page()

print("Paste the sign-in link into the browser.")
input("After you're logged in and on the quiz page, press Enter...")