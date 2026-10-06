import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '../helpers';

const mockLogin = vi.fn();
const mockRegister = vi.fn();
const mockClearPending = vi.fn();
let mockPendingEmail: string | null = null;

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    login: mockLogin,
    register: mockRegister,
    pendingEmail: mockPendingEmail,
    user: null,
    token: null,
    logout: vi.fn(),
    clearPending: mockClearPending,
  }),
}));

import { AuthPage } from '@/components/AuthPage';

describe('AuthPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockPendingEmail = null;
    mockClearPending.mockClear();
    mockLogin.mockResolvedValue({});
    mockRegister.mockResolvedValue({});
  });

  describe('login mode (default)', () => {
    it('renders email and password inputs', () => {
      render(<AuthPage />);
      expect(screen.getByPlaceholderText('doctor@hospital.com')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('••••••••')).toBeInTheDocument();
    });

    it('does NOT show register-only fields', () => {
      render(<AuthPage />);
      expect(screen.queryByPlaceholderText('Juan')).not.toBeInTheDocument();
    });

    it('calls login with email + password on submit', async () => {
      const user = userEvent.setup();
      render(<AuthPage />);

      await user.type(screen.getByPlaceholderText('doctor@hospital.com'), 'doc@test.com');
      await user.type(screen.getByPlaceholderText('••••••••'), 'pass1234');
      await user.click(screen.getByRole('button', { name: /auth\.submit_login/i }));

      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalledWith('doc@test.com', 'pass1234');
      });
    });

    it('shows error message when login returns an error', async () => {
      mockLogin.mockResolvedValue({ error: 'Invalid credentials' });
      const user = userEvent.setup();
      render(<AuthPage />);

      await user.type(screen.getByPlaceholderText('doctor@hospital.com'), 'x@x.com');
      await user.type(screen.getByPlaceholderText('••••••••'), 'wrong');
      await user.click(screen.getByRole('button', { name: /auth\.submit_login/i }));

      await waitFor(() => {
        expect(screen.getByText('Invalid credentials')).toBeInTheDocument();
      });
    });

    it('clears error when switching modes', async () => {
      mockLogin.mockResolvedValue({ error: 'Invalid credentials' });
      const user = userEvent.setup();
      render(<AuthPage />);

      await user.type(screen.getByPlaceholderText('doctor@hospital.com'), 'x@x.com');
      await user.type(screen.getByPlaceholderText('••••••••'), 'wrong');
      await user.click(screen.getByRole('button', { name: /auth\.submit_login/i }));
      await waitFor(() => expect(screen.getByText('Invalid credentials')).toBeInTheDocument());

      await user.click(screen.getByText('auth.register'));
      expect(screen.queryByText('Invalid credentials')).not.toBeInTheDocument();
    });
  });

  describe('register mode', () => {
    it('shows additional fields after clicking register tab', async () => {
      const user = userEvent.setup();
      render(<AuthPage />);
      await user.click(screen.getByText('auth.register'));

      expect(screen.getByPlaceholderText('Juan')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('García López')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('dr_garcia')).toBeInTheDocument();
    });

    it('calls register with all fields on submit', async () => {
      const user = userEvent.setup();
      render(<AuthPage />);
      await user.click(screen.getByText('auth.register'));

      await user.type(screen.getByPlaceholderText('Juan'), 'Maria');
      await user.type(screen.getByPlaceholderText('García López'), 'Lopez');
      await user.type(screen.getByPlaceholderText('dr_garcia'), 'dr_maria');
      await user.type(screen.getByPlaceholderText('doctor@hospital.com'), 'maria@hosp.com');
      await user.type(screen.getByPlaceholderText('auth.password_placeholder_register'), 'Password123!');
      await user.click(screen.getByRole('button', { name: /auth\.submit_register/i }));

      await waitFor(() => {
        expect(mockRegister).toHaveBeenCalledWith({
          first_name: 'Maria',
          last_name: 'Lopez',
          username: 'dr_maria',
          email: 'maria@hosp.com',
          password: 'Password123!',
        });
      });
    });
  });

  describe('pending email confirmation screen', () => {
    it('shows confirmation UI when pendingEmail is set', () => {
      mockPendingEmail = 'doctor@hospital.com';
      render(<AuthPage />);
      expect(screen.queryByPlaceholderText('doctor@hospital.com')).not.toBeInTheDocument();
      expect(screen.getByText('auth.check_email_title')).toBeInTheDocument();
    });

    it('volver al login limpia el correo pendiente', async () => {
      mockPendingEmail = 'doctor@hospital.com';
      const user = userEvent.setup();
      render(<AuthPage />);

      await user.click(screen.getByText('auth.back_to_login'));

      // Sin esto la pantalla se repinta sola y el usuario se queda atascado
      expect(mockClearPending).toHaveBeenCalledOnce();
    });
  });

  describe('aviso de privacidad desde el registro', () => {
    it('se abre desde el formulario de registro y se cierra desde su propio botón', async () => {
      const user = userEvent.setup();
      render(<AuthPage />);
      await user.click(screen.getByText('auth.register'));

      await user.click(screen.getByText('privacy.learn_more'));
      expect(screen.getByText('privacy.intro')).toBeInTheDocument();

      await user.click(screen.getByText('privacy.close'));
      expect(screen.queryByText('privacy.intro')).not.toBeInTheDocument();
    });
  });

  describe('enlace inferior para cambiar de modo', () => {
    it('pasa a registro desde el enlace de pie, no solo desde la pestaña superior', async () => {
      const user = userEvent.setup();
      render(<AuthPage />);

      await user.click(screen.getByText('auth.sign_up'));

      expect(screen.getByPlaceholderText('Juan')).toBeInTheDocument();
    });
  });
});
