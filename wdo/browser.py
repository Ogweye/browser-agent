# from playwright.sync_api import sync_playwright

# import browser

# playwright = sync_playwright().start()

# context = playwright.chromium.launch_persistent_context(
#     user_data_dir="./profile",
#     headless=False,
#     viewport={
#     "width": 800,
#     "height": 900,
#     },
#     args=["--window-size=1600,900"]
# )


# page = context.new_page()

# try:
#     page.goto(
#         "https://www.whodeyonline.com/home",
#         wait_until="domcontentloaded",
#         timeout=60000
#     )
# except Exception as e:
#     print(f"[!] Page load warning: {e}")
#     print("[!] Continuing with the browser...")


from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "https://www.whodeyonline.com/home"

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

page = context.pages[0] if context.pages else context.new_page()

page.goto(URL, wait_until="domcontentloaded")

print("Edge opened.")
print("Current URL:", page.url)

input("Log in normally, then press ENTER here...")

print("Session saved in:", PROFILE_DIR)