import { NavLink, useNavigate } from 'react-router-dom';
import { createConversation } from '../api';

export default function Sidebar({ conversations, activeId, onDelete }) {
  const navigate = useNavigate();

  const handleNewChat = async () => {
    const { data } = await createConversation('New conversation');
    navigate(`/chat/${data.id}`);
  };

  return (
    <div className="w-64 bg-white border-r border-slate-200 flex flex-col h-full">
      <div className="p-4 border-b border-slate-200">
        <button
          onClick={handleNewChat}
          className="w-full px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition"
        >
          New Chat
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {conversations.map((conv) => (
          <div
            key={conv.id}
            className={`group flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer ${
              conv.id === activeId ? 'bg-indigo-50' : 'hover:bg-slate-100'
            }`}
          >
            <NavLink
              to={`/chat/${conv.id}`}
              className="flex-1 truncate text-sm text-slate-700 font-medium"
            >
              {conv.title || 'New conversation'}
            </NavLink>
            <button
              onClick={() => onDelete(conv.id)}
              className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-red-600 text-xs px-2"
              title="Delete conversation"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
