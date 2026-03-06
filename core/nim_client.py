"""
Novel OS - NVIDIA NIM API Client

Integrates NVIDIA NIM models for AI-powered novel writing.
Supports all NIM-compatible models including Llama, Mixtral, and others.

Usage:
    Set your API key:
        - Environment variable: NVIDIA_NIM_API_KEY=nvapi-xxxxx
        - Or pass directly: NIMClient(api_key="nvapi-xxxxx")
    
    Then use with the orchestrator:
        python orchestrator.py --nim-key nvapi-xxxxx write --chapter 1
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
import json
import time
import requests
from pathlib import Path
from typing import Optional, Dict, Any, List, Generator

# Import token management (should always be available since it's in the same directory)
try:
    from token_manager import (
        estimate_tokens, estimate_tokens_for_messages, get_model_limits,
        trim_to_token_budget, SmartPromptBuilder, ChunkedWriter,
        ChapterSummarizer, print_token_report, ModelLimits, DEFAULT_LIMITS,
    )
    TOKEN_MANAGER_AVAILABLE = True
except ImportError:
    TOKEN_MANAGER_AVAILABLE = False


# ===== Default Configuration =====

NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"

# Recommended NIM models for novel writing (ordered by quality for creative tasks)
NIM_MODELS = {
    "llama-3.1-70b": "meta/llama-3.1-70b-instruct",
    "llama-3.1-405b": "meta/llama-3.1-405b-instruct",
    "llama-3.1-8b": "meta/llama-3.1-8b-instruct",
    "mixtral-8x22b": "mistralai/mixtral-8x22b-instruct-v0.1",
    "mixtral-8x7b": "mistralai/mixtral-8x7b-instruct-v0.1",
    "nemotron-70b": "nvidia/llama-3.1-nemotron-70b-instruct",
    "qwen2.5-72b": "qwen/qwen2.5-72b-instruct",
}

# Default model for each agent type
AGENT_MODEL_DEFAULTS = {
    "architect": "llama-3.1-70b",     # Good at planning/structure
    "scribe": "llama-3.1-70b",        # Best for creative prose
    "editor": "llama-3.1-70b",        # Good at refinement
    "continuity": "llama-3.1-70b",    # Good at analysis
    "style_curator": "llama-3.1-70b", # Good at style matching
}


class NIMClient:
    """
    Client for NVIDIA NIM API.
    
    Compatible with OpenAI-style chat completions API that NIM exposes.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = NIM_BASE_URL,
        default_model: str = "llama-3.1-70b",
    ):
        self.api_key = api_key or os.environ.get("NVIDIA_NIM_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        
        if not self.api_key:
            raise ValueError(
                "NVIDIA NIM API key required.\n"
                "Set via environment variable: NVIDIA_NIM_API_KEY=nvapi-xxxxx\n"
                "Or pass directly: NIMClient(api_key='nvapi-xxxxx')"
            )
    
    def _get_model_id(self, model_name: str) -> str:
        """Resolve a short model name to a full NIM model ID."""
        if model_name in NIM_MODELS:
            return NIM_MODELS[model_name]
        # If it looks like a full model ID already, use it directly
        if "/" in model_name:
            return model_name
        # Default fallback
        return NIM_MODELS.get(self.default_model, self.default_model)
    
    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        top_p: float = 0.9,
        stream: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Send a chat completion request to NIM.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name (short or full). Defaults to self.default_model
            temperature: Sampling temperature (0.0-1.0). Higher = more creative
            max_tokens: Maximum tokens in response
            top_p: Nucleus sampling parameter
            stream: Whether to stream the response
            
        Returns:
            Full API response as dict, or streamed text if stream=True
        """
        model_id = self._get_model_id(model or self.default_model)
        
        payload = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "stream": stream,
            **kwargs,
        }
        
        url = f"{self.base_url}/chat/completions"
        
        try:
            response = requests.post(
                url,
                headers=self._get_headers(),
                json=payload,
                stream=stream,
                timeout=120,
            )
            response.raise_for_status()
            
            if stream:
                return self._handle_stream(response)
            else:
                return response.json()
                
        except requests.exceptions.HTTPError as e:
            error_detail = ""
            try:
                error_detail = e.response.json()
            except Exception:
                error_detail = e.response.text
            raise RuntimeError(
                f"NIM API error ({e.response.status_code}): {error_detail}"
            ) from e
        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                "Cannot connect to NIM API. Check your network and base URL."
            )
        except requests.exceptions.Timeout:
            raise RuntimeError(
                "NIM API request timed out. The model may be loading or the request is too large."
            )
    
    def _handle_stream(self, response) -> Generator[str, None, None]:
        """Handle streaming response from NIM."""
        for line in response.iter_lines():
            if line:
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
    
    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """
        Simple text generation helper.
        
        Args:
            system_prompt: System instructions for the model
            user_prompt: The user's request/prompt
            model: Model to use
            temperature: Creativity level
            max_tokens: Max response length
            
        Returns:
            Generated text as string
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        result = self.chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        return result["choices"][0]["message"]["content"]
    
    def generate_text_streaming(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Generator[str, None, None]:
        """
        Stream text generation (prints tokens as they arrive).
        
        Yields:
            Text chunks as they arrive from the API
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        return self.chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
    
    def list_available_models(self) -> List[Dict[str, str]]:
        """List available NIM models."""
        try:
            response = requests.get(
                f"{self.base_url}/models",
                headers=self._get_headers(),
                timeout=30,
            )
            response.raise_for_status()
            return response.json().get("data", [])
        except Exception as e:
            print(f"⚠️  Could not list models: {e}")
            return []
    
    def test_connection(self) -> bool:
        """Test if the NIM API connection works."""
        try:
            result = self.generate_text(
                system_prompt="Reply with exactly: OK",
                user_prompt="Test",
                max_tokens=10,
                temperature=0.0,
            )
            print(f"✅ NIM connection successful! Response: {result.strip()}")
            return True
        except Exception as e:
            print(f"❌ NIM connection failed: {e}")
            return False


class AgentRunner:
    """
    Runs Novel OS agents using the NIM API.
    
    Each agent has a system prompt (from agents/<name>/prompt.md) and receives
    task-specific user prompts generated by the orchestrator.
    """
    
    def __init__(self, nim_client: NIMClient, agents_dir: Optional[str] = None):
        self.nim = nim_client
        self.agents_dir = Path(agents_dir) if agents_dir else Path(__file__).parent.parent / "agents"
        self._agent_prompts = {}  # Cache loaded system prompts
        
        # Token management
        if TOKEN_MANAGER_AVAILABLE:
            model_name = nim_client.default_model
            self.model_limits = get_model_limits(model_name)
        else:
            self.model_limits = None
    
    def _load_agent_prompt(self, agent_name: str) -> str:
        """Load an agent's system prompt from disk."""
        if agent_name in self._agent_prompts:
            return self._agent_prompts[agent_name]
        
        # Map agent roles to directory names
        agent_dirs = {
            "architect": "architect",
            "scribe": "scribe",
            "editor": "editor",
            "continuity": "continuity_guardian",
            "continuity_guardian": "continuity_guardian",
            "style_curator": "style_curator",
        }
        
        dir_name = agent_dirs.get(agent_name, agent_name)
        prompt_path = self.agents_dir / dir_name / "prompt.md"
        
        if not prompt_path.exists():
            raise FileNotFoundError(f"Agent prompt not found: {prompt_path}")
        
        prompt = prompt_path.read_text(encoding="utf-8")
        self._agent_prompts[agent_name] = prompt
        return prompt
    
    def run_agent(
        self,
        agent_name: str,
        task_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> str:
        """
        Run a specific agent with a task prompt.
        
        Args:
            agent_name: One of 'architect', 'scribe', 'editor', 'continuity', 'style_curator'
            task_prompt: The task-specific prompt (e.g., chapter writing prompt)
            model: Override the default model for this agent
            temperature: Creativity level
            max_tokens: Max response length
            stream: Whether to stream output to console
            
        Returns:
            Agent's response as string
        """
        system_prompt = self._load_agent_prompt(agent_name)
        
        # Use agent-specific default model if none specified
        if model is None:
            model = AGENT_MODEL_DEFAULTS.get(agent_name, self.nim.default_model)
        
        agent_display = {
            "architect": "🏗️  THE ARCHITECT",
            "scribe": "✍️  THE SCRIBE",
            "editor": "🔍 THE EDITOR",
            "continuity": "🛡️  CONTINUITY GUARDIAN",
            "continuity_guardian": "🛡️  CONTINUITY GUARDIAN",
            "style_curator": "🎨 STYLE CURATOR",
        }
        
        display_name = agent_display.get(agent_name, f"🤖 {agent_name.upper()}")
        print(f"\n{'='*60}")
        print(f"  {display_name} is working...")
        print(f"  Model: {self.nim._get_model_id(model)}")
        print(f"{'='*60}\n")
        
        if stream:
            # Stream tokens to console and collect full response
            chunks = []
            for chunk in self.nim.generate_text_streaming(
                system_prompt=system_prompt,
                user_prompt=task_prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                print(chunk, end="", flush=True)
                chunks.append(chunk)
            print()  # Final newline
            response = "".join(chunks)
        else:
            response = self.nim.generate_text(
                system_prompt=system_prompt,
                user_prompt=task_prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        
        # Report token usage
        if TOKEN_MANAGER_AVAILABLE:
            input_tokens = estimate_tokens(system_prompt) + estimate_tokens(task_prompt)
            output_tokens = estimate_tokens(response)
            print(f"\n   📊 Tokens — Input: ~{input_tokens:,} | Output: ~{output_tokens:,} | Total: ~{input_tokens + output_tokens:,}")
        
        return response
    
    def run_agent_with_context(
        self,
        agent_name: str,
        task_prompt: str,
        context_messages: Optional[List[Dict[str, str]]] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """
        Run an agent with additional context messages (multi-turn).
        
        Useful for follow-up refinements where the agent needs to see
        its previous output and new feedback.
        """
        system_prompt = self._load_agent_prompt(agent_name)
        
        if model is None:
            model = AGENT_MODEL_DEFAULTS.get(agent_name, self.nim.default_model)
        
        messages = [{"role": "system", "content": system_prompt}]
        
        if context_messages:
            messages.extend(context_messages)
        
        messages.append({"role": "user", "content": task_prompt})
        
        result = self.nim.chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        return result["choices"][0]["message"]["content"]


# ===== CLI for standalone testing =====

def main():
    """Test NIM connection and run a quick agent demo."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Novel OS - NIM Client")
    parser.add_argument(
        "--api-key",
        help="NVIDIA NIM API key (or set NVIDIA_NIM_API_KEY env var)",
    )
    parser.add_argument(
        "--model",
        default="llama-3.1-70b",
        help="Model to use (default: llama-3.1-70b)",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test API connection",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List available NIM models",
    )
    parser.add_argument(
        "--agent",
        choices=["architect", "scribe", "editor", "continuity", "style_curator"],
        help="Run a specific agent with a test prompt",
    )
    parser.add_argument(
        "--prompt",
        help="Custom prompt to send to the agent",
    )
    
    args = parser.parse_args()
    
    try:
        client = NIMClient(api_key=args.api_key, default_model=args.model)
    except ValueError as e:
        print(f"❌ {e}")
        return
    
    if args.test:
        client.test_connection()
        return
    
    if args.list_models:
        print("📋 Available NIM Models:")
        print("-" * 60)
        models = client.list_available_models()
        if models:
            for m in models:
                print(f"  • {m.get('id', 'unknown')}")
        else:
            print("  Could not fetch models. Pre-configured models:")
            for short, full in NIM_MODELS.items():
                print(f"  • {short:20s} → {full}")
        return
    
    if args.agent:
        runner = AgentRunner(client)
        prompt = args.prompt or "Create a brief test outline for a mystery novel set in a lighthouse."
        result = runner.run_agent(args.agent, prompt, stream=True)
        print(f"\n{'='*60}")
        print(f"✅ Agent completed. Output length: {len(result)} characters")
        return
    
    # Default: show help
    parser.print_help()


if __name__ == "__main__":
    main()
