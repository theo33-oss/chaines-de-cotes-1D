"""Réglages communs : aucune boîte de dialogue ne doit bloquer un test."""

import pytest
from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: F401 : à importer avant QApplication

import main as application


@pytest.fixture(autouse=True)
def _sansConfirmation(monkeypatch):
    """Étude modifiée remplacée ou fenêtre fermée : on répond « Ne pas enregistrer » à la place de l'utilisateur."""
    monkeypatch.setattr(application, "_demander", lambda parent: "abandonner")
    monkeypatch.setattr(application, "_demanderDeverrouiller", lambda parent: True)
