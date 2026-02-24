from openai import OpenAI

openai_client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key='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',
  timeout=120.0  # 2 minute timeout for API calls
)
