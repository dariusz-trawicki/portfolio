import asyncio
from openai import AsyncOpenAI

client = AsyncOpenAI(
    api_key="dummy",
    base_url="http://localhost:8080/v1"
)

async def main():
    response = await client.chat.completions.create(
        model="mistral",
        messages=[
            {"role": "system", "content": "Jesteś bardzo pomocnym asystentem"},
            {"role": "user", "content": "Witaj świecie"}
        ],
        temperature=0.5
    )

    print(response.choices[0].message.content)

if __name__ == "__main__":
    asyncio.run(main())
