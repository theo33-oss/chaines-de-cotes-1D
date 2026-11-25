"""Outils numériques maison (core/numerique.py) : comparaison à scipy, qui sert ici de référence."""

import math

import numpy as np
import pytest
from scipy.interpolate import PchipInterpolator
from scipy.optimize import brentq as brentq_scipy
from scipy.signal import fftconvolve as fftconvolve_scipy
from scipy.special import erfc as erfc_scipy

from chainecotes.core import numerique


def test_erfc_scalaire_et_tableau():
    z = np.linspace(-8, 8, 321)
    assert np.allclose(numerique.erfc(z), erfc_scipy(z), rtol=1e-13, atol=0)
    assert numerique.erfc(0.3) == pytest.approx(erfc_scipy(0.3), rel=1e-14)
    assert numerique.erfc(z.reshape(3, -1)[:, :5]).shape == (3, 5)


@pytest.mark.parametrize("na, nb", [(1, 9), (7, 7), (101, 3), (4001, 3001), (8003, 5)])
def test_fftconvolve_comme_scipy(na, nb):
    rng = np.random.default_rng(na * nb)
    a, b = rng.random(na), rng.random(nb)
    attendu = fftconvolve_scipy(a, b)
    obtenu = numerique.fftconvolve(a, b)
    assert obtenu.shape == attendu.shape
    assert np.max(np.abs(obtenu - attendu)) < 1e-12 * max(1.0, np.max(attendu))


@pytest.mark.parametrize(
    "f, a, b, xtol, rtol",
    [
        (lambda x: x**3 - 2 * x - 5, 2.0, 3.0, 1e-14, 1e-14),
        (lambda x: math.cos(x) - x, 0.0, 1.0, 1e-15, 1e-14),
        (lambda x: math.exp(x) - 1e6, 0.0, 30.0, 1e-14, 1e-13),
        (lambda x: x**9 - 1e-7, 0.0, 1.0, 1e-14, 1e-14),
        (lambda x: math.tanh(40 * (x - 0.3)), -1.0, 2.0, 2e-12, 8.9e-16),
    ],
)
def test_brentq_comme_scipy(f, a, b, xtol, rtol):
    attendu = brentq_scipy(f, a, b, xtol=xtol, rtol=rtol, maxiter=1000)
    obtenu = numerique.brentq(f, a, b, xtol=xtol, rtol=rtol, maxiter=1000)
    assert obtenu == pytest.approx(attendu, abs=1e-12, rel=1e-12)
    assert abs(f(obtenu)) < 1e-6 * max(1.0, abs(f(a)), abs(f(b)))


def test_brentq_erreurs():
    with pytest.raises(ValueError):
        numerique.brentq(lambda x: x * x + 1, -1, 1)
    with pytest.raises(RuntimeError):
        numerique.brentq(lambda x: x**3 - 2 * x - 5, 2.0, 3.0, xtol=1e-14, maxiter=2)
    assert numerique.brentq(lambda x: x, 0.0, 1.0) == 0.0


@pytest.mark.parametrize("seed", range(8))
def test_pchip_comme_scipy(seed):
    rng = np.random.default_rng(seed)
    n = int(rng.integers(3, 12))
    x = np.sort(rng.uniform(-50, 300, n)) + np.arange(n) * 0.5
    y = np.cumsum(rng.normal(0, 1, n)) if seed % 2 else np.cumsum(rng.random(n))  # non monotone, puis monotone
    t = np.linspace(x[0] - 30, x[-1] + 30, 400)  # y compris hors du domaine
    assert np.allclose(numerique.pchip(x, y, t), PchipInterpolator(x, y)(t), rtol=1e-12, atol=1e-12)


def test_pchip_deux_points_et_nœuds():
    x, y = np.array([0.0, 2.0]), np.array([1.0, 5.0])
    assert numerique.pchip(x, y, np.array([0.0, 1.0, 2.0])) == pytest.approx([1.0, 3.0, 5.0])
    x3, y3 = np.array([0.0, 1.0, 3.0]), np.array([2.0, 2.0, 7.0])
    assert numerique.pchip(x3, y3, x3) == pytest.approx(y3)
    with pytest.raises(ValueError):
        numerique.pchip(np.array([0.0, 0.0]), np.array([1.0, 2.0]), 0.5)
