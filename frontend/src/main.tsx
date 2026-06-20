import { StrictMode } from "react";
import ReactDOM from "react-dom/client";
import ChatPage from "./pages/ChatPage";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ChatPage />
  </StrictMode>
);
