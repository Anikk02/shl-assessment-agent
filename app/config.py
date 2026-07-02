# app/config.py
import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load .env file FIRST
load_dotenv()


@dataclass
class Config:
    """Application configuration"""
    
    # Application
    app_name: str = "SHL Assessment Recommender"
    app_version: str = "1.0.0"
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    environment: str = os.getenv("ENVIRONMENT", "production")
    
    # LLM Configuration
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "gemini-2.0-flash-exp")
    llm_provider: str = os.getenv("LLM_PROVIDER", "gemini")
    
    # Catalog Configuration
    catalog_url: str = "https://tcp-us-prod-rnd.shl.com/voiceRater/shl-ai-hiring/shl_product_catalog.json"
    catalog_path: str = "data/catalog.json"
    index_path: str = "data/catalog.index"
    
    # Agent Configuration
    max_turns: int = 8
    max_recommendations: int = 10
    min_recommendations: int = 1
    
    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_file: str = "data/logs/app.log"
    
    # API
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))


# Singleton instance
config = Config()

# Debug: Print API key status (remove after fixing)
print(f"API Key loaded: {'YES' if config.llm_api_key else 'NO'}")
print(f"API Key length: {len(config.llm_api_key) if config.llm_api_key else 0}")