"""Longitud de desarrollo requerida, común a todos los elementos (zapatas ahora, vigas y columnas después): una sola fuente.

Cada elemento describe la barra (BarAnchorage: diámetro, cómo termina, recubrimientos, separación y la razón As requerido /
As suministrado); aquí se eligen la ecuación y los factores del perfil (ψe por el recubrimiento declarado en materials,
ψcc de ganchos y el factor de refuerzo en exceso si el perfil lo permite con el nivel sísmico, D-071) y se arma el Check.
"""

from dataclasses import dataclass
from typing import Literal

from structurelab_rc.codes.registry import Profile
from structurelab_rc.domain.check import Check, check_from_errors
from structurelab_rc.domain.shear_strength import concrete_lambda
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import StructuredError
from structurelab_rc.model.project import Materials


@dataclass(frozen=True)
class BarAnchorage:
    """Barra que se desarrolla, en mm. Rectas: cb (el menor entre la distancia del centro de la barra a la superficie más
    cercana y la mitad de la separación), concreto fresco bajo la barra, recubrimiento libre y separación libre. Ganchos:
    recubrimiento lateral libre (normal al plano del gancho) y recubrimiento sobre la extensión. excess es As requerido /
    As suministrado (≤ 1; 1 si no se calcula). Compresión: solo el diámetro."""

    diameter: float
    end: Literal["straight", "hook", "compression"]
    cb: float = 0.0
    concrete_below: float = 0.0
    clear_cover: float = 0.0
    clear_spacing: float = 0.0
    side_cover: float = 0.0
    extension_cover: float = 0.0
    excess: float = 1.0


@dataclass(frozen=True)
class DevelopmentLength:
    length: float
    clause: str
    values: tuple[tuple[str, float], ...] = ()
    note: str = ""


def _excess(profile: Profile, bar: BarAnchorage, seismic_level: str) -> tuple[float, str]:
    """Factor de refuerzo en exceso que se aplica y, si hay exceso pero no se permite, por qué."""
    if bar.excess >= 1.0:
        return 1.0, ""
    if profile.development.excess_factor_permitted(bar.end, seismic_level):
        return bar.excess, ""
    ends = {"straight": "rectas", "hook": "con gancho", "compression": "a compresion"}
    return 1.0, f"Factor de refuerzo en exceso no aplicado: no lo permite {profile.development.clauses()['excess']} " \
                f"para barras {ends[bar.end]} con nivel sismico {seismic_level} (D-071)"


def required_length(profile: Profile, materials: Materials, bar: BarAnchorage, seismic_level: str) -> DevelopmentLength | StructuredError:
    """Longitud requerida (mm), numeral, factores usados y nota."""
    lam = concrete_lambda(profile, materials)
    if isinstance(lam, StructuredError):
        return lam
    development, fy, fc, db = profile.development, materials.fy, materials.fc, bar.diameter
    clauses = development.clauses()
    if bar.end == "compression":
        return DevelopmentLength(development.compression_development_length(fy=fy, fc=fc, lam=lam, db=db), clauses["compression"])
    excess, note = _excess(profile, bar, seismic_level)
    excess_values: tuple[tuple[str, float], ...] = (("As,req/As,sum", bar.excess),) if bar.excess < 1.0 else ()
    clause = clauses[bar.end if bar.end == "hook" else "tension"] + (f"; {clauses['excess']}" if excess < 1.0 else "")
    if bar.end == "hook":
        psi_e = development.hook_coating_factor(materials.coating)
        psi_cc = development.hook_cover_factor(db=db, side_cover=bar.side_cover, extension_cover=bar.extension_cover)
        length = development.hook_development_length(fy=fy, fc=fc, lam=lam, db=db, psi_e=psi_e, psi_cc=psi_cc, excess=excess)
        values = (("psi e", psi_e), ("psi cc", psi_cc), *excess_values, ("factor exceso", excess))
        return DevelopmentLength(length, clause, values, note)
    psi_e = development.tension_coating_factor(materials.coating, db=db, clear_cover=bar.clear_cover, clear_spacing=bar.clear_spacing)
    length = development.tension_development_length(fy=fy, fc=fc, lam=lam, db=db, cb=bar.cb, concrete_below=bar.concrete_below,
                                                    psi_e=psi_e, excess=excess)
    return DevelopmentLength(length, clause, (("psi e", psi_e), *excess_values, ("factor exceso", excess)), note)


def development_check(name: str, required: DevelopmentLength | StructuredError, available: float, note: str = "") -> Check:
    """Longitud requerida frente a la disponible."""
    if isinstance(required, StructuredError):
        return check_from_errors(name, [required])
    notes = "; ".join(text for text in (note, required.note) if text)
    return Check(name, Status.PASS if required.length <= available else Status.FAIL, clause=required.clause,
                 demand=required.length, capacity=available, unit="mm", values=required.values, note=notes)


def lap_splice(profile: Profile, materials: Materials, bar: BarAnchorage,
               given: tuple[float, float]) -> tuple[float, str] | StructuredError:
    """(longitud, clase) del empalme por traslapo a tracción de una barra recta (D-125): ℓd del perfil sin su mínimo ni el
    factor de refuerzo en exceso (ACI 25.5.2.1, NSR-10 C.12.15.1) y la clase A o B según given = (As provisto/As
    requerido en el empalme, fracción del acero empalmado en la sección)."""
    lam = concrete_lambda(profile, materials)
    if isinstance(lam, StructuredError):
        return lam
    development = profile.development
    psi_e = development.tension_coating_factor(materials.coating, db=bar.diameter, clear_cover=bar.clear_cover,
                                               clear_spacing=bar.clear_spacing)
    length = development.tension_development_length(fy=materials.fy, fc=materials.fc, lam=lam, db=bar.diameter, cb=bar.cb,
                                                    concrete_below=bar.concrete_below, psi_e=psi_e, excess=1.0, minimum=False)
    splice_class = profile.detailing.lap_splice_class(*given)
    return profile.detailing.tension_lap_length(length, splice_class), splice_class
