import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github-dark.css";
import { Message, Model, MODELS, ConversationOut, DocumentOut } from "../types";
import { MemoryOut } from "../types/memory";
import { streamChat } from "../services/chatService";
import { listConversations, getConversation, deleteConversation, renameConversation } from "../services/conversationService";
import { listDocuments, uploadDocument, deleteDocument } from "../services/documentService";
import { listMemories, deleteMemory, updateMemory } from "../services/memoryService";
import { toReadableError } from "../utils/errorUtils";

let nextId = 0;
function createId(): string {
  return `msg-${Date.now()}-${nextId++}`;
}

const ChatPage: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversations, setConversations] = useState<ConversationOut[]>([]);
  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [memories, setMemories] = useState<MemoryOut[]>([]);
  const [editingMemoryId, setEditingMemoryId] = useState<string | null>(null);
  const [editingMemoryContent, setEditingMemoryContent] = useState("");
  const [memorySearchQuery, setMemorySearchQuery] = useState("");
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [input, setInput] = useState("");
  const [model, setModel] = useState<Model>(MODELS[0]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchConversations = async () => {
    try {
      const data = await listConversations();
      setConversations(data);
    } catch (err) {
      console.error("Failed to fetch conversations:", err);
    }
  };

  const fetchDocs = async () => {
    try {
      const data = await listDocuments();
      setDocuments(data);
    } catch (err) {
      console.error("Failed to fetch documents:", err);
    }
  };

  const fetchMemories = async () => {
    try {
      const data = await listMemories();
      setMemories(data);
    } catch (err) {
      console.error("Failed to fetch memories:", err);
    }
  };

  useEffect(() => {
    fetchConversations();
    fetchDocs();
    fetchMemories();
  }, []);

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setLoading(true);
      await uploadDocument(file);
      await fetchDocs();
    } catch (err) {
      console.error("Failed to upload document:", err);
      setError("Failed to upload document.");
    } finally {
      setLoading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleDeleteDocument = async (id: string) => {
    try {
      setLoading(true);
      await deleteDocument(id);
      await fetchDocs();
    } catch (err) {
      console.error("Failed to delete document:", err);
      setError("Failed to delete document.");
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteMemory = async (id: string) => {
    try {
      setLoading(true);
      await deleteMemory(id);
      await fetchMemories();
    } catch (err) {
      console.error("Failed to delete memory:", err);
      setError("Failed to delete memory.");
    } finally {
      setLoading(false);
    }
  };

  const handleEditMemorySubmit = async (id: string) => {
    if (!editingMemoryContent.trim()) {
      setEditingMemoryId(null);
      return;
    }
    try {
      await updateMemory(id, editingMemoryContent.trim());
      await fetchMemories();
    } catch (err) {
      console.error("Failed to update memory:", err);
      setError("Failed to update memory.");
    } finally {
      setEditingMemoryId(null);
    }
  };

  const loadConversation = async (id: string) => {
    if (loading) return;
    try {
      setLoading(true);
      const data = await getConversation(id);
      setActiveConversationId(data.id);
      setMessages(data.messages);
      setError(null);
    } catch (err) {
      console.error("Failed to load conversation:", err);
      setError("Failed to load conversation.");
    } finally {
      setLoading(false);
    }
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMessage: Message = {
      id: createId(),
      role: "user",
      content: text,
    };

    const assistantId = createId();
    const updatedMessages = [...messages, userMessage];
    setMessages([
      ...updatedMessages,
      { id: assistantId, role: "assistant", content: "" },
    ]);
    setInput("");
    setError(null);
    setLoading(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamChat(
        {
          model,
          messages: updatedMessages.map(({ role, content }) => ({ role, content })),
          conversation_id: activeConversationId ?? undefined,
        },
        (token) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId
                ? { ...msg, content: msg.content + token }
                : msg,
            ),
          );
        },
        (newConversationId) => {
          if (!activeConversationId) {
            setActiveConversationId(newConversationId);
            fetchConversations();
          }
        },
        controller.signal,
      );
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        console.error("Failed to stream message:", err);
        setError(toReadableError(err));
        // Remove the empty assistant message on failure
        setMessages((prev) => prev.filter((msg) => msg.id !== assistantId));
      }
    } finally {
      abortRef.current = null;
      setLoading(false);
    }
  };

  const handleClear = () => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setMessages([]);
    setActiveConversationId(null);
    setInput("");
    setError(null);
    setLoading(false);
  };

  const handleDeleteConversation = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent loading the conversation
    if (loading) return;

    try {
      setLoading(true);
      await deleteConversation(id);
      
      // If we deleted the active conversation, clear the chat view
      if (activeConversationId === id) {
        handleClear();
      }
      
      // Refresh sidebar
      await fetchConversations();
    } catch (err) {
      console.error("Failed to delete conversation:", err);
      setError("Failed to delete conversation.");
    } finally {
      setLoading(false);
    }
  };

  const handleRenameSubmit = async (id: string) => {
    if (!editingTitle.trim()) {
      setEditingId(null);
      return;
    }
    try {
      await renameConversation(id, editingTitle.trim());
      await fetchConversations();
    } catch (err) {
      console.error("Failed to rename conversation:", err);
      setError("Failed to rename conversation.");
    } finally {
      setEditingId(null);
    }
  };

  const renderMemory = (mem: MemoryOut) => (
    <div key={mem.id} style={{ padding: "4px", borderRadius: "4px", marginBottom: "4px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
      {editingMemoryId === mem.id ? (
        <input
          type="text"
          value={editingMemoryContent}
          onChange={(e) => setEditingMemoryContent(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleEditMemorySubmit(mem.id);
            if (e.key === "Escape") setEditingMemoryId(null);
          }}
          onBlur={() => handleEditMemorySubmit(mem.id)}
          autoFocus
          style={{ flex: 1, marginRight: "4px", minWidth: 0, fontSize: "0.8em" }}
        />
      ) : (
        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: "0.8em", flex: 1, marginRight: "4px" }} title={mem.content}>
          {mem.content}
        </span>
      )}
      <div style={{ display: "flex", gap: "2px", flexShrink: 0 }}>
        {editingMemoryId !== mem.id && (
          <button onClick={() => { setEditingMemoryId(mem.id); setEditingMemoryContent(mem.content); }} disabled={loading} style={{ padding: "2px 4px", fontSize: "0.7em", backgroundColor: "#4CAF50", color: "white", border: "none", borderRadius: "3px", cursor: "pointer" }}>Edit</button>
        )}
        <button onClick={() => handleDeleteMemory(mem.id)} disabled={loading} style={{ padding: "2px 4px", fontSize: "0.7em", backgroundColor: "#ff4444", color: "white", border: "none", borderRadius: "3px", cursor: "pointer" }}>Del</button>
      </div>
    </div>
  );

  return (
    <div style={{ display: "flex", height: "100vh" }}>
      {/* Sidebar */}
      <div style={{ width: "250px", borderRight: "1px solid #ccc", padding: "10px", display: "flex", flexDirection: "column" }}>
        <button onClick={handleClear} disabled={loading} style={{ marginBottom: "20px" }}>
          New Chat
        </button>
        <div style={{ overflowY: "auto", flex: 1 }}>
          <h3>Conversations</h3>
          <input
            type="text"
            placeholder="Search chats..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ width: "100%", boxSizing: "border-box", marginBottom: "10px", padding: "4px" }}
          />
          {conversations
            .filter((conv) => conv.title.toLowerCase().includes(searchQuery.toLowerCase()))
            .map((conv) => (
            <div
              key={conv.id}
              onClick={() => loadConversation(conv.id)}
              style={{
                padding: "8px",
                cursor: "pointer",
                backgroundColor: activeConversationId === conv.id ? "#eee" : "transparent",
                color: activeConversationId === conv.id ? "#000" : "inherit",
                borderRadius: "4px",
                marginBottom: "4px",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center"
              }}
            >
              {editingId === conv.id ? (
                <input
                  type="text"
                  value={editingTitle}
                  onChange={(e) => setEditingTitle(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleRenameSubmit(conv.id);
                    if (e.key === "Escape") setEditingId(null);
                  }}
                  onBlur={() => handleRenameSubmit(conv.id)}
                  autoFocus
                  onClick={(e) => e.stopPropagation()}
                  style={{ flex: 1, marginRight: "8px", minWidth: 0 }}
                />
              ) : (
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1, marginRight: "8px" }}>
                  {conv.title}
                </span>
              )}
              
              <div style={{ display: "flex", gap: "4px", flexShrink: 0 }}>
                {editingId !== conv.id && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setEditingId(conv.id);
                      setEditingTitle(conv.title);
                    }}
                    disabled={loading}
                    style={{
                      padding: "2px 6px",
                      fontSize: "0.8em",
                      backgroundColor: "#4CAF50",
                      color: "white",
                      border: "none",
                      borderRadius: "3px",
                      cursor: "pointer"
                    }}
                  >
                    Edit
                  </button>
                )}
                <button 
                  onClick={(e) => handleDeleteConversation(conv.id, e)}
                  disabled={loading}
                  style={{ 
                    padding: "2px 6px",
                    fontSize: "0.8em",
                    backgroundColor: "#ff4444",
                    color: "white",
                    border: "none",
                    borderRadius: "3px",
                    cursor: "pointer"
                  }}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>

        <hr style={{ margin: "20px 0" }} />
        
        <div style={{ flex: 1, overflowY: "auto" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
            <h3 style={{ margin: 0 }}>Documents</h3>
            <button onClick={handleUploadClick} disabled={loading} style={{ padding: "2px 6px", fontSize: "0.8em", cursor: "pointer" }}>
              Upload
            </button>
            <input 
              type="file" 
              ref={fileInputRef} 
              style={{ display: "none" }} 
              accept=".pdf,.txt,.md"
              onChange={handleFileChange}
            />
          </div>
          
          {documents.map((doc) => (
            <div key={doc.id} style={{
              padding: "8px",
              backgroundColor: "transparent",
              borderRadius: "4px",
              marginBottom: "4px",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center"
            }}>
              <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: "0.9em" }} title={doc.filename}>
                {doc.filename}
              </span>
              <button 
                onClick={() => handleDeleteDocument(doc.id)}
                disabled={loading}
                style={{ 
                  marginLeft: "8px",
                  padding: "2px 6px",
                  fontSize: "0.8em",
                  backgroundColor: "#ff4444",
                  color: "white",
                  border: "none",
                  borderRadius: "3px",
                  cursor: "pointer",
                  flexShrink: 0
                }}
              >
                Delete
              </button>
            </div>
          ))}
        </div>

        <hr style={{ margin: "20px 0" }} />
        
        <div style={{ flex: 1, overflowY: "auto" }}>
          <h3 style={{ margin: 0, marginBottom: "10px" }}>Memories</h3>
          
          <input
            type="text"
            placeholder="Search memories..."
            value={memorySearchQuery}
            onChange={(e) => setMemorySearchQuery(e.target.value)}
            style={{ width: "100%", boxSizing: "border-box", marginBottom: "10px", padding: "4px" }}
          />
          
          <h4 style={{ margin: "5px 0", fontSize: "0.9em", color: "#666" }}>Episodic</h4>
          {memories
            .filter(m => m.memory_type === "episodic" && m.content.toLowerCase().includes(memorySearchQuery.toLowerCase()))
            .map(renderMemory)}

          <h4 style={{ margin: "10px 0 5px 0", fontSize: "0.9em", color: "#666" }}>Conversational</h4>
          {memories
            .filter(m => m.memory_type === "conversational" && m.content.toLowerCase().includes(memorySearchQuery.toLowerCase()))
            .map(renderMemory)}
        </div>
      </div>

      {/* Main Chat Area */}
      <div style={{ flex: 1, padding: "20px", display: "flex", flexDirection: "column" }}>
        <div>
          <h1>Chat</h1>
          <select
            value={model}
            onChange={(e) => setModel(e.target.value as Model)}
            disabled={loading}
          >
            {MODELS.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>

        <div style={{ flex: 1, overflowY: "auto", margin: "20px 0" }}>
          {messages.length === 0 && <p>No messages yet.</p>}
          {messages.map((msg) => (
            <div key={msg.id}>
              <strong>{msg.role}:</strong>
              {msg.role === "assistant" ? (
                <ReactMarkdown rehypePlugins={[rehypeHighlight]}>
                  {msg.content}
                </ReactMarkdown>
              ) : (
                <span> {msg.content}</span>
              )}
            </div>
          ))}
          {loading && <p>Generating…</p>}
        </div>

        {error && (
          <div role="alert">
            <p><strong>Error:</strong> {error}</p>
            <button onClick={() => setError(null)}>Dismiss</button>
          </div>
        )}

        <div>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSend();
            }}
            placeholder="Type a message…"
            disabled={loading}
            style={{ width: "80%" }}
          />
          <button onClick={handleSend} disabled={loading}>
            Send
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatPage;
