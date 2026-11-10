"""Erreur commune aux moteurs de calcul."""


class ErreurChaine(Exception):
    """Erreur de saisie ou de calcul, avec un identifiant stable (ex. 'Chaine:Saisie:nonFermee')."""

    def __init__(self, identifiant: str, message: str):
        super().__init__(message)
        self.identifiant = identifiant
        self.message = message

    def __str__(self) -> str:
        return self.message
