"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Council members - list of OpenRouter model identifiers (실제 사용 가능한 무료 모델)
COUNCIL_MODELS = [
    "tngtech/tng-r1t-chimera:free",           # 무료 - 163K context
    "openrouter/bert-nebulon-alpha",          # 무료 - 256K context
    "x-ai/grok-4.1-fast:free",                # 무료 - 2M context
    "kwaipilot/kat-coder-pro:free",           # 무료 - 256K context
]

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = "tngtech/tng-r1t-chimera:free"  # 무료

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Data directory for conversation storage
DATA_DIR = "data/conversations"
