import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '../helpers';

// ── ConversationContext mock ──────────────────────────────────────────────────
const mockCreateConversation = vi.fn();
const mockSwitchConversation = vi.fn();
const mockDeleteConversation = vi.fn();
const mockRestoreConversation = vi.fn();

let mockConversations: Array<{
  conversation_id: string;
  started_at: string;
  status: string;
  deleted_at: null | string;
  message_count: number;
  last_message: { content: string; timestamp: string } | null;
}> = [];

let mockTrashedConversations: typeof mockConversations = [];
let mockActiveConversationId: string | null = null;

vi.mock('@/contexts/ConversationContext', () => ({
  useConversation: () => ({
    conversations: mockConversations,
    trashedConversations: mockTrashedConversations,
    activeConversationId: mockActiveConversationId,
    createConversation: mockCreateConversation,
    switchConversation: mockSwitchConversation,
    deleteConversation: mockDeleteConversation,
    restoreConversation: mockRestoreConversation,
  }),
}));

// ── AuthContext mock ──────────────────────────────────────────────────────────
const mockLogout = vi.fn();

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 'u1', first_name: 'María', last_name: 'García', username: 'dra_garcia', email: 'maria@hosp.com' },
    token: 'tok-123',
    logout: mockLogout,
  }),
}));

import { ConversationSidebar } from '@/components/ConversationSidebar';

const now = new Date().toISOString();

describe('ConversationSidebar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockConversations = [];
    mockTrashedConversations = [];
    mockActiveConversationId = null;
  });

  describe('user info section', () => {
    it('shows the doctor name', () => {
      render(<ConversationSidebar />);
      expect(screen.getByText(/María García/)).toBeInTheDocument();
    });

    it('shows the username with @ prefix', () => {
      render(<ConversationSidebar />);
      expect(screen.getByText('@dra_garcia')).toBeInTheDocument();
    });

    it('calls logout when logout button is clicked', async () => {
      const user = userEvent.setup();
      render(<ConversationSidebar />);
      await user.click(screen.getByTitle('auth.logout'));
      expect(mockLogout).toHaveBeenCalledOnce();
    });
  });

  describe('new analysis button', () => {
    it('renders the new analysis button', () => {
      render(<ConversationSidebar />);
      expect(screen.getByText('sidebar.new_analysis')).toBeInTheDocument();
    });

    it('calls createConversation when clicked', async () => {
      const user = userEvent.setup();
      render(<ConversationSidebar />);
      await user.click(screen.getByText('sidebar.new_analysis'));
      expect(mockCreateConversation).toHaveBeenCalledOnce();
    });
  });

  describe('empty state', () => {
    it('shows no_previous message when there are no conversations', () => {
      render(<ConversationSidebar />);
      expect(screen.getByText('sidebar.no_previous')).toBeInTheDocument();
    });
  });

  describe('conversation list', () => {
    beforeEach(() => {
      mockConversations = [
        { conversation_id: 'c1', started_at: now, status: 'active', deleted_at: null, message_count: 3, last_message: { content: 'Patient report', timestamp: now } },
        { conversation_id: 'c2', started_at: now, status: 'active', deleted_at: null, message_count: 1, last_message: { content: 'Another note', timestamp: now } },
      ];
    });

    it('renders all conversations', () => {
      render(<ConversationSidebar />);
      expect(screen.getByText('Patient report')).toBeInTheDocument();
      expect(screen.getByText('Another note')).toBeInTheDocument();
    });

    it('does NOT show empty state when conversations exist', () => {
      render(<ConversationSidebar />);
      expect(screen.queryByText('sidebar.no_previous')).not.toBeInTheDocument();
    });

    it('calls switchConversation when a conversation is clicked', async () => {
      const user = userEvent.setup();
      render(<ConversationSidebar />);
      await user.click(screen.getByText('Patient report'));
      expect(mockSwitchConversation).toHaveBeenCalledWith('c1');
    });

    it('shows message count using messages_one for 1 message', () => {
      mockConversations = [
        { conversation_id: 'c1', started_at: now, status: 'active', deleted_at: null, message_count: 1, last_message: null },
      ];
      render(<ConversationSidebar />);
      expect(screen.getByText(/1.*sidebar\.messages_one/)).toBeInTheDocument();
    });

    it('shows message count using messages_other for multiple messages', () => {
      render(<ConversationSidebar />);
      expect(screen.getByText(/3.*sidebar\.messages_other/)).toBeInTheDocument();
    });
  });

  describe('trash section', () => {
    beforeEach(() => {
      mockTrashedConversations = [
        { conversation_id: 't1', started_at: now, status: 'active', deleted_at: now, message_count: 0, last_message: { content: 'Old report', timestamp: now } },
      ];
    });

    it('shows trash section when there are trashed conversations', () => {
      render(<ConversationSidebar />);
      expect(screen.getByText(/sidebar\.trash/)).toBeInTheDocument();
    });

    it('does NOT show trash section when trash is empty', () => {
      mockTrashedConversations = [];
      render(<ConversationSidebar />);
      expect(screen.queryByText(/sidebar\.trash/)).not.toBeInTheDocument();
    });

    it('shows trashed conversations after clicking the trash toggle', async () => {
      const user = userEvent.setup();
      render(<ConversationSidebar />);
      await user.click(screen.getByText(/sidebar\.trash/));
      expect(screen.getByText(/Old report/)).toBeInTheDocument();
    });

    it('calls restoreConversation when restore button is clicked', async () => {
      const user = userEvent.setup();
      render(<ConversationSidebar />);
      await user.click(screen.getByText(/sidebar\.trash/));
      await user.click(screen.getByTitle('sidebar.restore'));
      expect(mockRestoreConversation).toHaveBeenCalledWith('t1');
    });
  });
});
