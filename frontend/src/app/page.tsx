'use client';

import { AuthProvider, useAuth } from '@/contexts/AuthContext';
import { ConversationProvider } from '@/contexts/ConversationContext';
import { ChatInterface } from '@/components/ChatInterface';
import { AuthPage } from '@/components/AuthPage';

function AppContent() {
  const { user, token, mounted } = useAuth();

  if (!mounted) return null;
  if (!user || !token) return <AuthPage />;

  return (
    <ConversationProvider userId={user.id} token={token}>
      <ChatInterface />
    </ConversationProvider>
  );
}

export default function Home() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
