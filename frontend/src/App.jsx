import { Routes, Route, Outlet, useNavigate, useParams } from 'react-router-dom';
import { useEffect, useState } from 'react';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import UploadPage from './pages/UploadPage';
import DocumentsPage from './pages/DocumentsPage';
import ChatPage from './pages/ChatPage';
import { listConversations, deleteConversation } from './api';

function ChatLayout() {
  const navigate = useNavigate();
  const [conversations, setConversations] = useState([]);
  const { conversation_id } = useParams();

  const loadConversations = async () => {
    const { data } = await listConversations();
    setConversations(data.conversations);
  };

  useEffect(() => {
    loadConversations();
  }, []);

  const handleDeleteConversation = async (id) => {
    if (!confirm('Delete this conversation?')) return;
    await deleteConversation(id);
    await loadConversations();
    navigate('/chat');
  };

  return (
    <div className="flex h-[calc(100vh-4rem)]">
      <Sidebar
        conversations={conversations}
        activeId={conversation_id}
        onDelete={handleDeleteConversation}
      />
      <div className="flex-1 overflow-hidden">
        <Outlet context={{ onConversationsChange: loadConversations }} />
      </div>
    </div>
  );
}

export default function App() {
  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<UploadPage />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/chat" element={<ChatLayout />}>
            <Route index element={<ChatPage />} />
            <Route path=":conversation_id" element={<ChatPage />} />
          </Route>
        </Routes>
      </main>
    </div>
  );
}
