from quizbounty.browser import page
from quizbounty.scrapper import read_question
from quizbounty.ai import choose_answer
from quizbounty.actions import click_answer

page.goto("YOUR_URL")

while True:

    data = read_question()

    print(data)

    decision = choose_answer(data)

    print(decision)

    click_answer(decision["id"])

    break