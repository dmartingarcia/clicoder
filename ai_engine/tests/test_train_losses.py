"""
Tests de las pérdidas y utilidades nuevas de train.py (ZLPR, R-Drop, EMA de pesos).
Solo tensores: no cargan el encoder ni tocan la GPU.
"""

import sys
from pathlib import Path

import pytest
import torch
import torch.nn as nn

sys.path.insert(0, str(Path(__file__).parent.parent))

from train import WeightEMA, rdrop_loss, zlpr_loss


def test_zlpr_premia_el_orden_correcto():
    t = torch.tensor([[1.0, 0.0, 0.0, 0.0]])
    bien = torch.tensor([[6.0, -6.0, -6.0, -6.0]])
    mal = torch.tensor([[-6.0, 6.0, 6.0, 6.0]])
    assert zlpr_loss(bien, t) < zlpr_loss(mal, t)


def test_zlpr_es_casi_cero_con_separacion_perfecta():
    t = torch.tensor([[1.0, 1.0, 0.0, 0.0]])
    z = torch.tensor([[20.0, 20.0, -20.0, -20.0]])
    assert zlpr_loss(z, t).item() == pytest.approx(0.0, abs=1e-6)


def test_zlpr_baja_al_subir_un_positivo_por_encima_de_un_negativo():
    t = torch.tensor([[1.0, 0.0]])
    antes = zlpr_loss(torch.tensor([[0.0, 1.0]]), t)
    despues = zlpr_loss(torch.tensor([[1.0, 0.0]]), t)
    assert despues < antes


def test_zlpr_soporta_documentos_sin_positivos_y_sin_negativos():
    z = torch.tensor([[1.0, 2.0, 3.0]])
    solo_negativos = zlpr_loss(z, torch.zeros_like(z))
    solo_positivos = zlpr_loss(z, torch.ones_like(z))
    for v in (solo_negativos, solo_positivos):
        assert torch.isfinite(v)
        assert v.item() >= 0.0


def test_zlpr_ignora_positivos_suavizados_por_debajo_de_0_5():
    # label_smoothing=0.1 deja los positivos en 0.9: deben seguir contando como positivos
    z = torch.tensor([[5.0, -5.0]])
    assert zlpr_loss(z, torch.tensor([[0.9, 0.0]])) == pytest.approx(
        zlpr_loss(z, torch.tensor([[1.0, 0.0]])).item(), abs=1e-6
    )


def test_zlpr_propaga_gradiente():
    z = torch.tensor([[0.5, -0.5, 0.2]], requires_grad=True)
    zlpr_loss(z, torch.tensor([[1.0, 0.0, 0.0]])).backward()
    assert z.grad is not None and torch.isfinite(z.grad).all()
    assert z.grad.abs().sum() > 0


def test_zlpr_estable_con_muchas_clases():
    torch.manual_seed(0)
    z = torch.randn(4, 1767) * 10
    t = (torch.rand(4, 1767) < 0.01).float()
    v = zlpr_loss(z, t)
    assert torch.isfinite(v)


def test_rdrop_es_cero_si_las_dos_pasadas_coinciden():
    z = torch.randn(3, 10)
    assert rdrop_loss(z, z).item() == pytest.approx(0.0, abs=1e-7)


def test_rdrop_crece_con_la_discrepancia():
    a = torch.zeros(1, 5)
    poco = rdrop_loss(a, torch.full((1, 5), 0.5))
    mucho = rdrop_loss(a, torch.full((1, 5), 5.0))
    assert 0 < poco.item() < mucho.item()


def test_rdrop_es_simetrico():
    a, b = torch.randn(2, 6), torch.randn(2, 6)
    assert rdrop_loss(a, b).item() == pytest.approx(rdrop_loss(b, a).item(), abs=1e-6)


def _modelo():
    m = nn.Linear(3, 2)
    with torch.no_grad():
        m.weight.fill_(1.0)
        m.bias.fill_(0.0)
    return m


def test_ema_arranca_en_los_pesos_actuales():
    m = _modelo()
    ema = WeightEMA(m, 0.9)
    assert torch.allclose(ema.shadow["weight"], m.weight)


def test_ema_sigue_a_los_pesos_con_el_decaimiento_indicado():
    m = _modelo()
    ema = WeightEMA(m, 0.9)
    with torch.no_grad():
        m.weight.fill_(2.0)
    ema.update(m)
    assert ema.shadow["weight"].mean().item() == pytest.approx(1.1, abs=1e-6)


def test_ema_ignora_parametros_congelados():
    m = _modelo()
    m.bias.requires_grad = False
    ema = WeightEMA(m, 0.9)
    assert "bias" not in ema.shadow
    assert "weight" in ema.shadow


def test_ema_incorpora_parametros_descongelados_despues():
    m = _modelo()
    m.bias.requires_grad = False
    ema = WeightEMA(m, 0.9)
    m.bias.requires_grad = True
    ema.update(m)
    assert "bias" in ema.shadow


def test_ema_applied_sustituye_y_restaura_los_pesos():
    m = _modelo()
    ema = WeightEMA(m, 0.9)
    with torch.no_grad():
        m.weight.fill_(2.0)
    with ema.applied(m):
        assert m.weight.mean().item() == pytest.approx(1.0)
    assert m.weight.mean().item() == pytest.approx(2.0)


def test_ema_restaura_los_pesos_aunque_falle_la_evaluacion():
    m = _modelo()
    ema = WeightEMA(m, 0.9)
    with torch.no_grad():
        m.weight.fill_(2.0)
    with pytest.raises(RuntimeError), ema.applied(m):
        raise RuntimeError("fallo durante la evaluación")
    assert m.weight.mean().item() == pytest.approx(2.0)
