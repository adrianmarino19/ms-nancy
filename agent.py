from typing import Any
from openai import OpenAI
from dotenv import load_dotenv
import os
import json

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
        "type": "function",
        "name": "get_name",
        "parameters": None,
        "description": "Get the user's name.",
        "strict": False,
    },
    {
        "type": "function",
        "name": "sumdrian",
        "description": "Get the sumdrian of two numbers. Sumdrian is a special sum in the Sumdrian planet.",
        "parameters": {
            "type": "object",
            "properties": {
                "x": {
                    "type": "integer",
                    "description": "first integer to add",
                },
                "y": {
                    "type": "integer",
                    "description": "second integer to add",
                },
            },
            "required": ["x", "y"],
            "additionalProperties": False,
        },
        "strict": True,
    }
]   


def get_name():
    return "The name of him is Adrian. He is your Master"

def sumdrian(x, y):
    """
    Calculates the sumdrian of two numbers. 
    Sumdrian is an alternative addition in the Sumdrian planet.
    """
    sum = x + y
    return f"{sum}-drians"


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
        if output[0].type == "function_call":
            if output[0].name == "get_name":
                tool_result = get_name()
                history.append(
                    {
                        "type": "function_call_output",
                        "call_id": output[0].call_id,
                        "output": tool_result,
                    })
            if output[0].name == "sumdrian":
                args = json.loads(output[0].arguments)
                x = args["x"]
                y = args["y"]
                tool_result = sumdrian(x, y)
                
                history.append(
                    {
                        "type": "function_call_output",
                        "call_id": output[0].call_id,
                        "output": tool_result,
                    })
        else: 
            print(output_text)
            text = input()
            history = [{"role": "user", "content": text}]


if __name__ == "__main__":
    conversation()
