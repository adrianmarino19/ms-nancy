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
        tools_dict: dict = None, 
        history: list = None,
        client = OpenAI(api_key=API_KEY)
    ):
        self.system_prompt = system_prompt
        self.tools = tools if tools is not None else []
        self.tools_dict = tools_dict if tools_dict is not None else {}
        self.history = history if history is not None else []
        self.client = client
    

    def llm_call(self, text, tools = None):
        response = self.client.responses.create(
            model="gpt-5.4-nano-2026-03-17",
            instructions=self.system_prompt,
            input=text,
            tools=self.tools,
        )

        return response.output, response.output_text
    
    def chat(self):
        text = input()
        
        self.history.append({"role": "user", "content": text})
        
        while text != "end":
            output, output_text = self.llm_call(
                self.history,
                self.tools
            )

            response_type = output[0].type
            
            if response_type == "function_call":
                function_name, arguments = output[0].name, output[0].arguments
                self.history.append(output[0])

                if function_name in self.tools_dict:
                    args = json.loads(arguments)

                    try:
                        tool_result = self.tools_dict[function_name](**args)
                        
                        self.history.append(
                            {
                                "type": "function_call_output",
                                "call_id": output[0].call_id,
                                "output": tool_result,
                            }
                        )
                    except Exception as e:
                        tool_result = f"Tool failed: {e}"

                        self.history.append(
                            {
                                "type": "function_call_output",
                                "call_id": output[0].call_id,
                                "output": tool_result,
                            }
                        )
                else:
                    tool_result = f"Unknown tool: {function_name}"

                    self.history.append(
                        {
                            "type": "function_call_output",
                            "call_id": output[0].call_id,
                            "output": tool_result,
                        }
                    )
            else: 
                print(output_text)
                self.history.append({"role": "assistant", "content": output_text})

                text = input()
                self.history.append({"role": "user", "content": text})
