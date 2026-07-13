import requests  
from config.settings import (
    NINEROUTER_BASE_URL, 
    LLM_MAX_TOKENS, 
    LLM_TEMPERATURE
)

def call_llm(system_prompt: str, user_message: str, response_schema: type, model: str):
    """
    Memanggil LLM (OpenAI-compatible via 9Router).
    Mengembalikan data sesuai dengan response_schema (Pydantic model).
    """
    headers = {"Content-Type": "application/json"}
    
    if not NINEROUTER_BASE_URL:
        raise ValueError("NINEROUTER_BASE_URL tidak diatur di environment/settings.")

    # Panggil via 9Router (OpenAI-compatible format)
    url = f"{NINEROUTER_BASE_URL}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "response_format": {"type": "json_object"},
        "temperature": LLM_TEMPERATURE,
        "max_tokens": LLM_MAX_TOKENS,
        "stream": False  # Memaksa agar tidak stream
    }
    response = requests.post(url, headers=headers, json=payload)
    
    try:
        response.raise_for_status()
        
        # Cek apakah router memaksa mengirim Stream (SSE) meski stream=False
        if response.text.strip().startswith("data:"):
            # Parsing Server-Sent Events (SSE)
            content = ""
            for line in response.text.splitlines():
                line = line.strip()
                if line.startswith("data: ") and line != "data: [DONE]":
                    import json
                    try:
                        chunk = json.loads(line[6:])
                        if "choices" in chunk and len(chunk["choices"]) > 0:
                            delta = chunk["choices"][0].get("delta", {})
                            if "content" in delta:
                                content += delta["content"]
                    except json.JSONDecodeError:
                        pass
        else:
            # Parsing JSON standard
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
    except Exception as e:
        raise RuntimeError(f"Gagal memanggil API LLM.\nStatus: {response.status_code}\nResponse Body: {response.text[:1000]}...") from e

    import re
    # 1. Coba cari di dalam blok markdown ```json ... ``` atau ``` ... ```
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
    if match:
        content = match.group(1).strip()
    else:
        # 2. Jika tidak ada blok markdown, cari kurung kurawal terluar (JSON Object)
        start = content.find('{')
        end = content.rfind('}')
        if start != -1 and end != -1 and end > start:
            content = content[start:end+1].strip()
        else:
            content = content.strip()

    try:
        return response_schema.model_validate_json(content)
    except Exception as e:
        raise ValueError(f"Gagal melakukan validasi Pydantic.\nLLM Output: {content}") from e