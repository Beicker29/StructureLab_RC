"""Vocabulario de niveles sísmicos del perfil aci-318-25."""


def seismic_levels() -> frozenset[str]:
    return frozenset({"none", "ordinary", "intermediate", "special"})
