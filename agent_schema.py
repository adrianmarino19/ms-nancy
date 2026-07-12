from typing import Any
from openai import OpenAI
from dotenv import load_dotenv
import os
import json
import pathlib

from prompts.system_prompt import SYSTEM_PROMPT

load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")

class Agent:
    def __init__(
        self, 
        system_prompt: str, 
        tools: list = None,
        history: list = None,
        previous_response_id: str = None,
        client = OpenAI(api_key=API_KEY)
    ):
        self.system_prompt = system_prompt
        self.tools = tools if tools is not None else []
        self.history = history if history is not None else []
        self.previous_response_id = previous_response_id
    

    def llm_call(self, text):
        response = self.client.responses.create(
            model="gpt-5.4-nano-2026-03-17",
            instructions=self.system_prompt,
            input=text,
            previous_response_id=self.previous_response_id,
            tools=self.tools,
        )

        return response.output, response.output_text, response.id
    
    def chat(self, text):
        previous_response_id = self.previous_response_id
        text = input()
        
        self.history.append({"role": "user", "content": text})
        
        while text != "end":
            output, output_text, previous_id = self.llm_call(
                self.history,
                self.previous_response_id,
                self.tools
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
            
            
        
        pass