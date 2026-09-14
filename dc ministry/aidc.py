import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PROMPT = """
You are an expert at multiple-choice questions.

Think through the question carefully before answering.
Use your general knowledge.
Compare every option before deciding.

Rules:
- Exactly one option is correct.
- Your answer MUST exactly match one of the provided options.
- Do not explain.
- Return ONLY JSON.

{
  "answer": "Exact option text"
}
"""

def choose_answer(question, answers):

    payload = {
        "question": question,
        "answers": [a["text"] for a in answers]
    }

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": json.dumps(payload)
            }
        ]
    )

    return json.loads(response.choices[0].message.content)