from playwright.async_api import async_playwright

PROFILE_PATH = r"C:\Users\USER\browser-agent\tk auto\profiles\account1"


async def start_browser():

    playwright = await async_playwright().start()

    context = await playwright.chromium.launch_persistent_context(
        user_data_dir=PROFILE_PATH,
        headless=False,
        timeout=60000,
    )

    page = context.pages[0] if context.pages else await context.new_page()

    return playwright, context, page