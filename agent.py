from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(
    api_key=API_KEY
)

# name = input("What is your name? ")


def llm_call(history: list) -> str:
    response = client.responses.create(
        model="gpt-5.4-nano-2026-03-17",
        input=history
    )
    return response.output_text

def conversation():
    history = []

    text = input()

    while text != "end":
        history.append({"role": "user", "content": text})
        response = llm_call(history)
        history.append({"role": "assistant", "content": response})
        print(response)
        text = input()

    print(history)

if __name__ == "__main__":
    # conversation()
    response = client.responses.create(
    model="gpt-5.6",
    input=[
        {"role": "user", "content": "knock knock."},
        {"role": "assistant", "content": "Who's there?"},
        {"role": "user", "content": "Orange."},
        ],
    )

    print(response.output_text)

# every diciotnary should be 1 message back&forth. 
# so now I have a dictionary with all my questions... how do I put memory into this...
