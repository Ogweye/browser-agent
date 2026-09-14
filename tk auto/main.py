import asyncio
from quizbounty.browser import start_browser


TIKTOK_URL = "https://www.tiktok.com"


async def main():
    playwright, context, page = await start_browser()

    try:
        await page.goto(
            TIKTOK_URL,
            wait_until="domcontentloaded"
        )

        print("\nTikTok opened.")
        print("Log into your account manually if necessary.")

        input("\nPress ENTER after logging in... ")

        video_url = input("Paste TikTok video URL: ").strip()
        comment = input("Enter comment: ").strip()

        if not video_url:
            print("No video URL supplied.")
            return

        if not comment:
            print("No comment supplied.")
            return

        print("\nOpening video...")

        await page.goto(
            video_url,
            wait_until="domcontentloaded"
        )

        await page.wait_for_timeout(3000)

        print("\n--- BUTTONS ---")

        buttons = page.locator("button")
        count = await buttons.count()

        for i in range(count):
            try:
                text = (await buttons.nth(i).inner_text()).strip()

                if text:
                    print(f"{i}: {text}")

            except Exception:
                pass

        print("\nVideo opened.")
        print(f"Comment: {comment}")

        input("\nPress ENTER to close the browser...")

    finally:
        await context.close()
        await playwright.stop()


if __name__ == "__main__":
    asyncio.run(main())