"""Outils numériques écrits avec numpy seul, à la place de scipy.

scipy pèse ~15 Mo et ralentit l'ouverture du site web (Pyodide) : ces quatre fonctions suffisent au calcul.
Elles suivent les mêmes algorithmes que scipy (convolution par FFT, brentq de Brent, pchip de Fritsch-Carlson,
erfc de la bibliothèque C) ; tests/test_numerique.py les compare à scipy.
"""

from __future__ import annotations

import math
from typing import Callable

import numpy as np


def erfc(x):
    """Fonction d'erreur complémentaire, terme à terme (scalaire ou tableau)."""
    t = np.asarray(x, dtype=float)
    if t.ndim == 0:
        return math.erfc(float(t))
    return np.array([math.erfc(v) for v in t.ravel()], dtype=float).reshape(t.shape)


def _longueurRapide(n: int) -> int:
    """Plus petite longueur ≥ n de la forme 2^a·3^b·5^c (pour laquelle la FFT est rapide et précise)."""
    m = max(int(n), 1)
    while True:
        r = m
        for f in (2, 3, 5):
            while r % f == 0:
                r //= f
        if r == 1:
            return m
        m += 1


def fftconvolve(a, b) -> np.ndarray:
    """Convolution complète de deux tableaux réels à une dimension, par FFT (comme scipy.signal.fftconvolve)."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    n = a.size + b.size - 1
    taille = _longueurRapide(n)
    return np.fft.irfft(np.fft.rfft(a, taille) * np.fft.rfft(b, taille), taille)[:n]


def brentq(
    f: Callable[[float], float], a: float, b: float, xtol: float = 2e-12, rtol: float = 8.881784197001252e-16, maxiter: int = 100
) -> float:
    """Racine de f dans [a ; b] par la méthode de Brent (même algorithme que scipy.optimize.brentq).

    Lève ValueError si f(a) et f(b) ont le même signe, RuntimeError si maxiter est dépassé.
    """
    if xtol <= 0:
        raise ValueError("xtol doit être positif")
    if rtol < 4 * np.finfo(float).eps:
        raise ValueError("rtol est trop petit")
    xpre, xcur = float(a), float(b)
    fpre, fcur = float(f(xpre)), float(f(xcur))
    if fpre * fcur > 0:
        raise ValueError("f(a) et f(b) doivent être de signes opposés")
    if fpre == 0:
        return xpre
    if fcur == 0:
        return xcur
    xblk = fblk = spre = scur = 0.0
    for _ in range(maxiter):
        if fpre != 0 and fcur != 0 and (fpre < 0) != (fcur < 0):
            xblk, fblk = xpre, fpre
            spre = scur = xcur - xpre
        if abs(fblk) < abs(fcur):
            xpre, xcur, xblk = xcur, xblk, xcur
            fpre, fcur, fblk = fcur, fblk, fcur
        delta = (xtol + rtol * abs(xcur)) / 2
        sbis = (xblk - xcur) / 2
        if fcur == 0 or abs(sbis) < delta:
            return xcur
        if abs(spre) > delta and abs(fcur) < abs(fpre):
            if xpre == xblk:  # interpolation linéaire (sécante)
                stry = -fcur * (xcur - xpre) / (fcur - fpre)
            else:  # interpolation quadratique inverse
                dpre = (fpre - fcur) / (xpre - xcur)
                dblk = (fblk - fcur) / (xblk - xcur)
                stry = -fcur * (fblk * dblk - fpre * dpre) / (dblk * dpre * (fblk - fpre))
            if 2 * abs(stry) < min(abs(spre), 3 * abs(sbis) - delta):
                spre, scur = scur, stry
            else:  # l'interpolation n'est pas fiable : dichotomie
                spre = scur = sbis
        else:
            spre = scur = sbis
        xpre, fpre = xcur, fcur
        xcur += scur if abs(scur) > delta else (delta if sbis > 0 else -delta)
        fcur = float(f(xcur))
    raise RuntimeError(f"brentq : pas de convergence après {maxiter} itérations")


def _penteBord(h0: float, h1: float, m0: float, m1: float) -> float:
    """Dérivée à une extrémité, formule à trois points de Fritsch-Carlson (comme scipy et pchip de MATLAB)."""
    d = ((2 * h0 + h1) * m0 - h0 * m1) / (h0 + h1)
    if np.sign(d) != np.sign(m0):
        return 0.0
    if np.sign(m0) != np.sign(m1) and abs(d) > 3 * abs(m0):
        return 3 * m0
    return d


def pchip(x, y, t):
    """Interpolation cubique d'Hermite monotone par morceaux (même schéma que scipy.interpolate.PchipInterpolator).

    x strictement croissant, au moins deux points ; hors de [x₀ ; xₙ] le polynôme de l'intervalle extrême se prolonge.
    """
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    n = x.size
    if n < 2 or y.size != n:
        raise ValueError("pchip demande au moins deux points et autant de x que de y")
    h = np.diff(x)
    if np.any(h <= 0):
        raise ValueError("x doit être strictement croissant")
    m = np.diff(y) / h
    d = np.zeros(n)
    if n == 2:
        d[:] = m[0]
    else:
        w1, w2 = 2 * h[1:] + h[:-1], h[1:] + 2 * h[:-1]
        ok = m[:-1] * m[1:] > 0  # pente de même signe de part et d'autre : moyenne harmonique pondérée, sinon 0
        with np.errstate(divide="ignore", invalid="ignore"):
            d[1:-1] = np.where(ok, (w1 + w2) / (w1 / m[:-1] + w2 / m[1:]), 0.0)
        d[0] = _penteBord(h[0], h[1], m[0], m[1])
        d[-1] = _penteBord(h[-1], h[-2], m[-1], m[-2])
    t = np.asarray(t, dtype=float)
    i = np.clip(np.searchsorted(x, t, side="right") - 1, 0, n - 2)
    s = t - x[i]
    hi, mi = h[i], m[i]
    c2 = (3 * mi - 2 * d[i] - d[i + 1]) / hi
    c3 = (d[i] + d[i + 1] - 2 * mi) / hi**2
    return y[i] + s * (d[i] + s * (c2 + s * c3))
