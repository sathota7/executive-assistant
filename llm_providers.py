# llm_providers.py
"""
Abstract base class and implementations for different LLM providers.
Supports: Claude (Anthropic), ChatGPT (OpenAI), Grok (xAI), Llama (via Ollama), Gemini (Google)
"""
import os
import json
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv

load_dotenv()


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the LLM provider with API key."""
        pass
    
    @abstractmethod
    def create_message(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tools: Optional[List[Dict]] = None,
        max_tokens: int = 4096,
        model: Optional[str] = None
    ) -> Any:
        """
        Create a message with the LLM.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            system_prompt: System prompt/instructions
            tools: Optional list of tool definitions
            max_tokens: Maximum tokens to generate
            model: Optional model name (uses default if not provided)
        
        Returns:
            Response object from the provider
        """
        pass
    
    @abstractmethod
    def extract_text_from_response(self, response: Any) -> str:
        """Extract text content from the response object."""
        pass
    
    @abstractmethod
    def extract_tool_use(self, response: Any) -> List[Dict]:
        """Extract tool use calls from the response (if any)."""
        pass
    
    @abstractmethod
    def get_stop_reason(self, response: Any) -> str:
        """Get the stop reason from the response."""
        pass


class ClaudeProvider(LLMProvider):
    """Claude (Anthropic) provider implementation."""
    
    def __init__(self, api_key: Optional[str] = None):
        try:
            import anthropic
        except ImportError:
            raise ImportError("anthropic package required. Install with: pip install anthropic")
        
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")
        
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.default_model = "claude-sonnet-4-20250514"
    
    def create_message(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tools: Optional[List[Dict]] = None,
        max_tokens: int = 4096,
        model: Optional[str] = None
    ) -> Any:
        model = model or self.default_model
        return self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            tools=tools,
            messages=messages
        )
    
    def extract_text_from_response(self, response: Any) -> str:
        text_parts = []
        for block in response.content:
            if hasattr(block, 'text'):
                text_parts.append(block.text)
        return ''.join(text_parts)
    
    def extract_tool_use(self, response: Any) -> List[Dict]:
        tool_uses = []
        for block in response.content:
            if hasattr(block, 'type') and block.type == 'tool_use':
                tool_uses.append({
                    'id': block.id,
                    'name': block.name,
                    'input': block.input
                })
        return tool_uses
    
    def get_stop_reason(self, response: Any) -> str:
        return response.stop_reason or 'end_turn'


class ChatGPTProvider(LLMProvider):
    """ChatGPT (OpenAI) provider implementation."""
    
    def __init__(self, api_key: Optional[str] = None):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package required. Install with: pip install openai")
        
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
        
        self.client = OpenAI(api_key=self.api_key)
        self.default_model = "gpt-4-turbo-preview"
    
    def create_message(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tools: Optional[List[Dict]] = None,
        max_tokens: int = 4096,
        model: Optional[str] = None
    ) -> Any:
        model = model or self.default_model
        
        # Convert messages format and prepend system prompt
        formatted_messages = [{"role": "system", "content": system_prompt}]
        
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            
            # Handle tool results
            if isinstance(content, list):
                # Convert Anthropic tool result format to OpenAI format
                for item in content:
                    if item.get('type') == 'tool_result':
                        formatted_messages.append({
                            "role": "tool",
                            "tool_call_id": item.get('tool_use_id'),
                            "content": item.get('content', '')
                        })
            else:
                formatted_messages.append({"role": role, "content": content})
        
        # Convert tools format if provided
        formatted_tools = None
        if tools:
            formatted_tools = []
            for tool in tools:
                formatted_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.get("name"),
                        "description": tool.get("description"),
                        "parameters": tool.get("input_schema", {})
                    }
                })
        
        return self.client.chat.completions.create(
            model=model,
            messages=formatted_messages,
            tools=formatted_tools,
            max_tokens=max_tokens
        )
    
    def extract_text_from_response(self, response: Any) -> str:
        if response.choices and len(response.choices) > 0:
            return response.choices[0].message.content or ""
        return ""
    
    def extract_tool_use(self, response: Any) -> List[Dict]:
        tool_uses = []
        if response.choices and len(response.choices) > 0:
            message = response.choices[0].message
            if hasattr(message, 'tool_calls') and message.tool_calls:
                for tool_call in message.tool_calls:
                    tool_uses.append({
                        'id': tool_call.id,
                        'name': tool_call.function.name,
                        'input': json.loads(tool_call.function.arguments)
                    })
        return tool_uses
    
    def get_stop_reason(self, response: Any) -> str:
        if response.choices and len(response.choices) > 0:
            finish_reason = response.choices[0].finish_reason
            if finish_reason == 'tool_calls':
                return 'tool_use'
            return finish_reason or 'stop'
        return 'stop'


class GrokProvider(LLMProvider):
    """Grok (xAI) provider implementation."""
    
    def __init__(self, api_key: Optional[str] = None):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package required for Grok. Install with: pip install openai")
        
        self.api_key = api_key or os.getenv('GROK_API_KEY') or os.getenv('XAI_API_KEY')
        if not self.api_key:
            raise ValueError("GROK_API_KEY or XAI_API_KEY not found in environment")
        
        # Grok uses OpenAI-compatible API
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.x.ai/v1"
        )
        self.default_model = "grok-beta"
    
    def create_message(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tools: Optional[List[Dict]] = None,
        max_tokens: int = 4096,
        model: Optional[str] = None
    ) -> Any:
        # Grok uses OpenAI-compatible format
        model = model or self.default_model
        formatted_messages = [{"role": "system", "content": system_prompt}]
        
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            if isinstance(content, list):
                for item in content:
                    if item.get('type') == 'tool_result':
                        formatted_messages.append({
                            "role": "tool",
                            "tool_call_id": item.get('tool_use_id'),
                            "content": item.get('content', '')
                        })
            else:
                formatted_messages.append({"role": role, "content": content})
        
        formatted_tools = None
        if tools:
            formatted_tools = []
            for tool in tools:
                formatted_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.get("name"),
                        "description": tool.get("description"),
                        "parameters": tool.get("input_schema", {})
                    }
                })
        
        return self.client.chat.completions.create(
            model=model,
            messages=formatted_messages,
            tools=formatted_tools,
            max_tokens=max_tokens
        )
    
    def extract_text_from_response(self, response: Any) -> str:
        if response.choices and len(response.choices) > 0:
            return response.choices[0].message.content or ""
        return ""
    
    def extract_tool_use(self, response: Any) -> List[Dict]:
        tool_uses = []
        if response.choices and len(response.choices) > 0:
            message = response.choices[0].message
            if hasattr(message, 'tool_calls') and message.tool_calls:
                for tool_call in message.tool_calls:
                    tool_uses.append({
                        'id': tool_call.id,
                        'name': tool_call.function.name,
                        'input': json.loads(tool_call.function.arguments)
                    })
        return tool_uses
    
    def get_stop_reason(self, response: Any) -> str:
        if response.choices and len(response.choices) > 0:
            finish_reason = response.choices[0].finish_reason
            if finish_reason == 'tool_calls':
                return 'tool_use'
            return finish_reason or 'stop'
        return 'stop'


class LlamaProvider(LLMProvider):
    """Llama (via Ollama) provider implementation."""
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        try:
            import requests
        except ImportError:
            raise ImportError("requests package required. Install with: pip install requests")
        
        self.base_url = base_url or os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        self.default_model = os.getenv('OLLAMA_MODEL', 'llama3')
        self.api_key = api_key  # Usually not needed for local Ollama
    
    def create_message(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tools: Optional[List[Dict]] = None,
        max_tokens: int = 4096,
        model: Optional[str] = None
    ) -> Any:
        import requests
        
        model = model or self.default_model
        
        # Ollama format: combine system prompt with messages
        formatted_messages = [{"role": "system", "content": system_prompt}]
        
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            if isinstance(content, str):
                formatted_messages.append({"role": role, "content": content})
            # Note: Ollama may not support tool calling in the same way
        
        # Note: Tool support in Ollama is limited
        if tools:
            print("Warning: Tool calling support in Ollama may be limited")
        
        response = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": model,
                "messages": formatted_messages,
                "options": {
                    "num_predict": max_tokens
                }
            },
            timeout=120
        )
        response.raise_for_status()
        return response.json()
    
    def extract_text_from_response(self, response: Any) -> str:
        if isinstance(response, dict):
            return response.get('message', {}).get('content', '')
        return str(response)
    
    def extract_tool_use(self, response: Any) -> List[Dict]:
        # Ollama doesn't natively support tool calling like other providers
        # This would need custom parsing or a wrapper
        return []
    
    def get_stop_reason(self, response: Any) -> str:
        if isinstance(response, dict):
            return response.get('done', True) and 'stop' or 'continue'
        return 'stop'


class GeminiProvider(LLMProvider):
    """Gemini (Google) provider implementation."""
    
    def __init__(self, api_key: Optional[str] = None):
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError("google-generativeai package required. Install with: pip install google-generativeai")
        
        self.api_key = api_key or os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_AI_API_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY or GOOGLE_AI_API_KEY not found in environment")
        
        genai.configure(api_key=self.api_key)
        self.default_model = "gemini-pro"
    
    def create_message(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tools: Optional[List[Dict]] = None,
        max_tokens: int = 4096,
        model: Optional[str] = None
    ) -> Any:
        import google.generativeai as genai
        
        model = model or self.default_model
        
        # Convert messages format for Gemini
        # Gemini uses a different format - combine system with first user message
        history = []
        current_content = system_prompt + "\n\n"
        
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            
            if role == 'user' and isinstance(content, str):
                current_content += f"User: {content}\n"
            elif role == 'assistant' and isinstance(content, str):
                current_content += f"Assistant: {content}\n"
        
        # Note: Gemini tool support requires different setup
        if tools:
            print("Warning: Tool calling in Gemini requires function declaration setup")
        
        gen_model = genai.GenerativeModel(model)
        response = gen_model.generate_content(current_content)
        return response
    
    def extract_text_from_response(self, response: Any) -> str:
        if hasattr(response, 'text'):
            return response.text
        return str(response)
    
    def extract_tool_use(self, response: Any) -> List[Dict]:
        # Gemini tool calling requires function declarations
        # This is a simplified version
        return []
    
    def get_stop_reason(self, response: Any) -> str:
        if hasattr(response, 'stop_reason'):
            return str(response.stop_reason)
        return 'stop'


def get_llm_provider(provider_name: Optional[str] = None, **kwargs) -> LLMProvider:
    """
    Factory function to get the appropriate LLM provider.
    
    Args:
        provider_name: Name of provider ('claude', 'chatgpt', 'grok', 'llama', 'gemini')
                      If None, uses LLM_PROVIDER env var or defaults to 'claude'
        **kwargs: Additional arguments to pass to provider (api_key, base_url, etc.)
    
    Returns:
        LLMProvider instance
    """
    provider_name = (provider_name or os.getenv('LLM_PROVIDER', 'claude')).lower()
    
    providers = {
        'claude': ClaudeProvider,
        'anthropic': ClaudeProvider,
        'chatgpt': ChatGPTProvider,
        'openai': ChatGPTProvider,
        'gpt': ChatGPTProvider,
        'grok': GrokProvider,
        'xai': GrokProvider,
        'llama': LlamaProvider,
        'ollama': LlamaProvider,
        'gemini': GeminiProvider,
        'google': GeminiProvider
    }
    
    provider_class = providers.get(provider_name)
    if not provider_class:
        raise ValueError(
            f"Unknown provider: {provider_name}. "
            f"Supported providers: {', '.join(set(providers.keys()))}"
        )
    
    try:
        return provider_class(**kwargs)
    except Exception as e:
        raise ValueError(f"Failed to initialize {provider_name} provider: {e}")


# json module already imported at top

