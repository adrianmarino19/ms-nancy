from typing import Any
from openai import OpenAI
from dotenv import load_dotenv
import os
import json
import pathlib

from prompts.system_prompt import SYSTEM_PROMPT
from agent_schema import Agent
from tools import tools, get_name, sumdrian


nancy = Agent(
    system_prompt=SYSTEM_PROMPT,
    tools=tools,
)


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