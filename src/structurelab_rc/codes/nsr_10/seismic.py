"""Vocabulario de niveles sísmicos del perfil nsr-10."""


def seismic_levels() -> frozenset[str]:
    return frozenset({"DMI", "DMO", "DES"})
