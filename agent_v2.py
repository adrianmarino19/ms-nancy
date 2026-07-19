import os
import json
import pathlib

from typing import Any
from openai import OpenAI
from dotenv import load_dotenv

from utils.prompts import SYSTEM_PROMPT
from utils.tools import tools, tools_dict, get_name, sumdrian
from agent_class import Agent


nancy = Agent(
    system_prompt=SYSTEM_PROMPT,
    tools=tools,
    tools_dict=tools_dict,
)


if __name__ == "__main__":
    nancy.chat()
