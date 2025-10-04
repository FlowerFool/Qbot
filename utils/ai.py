import aiohttp
import json

async def generate_ai_post_with_settings(work_data: dict, settings: tuple):
    _, ai_provider, model_name, api_key, api_url, temperature, max_tokens, is_active, *_ = settings
    if not is_active:
        raise ValueError("Нейросеть не активна")
    if not api_url:
        api_url = "https://api.openai.com/v1/chat/completions"

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": f"Сгенерируй пост для работы: {work_data}"}],
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(api_url, headers=headers, json=payload) as resp:
            data = await resp.json()
            return data["choices"][0]["message"]["content"]
