import { useOutletContext, useParams } from 'react-router-dom';
import Chat from '../components/Chat';

export default function ChatPage() {
  const { conversation_id } = useParams();
  const { onConversationsChange } = useOutletContext();

  return (
    <Chat
      key={conversation_id || 'new'}
      conversationId={conversation_id || null}
      onConversationsChange={onConversationsChange}
    />
  );
}
