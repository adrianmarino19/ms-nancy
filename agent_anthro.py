from dotenv import load_dotenv
import os

import anthropic

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")



client = anthropic.Anthropic()

message = client.messages.create(
  model="claude-haiku-4-5",
  max_tokens=1024,
  messages=[{
    "role": "user",
    "content": "Hello, Claude"
  }]
)

print(message.content[0].text)