from pathlib import Path
from playwright.sync_api import sync_playwright


URL = "https://quizbounty.com"

PROFILE_DIR = Path(__file__).parent / "edge_profile"

playwright = sync_playwright().start()

context = playwright.chromium.launch_persistent_context(
    user_data_dir=str(PROFILE_DIR),
    executable_path=r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    headless=False,
    viewport={
        "width": 800,
        "height": 900,
    },
)

page = (
    context.pages[0]
    if context.pages
    else context.new_page()
)

page.goto(
    URL,
    wait_until="domcontentloaded"
)

print("Edge opened.")
print("Current URL:", page.url)