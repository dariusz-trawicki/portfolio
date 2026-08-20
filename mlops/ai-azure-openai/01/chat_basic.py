import os
from openai import AzureOpenAI
from dotenv import load_dotenv
load_dotenv()

client = AzureOpenAI(
  azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT"), 
  api_key = os.getenv("AZURE_OPENAI_KEY"),  
  api_version = "2024-08-01-preview"
)

# Select the model
deployment = os.getenv("AZURE_DEPLOYMENT_NAME")

# Create your first prompt
text_prompt = "How far away is the moon from the earth?"

response = client.chat.completions.create(
  model=deployment,
  messages = [{"role":"system", "content":"You are a helpful assistant."},
              {"role":"user","content":text_prompt},])

print(response.choices[0].message.content)
