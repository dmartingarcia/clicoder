import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '../helpers';

import { PrivacyModal } from '@/components/PrivacyModal';

// Cada derecho vive en su propia fila; la acción, si la hay, está dentro.
function fila(clave: string) {
  const titulo = screen.getByText(`privacy.${clave}_title`);
  const contenedor = titulo.closest('div.flex.items-start');
  if (!contenedor) throw new Error(`no hay fila para ${clave}`);
  return contenedor as HTMLElement;
}

describe('PrivacyModal', () => {
  it('enumera los seis derechos del reglamento con su descripción', () => {
    render(<PrivacyModal onClose={vi.fn()} />);

    for (const art of ['art15', 'art16', 'art17', 'art18', 'art20', 'art21']) {
      expect(screen.getByText(`privacy.${art}_title`)).toBeInTheDocument();
      expect(screen.getByText(`privacy.${art}_desc`)).toBeInTheDocument();
    }
  });

  it('identifica al responsable del tratamiento y su base legal', () => {
    render(<PrivacyModal onClose={vi.fn()} />);

    expect(screen.getByText('privacy.contact_name')).toBeInTheDocument();
    expect(screen.getByText('privacy.contact_basis')).toBeInTheDocument();
    expect(screen.getByText('privacy.contact_email').closest('a')).toHaveAttribute(
      'href',
      'mailto:privacy.contact_email'
    );
  });

  it('el derecho de acceso lleva un botón que exporta', async () => {
    const onExport = vi.fn();
    const user = userEvent.setup();
    render(<PrivacyModal onClose={vi.fn()} onExport={onExport} />);

    const boton = fila('art15').querySelector('button');
    expect(boton).not.toBeNull();
    await user.click(boton!);

    expect(onExport).toHaveBeenCalledOnce();
  });

  it('el derecho de supresión lleva un botón que borra la cuenta', async () => {
    const onDeleteAccount = vi.fn();
    const user = userEvent.setup();
    render(<PrivacyModal onClose={vi.fn()} onDeleteAccount={onDeleteAccount} />);

    const boton = fila('art17').querySelector('button');
    expect(boton).not.toBeNull();
    await user.click(boton!);

    expect(onDeleteAccount).toHaveBeenCalledOnce();
  });

  it('sin manejador no pinta el botón, en vez de pintar uno que no hace nada', () => {
    render(<PrivacyModal onClose={vi.fn()} />);

    expect(fila('art15').querySelector('button')).toBeNull();
    expect(fila('art17').querySelector('button')).toBeNull();
  });

  it('los derechos que se ejercen por correo no ofrecen acción en la aplicación', () => {
    render(<PrivacyModal onClose={vi.fn()} onExport={vi.fn()} onDeleteAccount={vi.fn()} />);

    // Rectificación, limitación y oposición van por correo
    for (const art of ['art16', 'art18', 'art21']) {
      expect(fila(art).querySelector('button')).toBeNull();
    }
    // La portabilidad se marca ejercitable pero aún no tiene acción propia
    expect(fila('art20').querySelector('button')).toBeNull();
  });

  it('se cierra desde el pie', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<PrivacyModal onClose={onClose} onExport={vi.fn()} onDeleteAccount={vi.fn()} />);

    await user.click(screen.getByText('privacy.close'));

    expect(onClose).toHaveBeenCalledOnce();
  });
});
