// LLM client configuration for document extraction.
// Primary: GPT-4o (best multimodal/vision model for document understanding)
// Fallback: Claude Sonnet 4 (strong alternative with good vision capabilities)

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

// Fallback chain: tries GPT-4o first, falls back to Claude Sonnet on any failure
// (network error, rate limit, invalid response, etc.)
client<llm> ExtractorWithFallback {
  provider fallback
  options {
    strategy [GPT4o, AnthropicSonnet]
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
