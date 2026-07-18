from curses import use_default_colors


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

tools_dict = {"get_name": get_name, "sumdrian": sumdrian}

def use_tool(function):
    return 
