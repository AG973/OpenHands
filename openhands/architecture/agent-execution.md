# Agent Execution & LLM Flow

When the agent executes inside the sandbox, it makes LLM calls through LiteLLM or directly via the native Ollama provider:

```mermaid
sequenceDiagram
    autonumber
    participant User as User (Browser)
    participant AS as Agent Server
    participant Agent as Agent<br/>(CodeAct)
    participant LLM as LLM Class
    participant Ollama as Ollama<br/>(Local or Cloud)
    participant Lite as LiteLLM
    participant Provider as LLM Provider<br/>(OpenAI, Anthropic, etc.)
    participant AES as Action Execution Server

    Note over User,AES: Agent Loop - LLM Call Flow

    User->>AS: WebSocket: User message
    AS->>Agent: Process message
    Note over Agent: Build prompt from state

    Agent->>LLM: completion(messages, tools)
    Note over LLM: Apply config (model, temp, etc.)

    alt Using Ollama (Local or Cloud)
        LLM->>Ollama: POST /api/chat
        Note over Ollama: Native provider (bypasses LiteLLM)
        Ollama-->>LLM: Response
    else Using Other Provider
        LLM->>Lite: {provider}/{model}
        Lite->>Provider: Direct API call
        Provider-->>Lite: Response
        Lite-->>LLM: ModelResponse
    end

    Note over LLM: Track metrics (cost, tokens)
    LLM-->>Agent: Parsed response

    Note over Agent: Parse action from response
    AS->>User: WebSocket: Action event

    Note over User,AES: Action Execution

    AS->>AES: HTTP: Execute action
    Note over AES: Run command/edit file
    AES-->>AS: Observation
    AS->>User: WebSocket: Observation event

    Note over Agent: Update state
    Note over Agent: Loop continues...
```

### LLM Components

| Component | Purpose | Location |
|-----------|---------|----------|
| **LLM Class** | Wrapper with retries, metrics, config | `openhands/llm/llm.py` |
| **Ollama Provider** | Native Ollama client (bypasses LiteLLM) | `openhands/llm/ollama_provider.py` |
| **LiteLLM** | Universal LLM API adapter (free library) | External library |
| **LLM Registry** | Manages multiple LLM instances | `openhands/llm/llm_registry.py` |

### Model Routing

```
User selects model
        │
        ▼
┌───────────────────┐
│ Provider?         │
└───────────────────┘
        │
        ├── ollama/llama3.2       ──► Native Ollama provider (local)
        │                              Direct HTTP to localhost:11434
        │
        ├── anthropic/claude-3-5  ──► Direct to Anthropic API
        │                              (User's API key via LiteLLM)
        │
        ├── openai/gpt-4          ──► Direct to OpenAI API
        │                              (User's API key via LiteLLM)
        │
        └── azure/gpt-4           ──► Direct to Azure OpenAI
                                       (User's API key via LiteLLM)
```

### Local LLM Setup

For local Ollama models, set these in your config:
- `provider = "ollama"`
- `model = "ollama/llama3.2-vision:11b"` (or any Ollama model)
- `base_url = "http://localhost:11434"`
- `api_key = "ollama"` (placeholder, not used)
