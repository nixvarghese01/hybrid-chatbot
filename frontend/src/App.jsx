import { useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "/api";

const promptIdeas = [
  "Summarize this topic in five bullets.",
  "Compare two options and recommend one.",
  "Draft a professional email reply.",
  "Explain this concept in simple words.",
];

const resourceLinks = [
  {
    label: "Swagger Docs",
    href: "/api/docs",
    description: "Interactive endpoint testing",
  },
  {
    label: "ReDoc",
    href: "/api/redoc",
    description: "Clean API reference view",
  },
];

const modelOptions = [
  { id: "local", label: "Local", description: "Private local Ollama route" },
  { id: "openai", label: "OpenAI", description: "Hosted OpenAI cloud route" },
  { id: "gemini", label: "Gemini", description: "Hosted Gemini cloud route" },
];

const initialMessages = [
  {
    role: "assistant",
    content:
      "Welcome. Ask a direct question, request a summary, compare options, or ask for a draft. Local mode is enabled by default for quick private responses.",
    meta: "ready | local default",
  },
];

export default function App() {
  const [messages, setMessages] = useState(initialMessages);
  const [input, setInput] = useState("");
  const [selectedModel, setSelectedModel] = useState("local");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const useLocal = selectedModel === "local";

  const expectedResponseTime = useLocal
    ? "Expected response time: about 5 to 20 seconds with the current lightweight local model."
    : "Expected response time: usually faster than local, but depends on provider availability and fallback behavior.";

  const handleSend = async (event) => {
    event.preventDefault();

    const message = input.trim();
    if (!message || isLoading) {
      return;
    }

    setMessages((current) => [...current, { role: "user", content: message }]);
    setInput("");
    setError("");
    setIsLoading(true);

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message,
          use_local: useLocal,
          cloud_provider: useLocal ? null : selectedModel,
        }),
      });

      const rawBody = await response.text();
      let data = {};

      try {
        data = rawBody ? JSON.parse(rawBody) : {};
      } catch {
        data = {
          detail: rawBody || "The server returned a non-JSON response.",
        };
      }

      if (!response.ok) {
        throw new Error(data.detail || "Failed to get response from the server.");
      }

      const fallbackLabel = data.fallback_used ? " | fallback" : "";
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: data.reply,
          meta: `${data.provider} | ${data.model_used}${fallbackLabel}`,
        },
      ]);
    } catch (requestError) {
      setError(requestError.message || "Something went wrong.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="app-shell">
      <section className="chat-card">
        <header className="hero">
          <div className="hero-copy">
            <p className="eyebrow">Hybrid AI Workspace</p>
            <h1>Chat with a faster local model or route to cloud reasoning when needed.</h1>
            <p className="hero-text">
              This assistant works best with clear prompts. Ask one focused question,
              add context when needed, and specify the format you want in the answer.
            </p>
          </div>

          <div className="hero-panel">
            <label className="toggle">
              <span>Model Route</span>
            </label>
            <div className="model-switcher" role="tablist" aria-label="Model route">
              {modelOptions.map((option) => (
                <button
                  key={option.id}
                  type="button"
                  className={`model-option ${selectedModel === option.id ? "active" : ""}`}
                  onClick={() => setSelectedModel(option.id)}
                >
                  <span className="model-option-label">{option.label}</span>
                  <span className="model-option-text">{option.description}</span>
                </button>
              ))}
            </div>
            <p className="status-pill">
              {selectedModel === "local"
                ? "Local mode: private and lightweight"
                : selectedModel === "openai"
                  ? "OpenAI mode: cloud-first reasoning"
                  : "Gemini mode: cloud-first fast route"}
            </p>
            <p className="response-time">{expectedResponseTime}</p>
          </div>
        </header>

        <section className="guidance-grid">
          <article className="guidance-card">
            <h2>How to prompt well</h2>
            <ul>
              <li>State the task first: summarize, compare, draft, explain, or rewrite.</li>
              <li>Add constraints like tone, length, audience, or output format.</li>
              <li>For best speed, keep prompts focused and avoid too many asks at once.</li>
            </ul>
          </article>

          <article className="guidance-card">
            <h2>Prompt starters</h2>
            <div className="prompt-list">
              {promptIdeas.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  className="prompt-chip"
                  onClick={() => setInput(prompt)}
                >
                  {prompt}
                </button>
              ))}
            </div>
          </article>
        </section>

        <section className="resource-bar">
          <div className="resource-copy">
            <p className="resource-title">Backend API references</p>
            <p className="resource-text">
              Keep the chatbot open here and open the API references in a separate tab when
              you want to inspect or test backend endpoints.
            </p>
          </div>
          <div className="resource-links">
            {resourceLinks.map((link) => (
              <a
                key={link.label}
                className="resource-link"
                href={link.href}
                target="_blank"
                rel="noreferrer"
              >
                <span className="resource-link-label">{link.label}</span>
                <span className="resource-link-text">{link.description}</span>
              </a>
            ))}
          </div>
        </section>

        <section className="messages">
          {messages.map((message, index) => (
            <article
              key={`${message.role}-${index}`}
              className={`message ${message.role}`}
            >
              <div className="message-role">{message.role}</div>
              <p>{message.content}</p>
              {message.meta ? <span className="message-meta">{message.meta}</span> : null}
            </article>
          ))}

          {isLoading ? (
            <article className="message assistant">
              <div className="message-role">assistant</div>
              <p>
                Thinking...
                {useLocal
                  ? " Local replies usually arrive within a few seconds."
                  : ` ${selectedModel} routing is in progress.`}
              </p>
            </article>
          ) : null}
        </section>

        <form className="composer" onSubmit={handleSend}>
          <input
            type="text"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Try: Summarize this report in three bullets for an executive audience."
            disabled={isLoading}
          />
          <button type="submit" disabled={isLoading || !input.trim()}>
            {isLoading ? "Sending..." : "Send"}
          </button>
        </form>

        {error ? <p className="error-banner">{error}</p> : null}
      </section>
    </main>
  );
}
