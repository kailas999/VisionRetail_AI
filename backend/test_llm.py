import asyncio
import os
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv("/app/.env")

async def test_llm():
    api_key = os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("OPENAI_MODEL")
    base_url = os.environ.get("OPENAI_BASE_URL")
    
    print(f"Testing OpenAI API...")
    print(f"Key: {api_key[:5]}...{api_key[-5:] if api_key else 'None'}")
    print(f"Model: {model}")
    print(f"Base URL: {base_url}")
    
    try:
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        response = await client.chat.completions.create(
            model=model or "gpt-5.2",
            messages=[{"role": "user", "content": "Say hello!"}],
            max_tokens=10
        )
        print("\n✅ SUCCESS!")
        print("Response:", response.choices[0].message.content)
    except Exception as e:
        print("\n❌ FAILED!")
        print(f"Error type: {type(e).__name__}")
        print(f"Error details: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_llm())
