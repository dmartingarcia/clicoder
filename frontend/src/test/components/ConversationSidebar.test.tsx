import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '../helpers';

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
      await user.click(screen.getByText('auth.logout'));
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
  describe('acciones de protección de datos', () => {
    it('abre el panel de derechos al pulsar privacidad', async () => {
      const user = userEvent.setup();
      render(<ConversationSidebar />);

      await user.click(screen.getByText('privacy.title'));

      expect(screen.getAllByText('privacy.title').length).toBeGreaterThan(1);
    });

    it('descarga los datos del usuario al exportar', async () => {
      const blob = new Blob(['{}'], { type: 'application/json' });
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        blob: () => Promise.resolve(blob),
      }) as unknown as typeof fetch;

      const clickSpy = vi.fn();
      const originalCreate = document.createElement.bind(document);
      vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
        const el = originalCreate(tag);
        if (tag === 'a') el.click = clickSpy;
        return el;
      });

      const user = userEvent.setup();
      render(<ConversationSidebar />);
      await user.click(screen.getByText('sidebar.export_data'));

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/users/export'),
        expect.objectContaining({ headers: { Authorization: 'Bearer tok-123' } })
      );
      expect(clickSpy).toHaveBeenCalled();
      vi.restoreAllMocks();
    });

    it('cierra la sesión si el token ha caducado al exportar', async () => {
      global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 401 }) as unknown as typeof fetch;

      const user = userEvent.setup();
      render(<ConversationSidebar />);
      await user.click(screen.getByText('sidebar.export_data'));

      expect(mockLogout).toHaveBeenCalled();
    });

    it('no descarga nada si la exportación falla', async () => {
      global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 }) as unknown as typeof fetch;
      const clickSpy = vi.fn();
      const originalCreate = document.createElement.bind(document);
      vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
        const el = originalCreate(tag);
        if (tag === 'a') el.click = clickSpy;
        return el;
      });

      const user = userEvent.setup();
      render(<ConversationSidebar />);
      await user.click(screen.getByText('sidebar.export_data'));

      expect(clickSpy).not.toHaveBeenCalled();
      vi.restoreAllMocks();
    });

    it('pide confirmación antes de borrar la cuenta', async () => {
      const user = userEvent.setup();
      render(<ConversationSidebar />);

      await user.click(screen.getByText('sidebar.delete_account'));

      // Borrar la cuenta no puede ocurrir con un solo clic
      expect(screen.getAllByText(/delete_account|confirm/i).length).toBeGreaterThan(1);
    });

    it('cancela el borrado de cuenta sin llamar a la API', async () => {
      global.fetch = vi.fn();
      const user = userEvent.setup();
      render(<ConversationSidebar />);

      await user.click(screen.getByText('sidebar.delete_account'));
      await user.click(screen.getByText('sidebar.cancel'));

      expect(screen.queryByText('sidebar.delete_account_confirm')).not.toBeInTheDocument();
      expect(global.fetch).not.toHaveBeenCalled();
    });

    it('borra la cuenta y cierra la sesión tras confirmar', async () => {
      global.fetch = vi.fn().mockResolvedValue({ ok: true, status: 200 }) as unknown as typeof fetch;
      const user = userEvent.setup();
      render(<ConversationSidebar />);

      await user.click(screen.getByText('sidebar.delete_account'));
      await user.click(screen.getByText('sidebar.delete_account_confirm'));

      await waitFor(() => expect(mockLogout).toHaveBeenCalled());
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/users/account'),
        expect.objectContaining({ method: 'DELETE', headers: { Authorization: 'Bearer tok-123' } })
      );
    });

    it('cierra la sesión sin borrar nada si el token ha caducado al confirmar', async () => {
      global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 401 }) as unknown as typeof fetch;
      const user = userEvent.setup();
      render(<ConversationSidebar />);

      await user.click(screen.getByText('sidebar.delete_account'));
      await user.click(screen.getByText('sidebar.delete_account_confirm'));

      await waitFor(() => expect(mockLogout).toHaveBeenCalled());
    });

    it('cierra el panel de privacidad sin dejar nada más abierto', async () => {
      const user = userEvent.setup();
      render(<ConversationSidebar />);

      await user.click(screen.getByText('privacy.title'));
      await user.click(screen.getByText('privacy.close'));

      expect(screen.queryByText('privacy.intro')).not.toBeInTheDocument();
    });

    it('exporta los datos desde el aviso de privacidad y lo cierra', async () => {
      const blob = new Blob(['{}'], { type: 'application/json' });
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        blob: () => Promise.resolve(blob),
      }) as unknown as typeof fetch;
      const clickSpy = vi.fn();
      const originalCreate = document.createElement.bind(document);
      vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
        const el = originalCreate(tag);
        if (tag === 'a') el.click = clickSpy;
        return el;
      });

      const user = userEvent.setup();
      render(<ConversationSidebar />);
      await user.click(screen.getByText('privacy.title'));

      const boton = screen.getByText('privacy.art15_title').closest('div.flex.items-start')!.querySelector('button')!;
      await user.click(boton);

      expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/users/export'), expect.anything());
      expect(screen.queryByText('privacy.intro')).not.toBeInTheDocument();
      vi.restoreAllMocks();
    });

    it('encadena el borrado de cuenta desde el panel de privacidad', async () => {
      const user = userEvent.setup();
      render(<ConversationSidebar />);
      await user.click(screen.getByText('privacy.title'));

      const boton = screen.getByText('privacy.art17_title').closest('div.flex.items-start')!.querySelector('button')!;
      await user.click(boton);

      expect(screen.queryByText('privacy.intro')).not.toBeInTheDocument();
      expect(screen.getByText('sidebar.delete_account_confirm')).toBeInTheDocument();
    });
  });

  describe('selector de idioma', () => {
    it('abre el desplegable y cambia de idioma al elegir una opción', async () => {
      const user = userEvent.setup();
      render(<ConversationSidebar />);

      await user.click(screen.getByText('es'));
      await user.click(screen.getByText('en'));

      expect(screen.queryByText('fr')).not.toBeInTheDocument();
    });
  });

  describe('interacción con una fila de conversación', () => {
    beforeEach(() => {
      mockConversations = [
        { conversation_id: 'c1', started_at: now, status: 'active', deleted_at: null, message_count: 3, last_message: { content: 'Patient report', timestamp: now } },
      ];
    });

    it('oculta el botón de borrar cuando el ratón sale de la fila', () => {
      render(<ConversationSidebar />);
      const fila = screen.getByText('Patient report').closest('div.relative.group')!;

      fireEvent.mouseEnter(fila);
      expect(screen.getByTitle('sidebar.delete')).toBeInTheDocument();

      fireEvent.mouseLeave(fila);
      expect(screen.queryByTitle('sidebar.delete')).not.toBeInTheDocument();
    });

    it('borra la conversación sin activarla al pulsar la papelera', async () => {
      const user = userEvent.setup();
      render(<ConversationSidebar />);
      const fila = screen.getByText('Patient report').closest('div.relative.group')!;

      fireEvent.mouseEnter(fila);
      await user.click(screen.getByTitle('sidebar.delete'));

      expect(mockDeleteConversation).toHaveBeenCalledWith('c1');
      expect(mockSwitchConversation).not.toHaveBeenCalled();
    });
  });

});
