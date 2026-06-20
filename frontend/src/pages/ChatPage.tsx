import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github-dark.css";
import { Message, Model, MODELS, ConversationOut, DocumentOut } from "../types";
import { MemoryOut } from "../types/memory";
import { UserProfile } from "../types/profile";
import { streamChat } from "../services/chatService";
import { listConversations, getConversation, deleteConversation, renameConversation } from "../services/conversationService";
import { listDocuments, uploadDocument, deleteDocument } from "../services/documentService";
import { listMemories, deleteMemory, updateMemory } from "../services/memoryService";
import { toReadableError } from "../utils/errorUtils";
import { 
  Menu, X, MessageSquare, FileText, Trash2, Edit2, 
  Send, Brain, Plus, Upload, Check, Folder, User
} from "lucide-react";

let nextId = 0;
function createId(): string {
  return `msg-${Date.now()}-${nextId++}`;
}

const ChatPage: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversations, setConversations] = useState<ConversationOut[]>([]);
  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [memories, setMemories] = useState<MemoryOut[]>([]);
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  
  const [sidebarOpen, setSidebarOpen] = useState(true);
  
  const [editingMemoryId, setEditingMemoryId] = useState<string | null>(null);
  const [editingMemoryContent, setEditingMemoryContent] = useState<string>("");
  const [selectedMemory, setSelectedMemory] = useState<MemoryOut | null>(null);
  const [memorySearchQuery, setMemorySearchQuery] = useState("");
  const [memoryCategoryFilter, setMemoryCategoryFilter] = useState<string>("all");
  
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
      // Also fetch profile to keep sidebar updated as memories might have changed it
      fetchProfile();
    } catch (err) {
      console.error("Failed to fetch memories:", err);
    }
  };

  const fetchProfile = async () => {
    try {
      const res = await fetch("/profile");
      if (res.ok) {
        setUserProfile(await res.json());
      } else {
        console.error(`Failed to fetch profile: ${res.statusText}`);
      }
    } catch (err) {
      console.error("Failed to fetch profile", err);
    }
  };

  useEffect(() => {
    fetchConversations();
    fetchDocs();
    fetchMemories();
    fetchProfile();
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
    e.stopPropagation();
    if (loading) return;

    try {
      setLoading(true);
      await deleteConversation(id);
      if (activeConversationId === id) {
        handleClear();
      }
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
    <div 
      key={mem.id} 
      className="card interactive" 
      style={{ display: "flex", flexDirection: "column", gap: "8px", padding: "10px", cursor: "pointer" }}
      onClick={() => setSelectedMemory(mem)}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
          <span className={`badge ${mem.memory_type}`}>{mem.memory_type}</span>
          <span className={`badge cat-${mem.category || "other"}`}>{mem.category || "other"}</span>
          {!mem.is_active && <span className="badge" style={{ backgroundColor: "var(--border-color)", color: "var(--text-secondary)" }}>Inactive</span>}
        </div>
        <div style={{ display: "flex", gap: "2px" }}>
          {editingMemoryId !== mem.id && (
            <button className="icon-only" onClick={(e) => { e.stopPropagation(); setEditingMemoryId(mem.id); setEditingMemoryContent(mem.content); }} disabled={loading}>
              <Edit2 size={14} />
            </button>
          )}
          <button className="icon-only danger" onClick={(e) => { e.stopPropagation(); handleDeleteMemory(mem.id); }} disabled={loading}>
            <Trash2 size={14} />
          </button>
        </div>
      </div>
      
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
          style={{ width: "100%" }}
        />
      ) : (
        <span style={{ fontSize: "0.85rem", lineHeight: "1.4" }} title={mem.content}>
          {mem.content}
        </span>
      )}
    </div>
  );

  return (
    <div style={{ display: "flex", height: "100vh", width: "100vw", backgroundColor: "var(--bg-main)" }}>
      {/* Sidebar */}
      <div style={{
        width: sidebarOpen ? "320px" : "0",
        backgroundColor: "var(--bg-sidebar)",
        borderRight: sidebarOpen ? "1px solid var(--border-color)" : "none",
        transition: "width 0.3s ease",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden"
      }}>
        <div style={{ padding: "16px", flex: 1, display: "flex", flexDirection: "column", overflowY: "auto", minWidth: "320px", gap: "24px" }}>
          
          <button className="primary" onClick={handleClear} disabled={loading} style={{ width: "100%", justifyContent: "center", padding: "10px" }}>
            <Plus size={16} /> New Chat
          </button>

          {/* Conversations Section */}
          <section style={{ display: "flex", flexDirection: "column", flex: 1, minHeight: "200px" }}>
            <div style={{ display: "flex", alignItems: "center", marginBottom: "8px", gap: "8px", color: "var(--text-secondary)" }}>
              <MessageSquare size={14} />
              <h3 style={{ margin: 0, fontSize: "0.8rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>Conversations</h3>
            </div>
            <input
              type="text"
              placeholder="Search chats..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ width: "100%", marginBottom: "12px", backgroundColor: "var(--bg-main)" }}
            />
            <div style={{ flex: 1, overflowY: "auto" }}>
              {conversations
                .filter((conv) => conv.title.toLowerCase().includes(searchQuery.toLowerCase()))
                .map((conv) => (
                <div
                  key={conv.id}
                  className={`card interactive ${activeConversationId === conv.id ? "active" : ""}`}
                  onClick={() => loadConversation(conv.id)}
                  style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "8px" }}
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
                      style={{ flex: 1, minWidth: 0 }}
                    />
                  ) : (
                    <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1, fontSize: "0.9rem" }}>
                      {conv.title}
                    </span>
                  )}
                  
                  <div style={{ display: "flex", gap: "2px", flexShrink: 0 }}>
                    {editingId !== conv.id && (
                      <button className="icon-only" onClick={(e) => { e.stopPropagation(); setEditingId(conv.id); setEditingTitle(conv.title); }} disabled={loading}>
                        <Edit2 size={14} />
                      </button>
                    )}
                    <button className="icon-only danger" onClick={(e) => handleDeleteConversation(conv.id, e)} disabled={loading}>
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Documents Section */}
          <section style={{ display: "flex", flexDirection: "column", flex: 1, minHeight: "150px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px", color: "var(--text-secondary)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <Folder size={14} />
                <h3 style={{ margin: 0, fontSize: "0.8rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>Documents</h3>
              </div>
              <button className="icon-only" onClick={handleUploadClick} disabled={loading} title="Upload Document">
                <Upload size={16} />
              </button>
              <input type="file" ref={fileInputRef} style={{ display: "none" }} accept=".pdf,.txt,.md" onChange={handleFileChange} />
            </div>
            <div style={{ flex: 1, overflowY: "auto" }}>
              {documents.map((doc) => (
                <div key={doc.id} className="card" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", overflow: "hidden" }}>
                    <FileText size={16} color="var(--accent-color)" style={{ flexShrink: 0 }} />
                    <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: "0.85rem" }} title={doc.filename}>
                      {doc.filename}
                    </span>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px", flexShrink: 0 }}>
                    <span className="badge" style={{ backgroundColor: "var(--bg-main)", color: "var(--text-secondary)" }}>{doc.chunk_count} ch</span>
                    <button className="icon-only danger" onClick={() => handleDeleteDocument(doc.id)} disabled={loading}>
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Profile Section */}
          <section style={{ display: "flex", flexDirection: "column", marginBottom: "20px" }}>
             <div style={{ display: "flex", alignItems: "center", marginBottom: "8px", gap: "8px", color: "var(--text-secondary)" }}>
              <User size={14} />
              <h3 style={{ margin: 0, fontSize: "0.8rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>Profile</h3>
            </div>
            {userProfile ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "6px", fontSize: "0.85rem" }}>
                {userProfile.college && <div><strong>College:</strong> {userProfile.college}</div>}
                {userProfile.branch && <div><strong>Branch:</strong> {userProfile.branch}</div>}
                {userProfile.preferred_language && <div><strong>Language:</strong> {userProfile.preferred_language}</div>}
                {userProfile.current_project && <div><strong>Project:</strong> {userProfile.current_project}</div>}
                {!userProfile.college && !userProfile.branch && !userProfile.preferred_language && !userProfile.current_project && (
                  <span style={{ color: "var(--text-secondary)", fontStyle: "italic" }}>No profile info yet.</span>
                )}
              </div>
            ) : (
               <span style={{ color: "var(--text-secondary)", fontStyle: "italic", fontSize: "0.85rem" }}>Loading...</span>
            )}
          </section>

          {/* Memories Section */}
          <section style={{ display: "flex", flexDirection: "column", flex: 1, minHeight: "250px" }}>
             <div style={{ display: "flex", alignItems: "center", marginBottom: "8px", gap: "8px", color: "var(--text-secondary)" }}>
              <Brain size={14} />
              <h3 style={{ margin: 0, fontSize: "0.8rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>Memories</h3>
            </div>
            <input
              type="text"
              placeholder="Search memories..."
              value={memorySearchQuery}
              onChange={(e) => setMemorySearchQuery(e.target.value)}
              style={{ width: "100%", marginBottom: "8px", backgroundColor: "var(--bg-main)" }}
            />
            <div style={{ display: "flex", flexWrap: "wrap", gap: "4px", marginBottom: "10px" }}>
              {["all", "personal", "education", "project", "preference", "goal"].map((cat) => (
                <button
                  key={cat}
                  onClick={() => setMemoryCategoryFilter(cat)}
                  style={{
                    padding: "3px 8px",
                    fontSize: "0.7rem",
                    borderRadius: "12px",
                    border: memoryCategoryFilter === cat ? "1px solid var(--accent-color)" : "1px solid var(--border-color)",
                    backgroundColor: memoryCategoryFilter === cat ? "var(--accent-color)" : "transparent",
                    color: memoryCategoryFilter === cat ? "#fff" : "var(--text-secondary)",
                    cursor: "pointer",
                    textTransform: "capitalize",
                  }}
                >
                  {cat === "all" ? "All" : cat}
                </button>
              ))}
            </div>
            <div style={{ flex: 1, overflowY: "auto" }}>
              {memories
                .filter(m => m.content.toLowerCase().includes(memorySearchQuery.toLowerCase()))
                .filter(m => memoryCategoryFilter === "all" || m.category === memoryCategoryFilter)
                .map(renderMemory)}
            </div>
          </section>

        </div>
      </div>

      {/* Main Chat Area */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", position: "relative" }}>
        
        {/* Top Header */}
        <div style={{ display: "flex", alignItems: "center", padding: "16px", borderBottom: "1px solid var(--border-color)", backgroundColor: "var(--bg-sidebar)" }}>
          <button className="icon-only" onClick={() => setSidebarOpen(!sidebarOpen)} style={{ marginRight: "16px" }}>
            {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
          <div style={{ display: "flex", alignItems: "center", gap: "12px", flex: 1 }}>
            <h2 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 600 }}>Phus AI</h2>
            <select value={model} onChange={(e) => setModel(e.target.value as Model)} disabled={loading} style={{ backgroundColor: "var(--bg-main)", marginLeft: "auto" }}>
              {MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
        </div>

        {/* Messages */}
        <div style={{ flex: 1, overflowY: "auto", padding: "40px 10%", display: "flex", flexDirection: "column", gap: "24px" }}>
          {messages.length === 0 && (
            <div style={{ margin: "auto", textAlign: "center", color: "var(--text-secondary)" }}>
              <Brain size={48} style={{ opacity: 0.5, marginBottom: "16px" }} />
              <h2>How can I help you today?</h2>
            </div>
          )}
          
          {messages.map((msg, idx) => {
            const isUser = msg.role === "user";
            return (
              <div key={msg.id} style={{
                display: "flex",
                flexDirection: "column",
                alignItems: isUser ? "flex-end" : "flex-start",
                width: "100%"
              }}>
                <div style={{
                  maxWidth: "80%",
                  padding: "12px 16px",
                  borderRadius: "12px",
                  backgroundColor: isUser ? "var(--user-bubble)" : "transparent",
                  color: isUser ? "var(--user-bubble-text)" : "var(--assistant-bubble-text)",
                  border: isUser ? "none" : "1px solid var(--border-color)",
                }}>
                  {isUser ? (
                    <span style={{ fontSize: "0.95rem", lineHeight: "1.5", whiteSpace: "pre-wrap" }}>{msg.content}</span>
                  ) : (
                    <div className="markdown-body" style={{ color: "var(--assistant-bubble-text)" }}>
                      <ReactMarkdown rehypePlugins={[rehypeHighlight]}>
                        {msg.content}
                      </ReactMarkdown>
                    </div>
                  )}
                  {/* Streaming Cursor Logic */}
                  {!isUser && loading && idx === messages.length - 1 && (
                    <span className="streaming-cursor"></span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {error && (
          <div style={{ margin: "0 10%", padding: "12px", backgroundColor: "rgba(248, 81, 73, 0.1)", border: "1px solid var(--danger-color)", borderRadius: "8px", color: "var(--danger-color)", display: "flex", justifyContent: "space-between" }}>
            <span style={{ fontSize: "0.9rem" }}><strong>Error:</strong> {error}</span>
            <button className="icon-only danger" onClick={() => setError(null)}><X size={16} /></button>
          </div>
        )}

        {/* Input Bar */}
        <div style={{ padding: "20px 10%", paddingBottom: "40px" }}>
          <div style={{ 
            display: "flex", 
            alignItems: "center", 
            backgroundColor: "var(--bg-card)", 
            border: "1px solid var(--border-color)", 
            borderRadius: "12px",
            padding: "8px",
            boxShadow: "0 8px 24px rgba(0,0,0,0.2)"
          }}>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleSend();
              }}
              placeholder="Message Phus AI..."
              disabled={loading}
              style={{ flex: 1, backgroundColor: "transparent", border: "none", outline: "none", fontSize: "1rem", padding: "8px 12px" }}
            />
            <button 
              className="primary"
              onClick={handleSend} 
              disabled={loading || !input.trim()}
              style={{ borderRadius: "8px", padding: "8px 16px" }}
            >
              <Send size={16} />
            </button>
          </div>
          <div style={{ textAlign: "center", marginTop: "12px", fontSize: "0.75rem", color: "var(--text-secondary)" }}>
            AI can make mistakes. Consider verifying important information.
          </div>
        </div>
        
      </div>
      {/* Memory Inspector Modal */}
      {selectedMemory && (
        <div style={{
          position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: "rgba(0,0,0,0.5)", zIndex: 1000,
          display: "flex", alignItems: "center", justifyContent: "center"
        }} onClick={() => setSelectedMemory(null)}>
          <div style={{
            backgroundColor: "var(--bg-sidebar)",
            padding: "24px", borderRadius: "12px", width: "400px", maxWidth: "90%",
            boxShadow: "0 10px 30px rgba(0,0,0,0.3)",
            display: "flex", flexDirection: "column", gap: "16px"
          }} onClick={e => e.stopPropagation()}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--border-color)", paddingBottom: "12px" }}>
              <h3 style={{ margin: 0, display: "flex", alignItems: "center", gap: "8px" }}>
                <Brain size={18} /> Memory Inspector
              </h3>
              <button className="icon-only" onClick={() => setSelectedMemory(null)}>
                <X size={18} />
              </button>
            </div>
            
            <div style={{ display: "flex", flexDirection: "column", gap: "12px", fontSize: "0.9rem" }}>
              <div>
                <strong style={{ color: "var(--text-secondary)", fontSize: "0.8rem", display: "block", marginBottom: "4px" }}>Content</strong>
                <div style={{ backgroundColor: "var(--bg-main)", padding: "10px", borderRadius: "8px", border: "1px solid var(--border-color)" }}>
                  {selectedMemory.content}
                </div>
              </div>
              
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                <div>
                  <strong style={{ color: "var(--text-secondary)", fontSize: "0.8rem", display: "block", marginBottom: "4px" }}>Type</strong>
                  <span className={`badge ${selectedMemory.memory_type}`}>{selectedMemory.memory_type}</span>
                </div>
                <div>
                  <strong style={{ color: "var(--text-secondary)", fontSize: "0.8rem", display: "block", marginBottom: "4px" }}>Category</strong>
                  <span className={`badge cat-${selectedMemory.category || "other"}`}>{selectedMemory.category || "other"}</span>
                </div>
                <div>
                  <strong style={{ color: "var(--text-secondary)", fontSize: "0.8rem", display: "block", marginBottom: "4px" }}>Importance</strong>
                  <span>{selectedMemory.importance} / 10</span>
                </div>
                <div>
                  <strong style={{ color: "var(--text-secondary)", fontSize: "0.8rem", display: "block", marginBottom: "4px" }}>Status</strong>
                  <span>{selectedMemory.is_active ? "Active" : "Inactive"}</span>
                </div>
              </div>

              <div>
                <strong style={{ color: "var(--text-secondary)", fontSize: "0.8rem", display: "block", marginBottom: "4px" }}>Dates</strong>
                <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                  <div>Created: {new Date(selectedMemory.created_at).toLocaleString()}</div>
                  {selectedMemory.last_accessed && <div>Last Accessed: {new Date(selectedMemory.last_accessed).toLocaleString()}</div>}
                  {selectedMemory.expires_at && <div>Expires: {new Date(selectedMemory.expires_at).toLocaleString()}</div>}
                </div>
              </div>

              <div>
                <strong style={{ color: "var(--text-secondary)", fontSize: "0.8rem", display: "block", marginBottom: "4px" }}>Memory ID</strong>
                <code style={{ fontSize: "0.75rem", padding: "4px 8px", backgroundColor: "var(--bg-main)", borderRadius: "4px", border: "1px solid var(--border-color)" }}>
                  {selectedMemory.id}
                </code>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ChatPage;
