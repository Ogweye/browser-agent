from quizbounty.browser import page

page.wait_for_selector("h1")

question = page.locator("h1").inner_text()

buttons = page.locator("button")

answers = []

for i in range(buttons.count()):

    text = buttons.nth(i).inner_text()

    letter = text.split("\n")[0].replace(".", "").strip()

    option = text.split("\n")[-1].strip()

    answers.append({
        "index": i,
        "letter": letter,
        "text": option
    })

print(question)
print(answers)