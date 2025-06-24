import React, { useState } from "react";
import ReactMarkdown from "react-markdown";

function App() {
  const [question, setQuestion] = useState("");
  const [conversation, setConversation] = useState([]); // Store chat history

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!question.trim()) return;

    // Add user's message to conversation
    const newConversation = [...conversation, { role: "user", content: question }];
    setConversation(newConversation);
    setQuestion(""); // Clear input

    try {
      // Send POST request with message and history
      const res = await fetch("http://localhost:8000/ask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: question,
          history: newConversation,
        }),
      });

      if (!res.ok) {
        throw new Error(`HTTP error! Status: ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let accumulatedText = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        accumulatedText += chunk;

        // Update conversation with bot's response
        setConversation([...newConversation, { role: "assistant", content: accumulatedText }]);
      }
    } catch (error) {
      console.error("Error fetching response:", error);
      setConversation([...newConversation, { role: "assistant", content: `Error: ${error.message}` }]);
    }
  };

  return (
    <div style={{ padding: "20px", maxWidth: "600px", margin: "0 auto" }}>
      <h1>Quiz Tutor Chatbot</h1>

      {/* Chat History */}
      <div
        style={{
          border: "1px solid #ccc",
          padding: "10px",
          minHeight: "300px",
          overflowY: "auto",
          marginBottom: "20px",
        }}
      >
        {conversation.length > 0 ? (
          conversation.map((msg, index) => (
            <div
              key={index}
              style={{
                textAlign: msg.role === "user" ? "right" : "left",
                margin: "10px 0",
              }}
            >
              <span
                style={{
                  display: "inline-block",
                  padding: "8px 12px",
                  borderRadius: "10px",
                  backgroundColor: msg.role === "user" ? "#007bff" : "#f1f1f1",
                  color: msg.role === "user" ? "white" : "black",
                  maxWidth: "70%",
                }}
              >
                {msg.role === "assistant" ? (
                  <ReactMarkdown>{msg.content}</ReactMarkdown>
                ) : (
                  msg.content
                )}
              </span>
            </div>
          ))
        ) : (
          <p>Start the conversation...</p>
        )}
      </div>

      {/* Input Form */}
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Type your message here"
          style={{ width: "80%", padding: "8px" }}
        />
        <button
          type="submit"
          style={{ padding: "8px 16px", marginLeft: "10px" }}
        >
          Send
        </button>
      </form>
    </div>
  );
}

export default App;