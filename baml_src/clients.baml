// LLM client configuration for document extraction.
// Four providers with automatic fallback: GPT-4o → Claude Sonnet → Gemini → Grok

client<llm> GPT4o {
  provider openai
  retry_policy Exponential
  options {
    model "gpt-4o"
    api_key env.OPENAI_API_KEY
  }
}

client<llm> AnthropicSonnet {
  provider anthropic
  retry_policy Exponential
  options {
    model "claude-sonnet-4-20250514"
    api_key env.ANTHROPIC_API_KEY
  }
}

client<llm> Gemini {
  provider google-ai
  retry_policy Exponential
  options {
    model "gemini-2.5-flash"
    api_key env.GOOGLE_API_KEY
  }
}

client<llm> Grok {
  provider openai-generic
  retry_policy Exponential
  options {
    model "grok-3"
    base_url "https://api.x.ai/v1"
    api_key env.XAI_API_KEY
  }
}

// Fallback chain: tries each provider in order on any failure
// (network error, rate limit, invalid response, etc.)
client<llm> ExtractorWithFallback {
  provider fallback
  options {
    strategy [GPT4o, AnthropicSonnet, Gemini, Grok]
  }
}

retry_policy Exponential {
  max_retries 2
  strategy {
    type exponential_backoff
    delay_ms 300
    multiplier 1.5
    max_delay_ms 10000
  }
}
