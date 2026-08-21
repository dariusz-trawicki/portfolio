# /// script
# dependencies = [
#   "ollama",
# ]
# ///


import ollama

response = ollama.chat(
    model="qwen3:4b-instruct-2507-q4_K_M",
    messages=[{"role": "user", "content": "What is the name of the highest mountain?"}],
)

print(response["message"]["content"])
