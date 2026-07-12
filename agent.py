from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(
    api_key=API_KEY
)

# name = input("What is your name? ")


def llm_call(
    text: list,
    previous_response_id: str | None = None,
    tools: dict | None = None,
    ) -> str:
    """
    OpenAI API wrapper
    """    
    response = client.responses.create(
        model="gpt-5.4-nano-2026-03-17",
        input=text,
        previous_response_id=previous_response_id,
        tools=tools
    )
    return response.output, response.output_text, response.id, 


tools = [
    {
        "name": "get_name",
        "parameters": None,
        "type": "function",
        "description": "Get the user's name.",
        "strict": False,
    }
]    

def get_name():
    return "The name of him is Adrian. He is your Master"



def conversation():
    previous_id = None
    text = input()

    history = [{"role": "user", "content": text}]
    while text != "end":
        output, output_text, previous_id = llm_call(
            history,
            previous_id,
            tools
        )
        print(output)
        text = input()
    

if __name__ == "__main__":
    conversation()
