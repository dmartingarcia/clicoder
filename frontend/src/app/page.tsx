'use client';

import { ConversationProvider } from '@/contexts/ConversationContext';
import { ChatInterface } from '@/components/ChatInterface';

export default function Home() {
  const userId = `doctor_${Math.random().toString(36).substr(2, 9)}`;

  return (
    <ConversationProvider userId={userId}>
      <ChatInterface />
    </ConversationProvider>
  );
}
