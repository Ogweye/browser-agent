from quizbounty.browser import page

def read_question():

    question = page.locator(".question-text").inner_text().strip()

    options = page.locator(".answer-option")

    answers = []

    for i in range(options.count()):

        answers.append({

            "id": i,

            "key": options.nth(i).locator(".key").inner_text(),

            "text": options.nth(i).locator(".answer-text").inner_text()

        })

    return {
        "question": question,
        "answers": answers
    }