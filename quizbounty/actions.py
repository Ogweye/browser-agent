from quizbounty.browser import page

def click_answer(answer_id):

    page.locator(".answer-option").nth(answer_id).click()