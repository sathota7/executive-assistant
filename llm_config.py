# llm_config.py
"""
Utilities for checking LLM provider availability and managing default provider configuration.
"""
import os
import json
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

# Provider configuration with their API key env var names
PROVIDER_CONFIG = {
    'claude': {
        'name': 'Claude (Anthropic)',
        'env_vars': ['ANTHROPIC_API_KEY'],
        'primary': True
    },
    'chatgpt': {
        'name': 'ChatGPT (OpenAI)',
        'env_vars': ['OPENAI_API_KEY'],
        'primary': True
    },
    'grok': {
        'name': 'Grok (xAI)',
        'env_vars': ['GROK_API_KEY', 'XAI_API_KEY'],
        'primary': True
    },
    'llama': {
        'name': 'Llama (Ollama)',
        'env_vars': [],  # No API key required, but needs Ollama running
        'primary': False
    },
    'gemini': {
        'name': 'Gemini (Google)',
        'env_vars': ['GEMINI_API_KEY', 'GOOGLE_AI_API_KEY'],
        'primary': True
    }
}


def check_provider_availability(provider_id: str) -> bool:
    """
    Check if a provider has valid credentials configured.
    
    Args:
        provider_id: Provider ID ('claude', 'chatgpt', 'grok', 'llama', 'gemini')
    
    Returns:
        True if provider has credentials/config, False otherwise
    """
    if provider_id not in PROVIDER_CONFIG:
        return False
    
    config = PROVIDER_CONFIG[provider_id]
    
    # Check if API keys are set
    if config['env_vars']:
        for env_var in config['env_vars']:
            if os.getenv(env_var):
                return True
        return False
    
    # For Llama (Ollama), check if base URL is accessible (optional check)
    if provider_id == 'llama':
        try:
            import requests
            base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
            # Try to ping Ollama (quick check)
            response = requests.get(f"{base_url}/api/tags", timeout=2)
            return response.status_code == 200
        except:
            # If Ollama not running, still consider it available (user can start it)
            # This allows selecting Llama even if Ollama is temporarily down
            return True
    
    return False


def get_available_providers() -> Dict[str, Dict]:
    """
    Get list of all providers with their availability status.
    
    Returns:
        Dictionary mapping provider_id to {'name': str, 'available': bool}
    """
    result = {}
    for provider_id, config in PROVIDER_CONFIG.items():
        result[provider_id] = {
            'name': config['name'],
            'available': check_provider_availability(provider_id)
        }
    return result


def get_default_provider() -> Optional[str]:
    """
    Get the default LLM provider from state file.
    
    Returns:
        Provider ID or None if not set
    """
    state_file = 'llm_provider_state.json'
    if os.path.exists(state_file):
        try:
            with open(state_file, 'r') as f:
                state = json.load(f)
                return state.get('default_provider')
        except:
            pass
    return None


def set_default_provider(provider_id: str) -> bool:
    """
    Set the default LLM provider in state file.
    
    Args:
        provider_id: Provider ID to set as default
    
    Returns:
        True if successful, False otherwise
    """
    if provider_id not in PROVIDER_CONFIG:
        return False
    
    # Verify provider is available before setting as default
    if not check_provider_availability(provider_id):
        return False
    
    state_file = 'llm_provider_state.json'
    try:
        state = {'default_provider': provider_id}
        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving provider state: {e}")
        return False


def get_effective_provider() -> str:
    """
    Get the effective provider to use (default or first available).
    
    Returns:
        Provider ID
    """
    # Check stored default first
    default = get_default_provider()
    if default and check_provider_availability(default):
        return default
    
    # Fall back to first available provider
    available = get_available_providers()
    for provider_id, info in available.items():
        if info['available']:
            return provider_id
    
    # Fall back to env var or claude
    return os.getenv('LLM_PROVIDER', 'claude')

