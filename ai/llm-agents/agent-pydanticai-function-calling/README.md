# Dice Game Agent (PydanticAI + OpenAI)

This project demonstrates a simple **dice game agent** built with **PydanticAI** and the **OpenAI API**.  
The agent can:
- Answer the current date
- Roll a six-sided die
- Compare the die result with the user's guess
- Personalize responses using the player's name

---

## Features

- Async OpenAI client integration
- Tool-based agent design (dice roll, date, player name)
- Deterministic + random behavior combination
- Example of tool calling and multi-step reasoning
- Beginner-friendly demonstration of PydanticAI

---

## Requirements

- Python **3.12+**
- OpenAI API key

---

## Environment Variables

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your_openai_api_key_here
```

---

## How It Works

1. The OpenAI API key is loaded from environment variables.
2. An asynchronous OpenAI client is initialized.
3. A `PydanticAI` agent is created with a system prompt describing the dice game.
4. Tools are registered:
   - `roll_dice()` – rolls a random number (1–6)
   - `date()` – returns the current date
   - `get_player_name()` – injects the player's name
5. The agent processes a user prompt and decides which tools to call.
6. The final response combines tool results into a natural language answer.


## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install ipykernel
python -m ipykernel install --user --name .venv --display-name "Python (.venv)"
```
