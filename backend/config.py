"""
Configuration Management
Centralized configuration for all services and agents.
Supports both development and production environments.
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Base configuration"""
    
    # GCP Configuration
    GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "your-project-id")
    GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")
    
    # LLM Configuration
    LLM_MODEL = os.getenv("LLM_MODEL", "gemini-1.5-pro")
    USE_MOCK_LLM = os.getenv("USE_MOCK_LLM", "true").lower() == "true"
    
    # Database Configuration
    FIRESTORE_DATABASE = os.getenv("FIRESTORE_DATABASE", "(default)")
    USE_FIRESTORE = os.getenv("USE_FIRESTORE", "true").lower() == "true"
    
    # Pub/Sub Configuration
    USE_MOCK_PUBSUB = os.getenv("USE_MOCK_PUBSUB", "true").lower() == "true"
    PUBSUB_PROJECT_ID = os.getenv("PUBSUB_PROJECT_ID", GCP_PROJECT_ID)
    
    # Agent Configuration
    CRITIC_AGENT_ENABLED = os.getenv("CRITIC_AGENT_ENABLED", "true").lower() == "true"
    CRITIC_EFFICIENCY_THRESHOLD = float(os.getenv("CRITIC_EFFICIENCY_THRESHOLD", "0.15"))
    CRITIC_CONFIDENCE_THRESHOLD = float(os.getenv("CRITIC_CONFIDENCE_THRESHOLD", "0.75"))
    
    # API Configuration
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("PORT", os.getenv("API_PORT", "8080")))
    API_DEBUG = os.getenv("API_DEBUG", "true").lower() == "true"
    
    # Knowledge Graph Configuration
    KNOWLEDGE_GRAPH_MAX_DEPTH = int(os.getenv("KNOWLEDGE_GRAPH_MAX_DEPTH", "5"))
    
    # Redis Configuration
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Auth Configuration
    SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", str(7 * 24 * 3600)))  # 7 days

    # Logging Configuration
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    USE_MOCK_LLM = True
    USE_MOCK_PUBSUB = True
    USE_FIRESTORE = False
    API_DEBUG = True


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    USE_MOCK_LLM = False
    USE_MOCK_PUBSUB = False
    USE_FIRESTORE = True
    API_DEBUG = False


class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    USE_MOCK_LLM = True
    USE_MOCK_PUBSUB = True
    USE_FIRESTORE = False
    TESTING = True
    API_DEBUG = True


def get_config(environment: Optional[str] = None) -> Config:
    """Get configuration based on environment"""
    
    if environment is None:
        environment = os.getenv("ENVIRONMENT", "development").lower()
    
    if environment == "production":
        return ProductionConfig()
    elif environment == "testing":
        return TestingConfig()
    else:
        return DevelopmentConfig()
