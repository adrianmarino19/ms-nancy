from typing import Any
from openai import OpenAI
from dotenv import load_dotenv
import os
import json
import pathlib

from prompts.system_prompt import SYSTEM_PROMPT
from agent_class import Agent
from tools import tools, tools_dict, get_name, sumdrian


nancy = Agent(
    system_prompt=SYSTEM_PROMPT,
    tools=tools,
    tools_dict= tools_dict,
    )


if __name__ == "__main__":
    print(nancy.chat())
