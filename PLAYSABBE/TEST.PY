import os

from dotenv import load_dotenv
from groq import Groq


load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY"),
    timeout=15.0,
    max_retries=0
)


print("Testing Groq...")
print("Model: openai/gpt-oss-120b")


try:

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {
                "role": "user",
                "content": """
Answer this multiple choice question.

Which city was home to the church Paul addressed
in his longest epistle?

A. Corinth
B. Ephesus
C. Rome
D. Philippi

Return ONLY the letter of the correct answer.
"""
            }
        ],
        temperature=0,
        max_tokens=100
    )

    print("\nREQUEST SUCCESSFUL")

    
    print(
        repr(
            getattr(
                response.choices[0].message,
                "reasoning",
                None
            )
        )
    )

except Exception as e:

    print("\nREQUEST FAILED")
    print(type(e).__name__)
    print(str(e))