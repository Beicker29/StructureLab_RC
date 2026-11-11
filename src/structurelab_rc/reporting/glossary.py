"""Nombres en palabras de todo lo que imprime la memoria (D-068); aquí no se calcula nada.

CHECKS: prefijo del nombre de una verificación → (capítulo, símbolo de la demanda, símbolo de la capacidad).
VALUES: nombre de un valor intermedio → (descripción, símbolo).
"""

STATUS_TEXT = {"PASS": "CUMPLE", "FAIL": "NO CUMPLE", "INCOMPLETE": "INCOMPLETO", "BLOCKED": "BLOQUEADO"}
PROFILE_NAMES = {"aci-318-25": "ACI CODE-318-25", "nsr-10": "NSR-10 Título C"}
UNITS = {"kN-m": "kN·m", "mm4": "mm⁴", "mm3": "mm³", "mm2": "mm²", "mm2/mm": "mm²/mm", "mm2/m": "mm²/m",
         "kN/m2": "kN/m²", "kN/m3": "kN/m³", "m2": "m²", "m3": "m³", "m4": "m⁴", "deg": "°", "-": "–", "": "–"}
DECIMALS = {"kN·m": 1, "kN": 1, "kPa": 1, "mm": 0, "mm⁴": 0, "mm³": 0, "mm²": 0, "mm²/m": 0, "mm²/mm": 3, "MPa": 2,
            "°": 2, "–": 4, "m²": 3, "m³": 3, "m⁴": 3, "kN/m²": 1, "kN/m³": 1}

# Orden de los prefijos: el primero que coincide gobierna (los más específicos van antes).
CHECKS: tuple[tuple[str, str, str, str], ...] = (
    ("Validacion de entrada", "requirements", "", ""),
    ("Flexion: resistencia", "flexure", "Mu", "φMn"),
    ("Flexion: deformacion neta", "requirements", "εt,min", "εt"),
    ("Flexion: acero minimo", "requirements", "As,min", "As"),
    ("Flexion: separacion por fisuracion", "requirements", "s", "s,máx"),
    ("Flexion: refuerzo superficial", "requirements", "s", "s,máx"),
    ("Viga alta: limite de seccion", "shear", "Vu", "φ0.83√f'c·bw·d"),
    ("Viga alta: refuerzo distribuido transversal", "requirements", "0.0025·bw", "Av/s"),
    ("Viga alta: refuerzo distribuido longitudinal", "requirements", "0.0025·bw·sd", "Aℓd"),
    ("Viga alta: separacion", "requirements", "s", "s,máx"),
    ("Viga alta: cortinas", "requirements", "s entre cortinas", "s,máx"),
    ("Aleta: flexion", "flexure", "Mu por metro", "φMn por metro"),
    ("Aleta: concreto simple", "flexure", "Mu por metro", "φMn por metro"),
    ("Aleta: cortante", "shear", "Vu por metro", "φVc por metro"),
    ("Aleta: deformacion neta", "requirements", "εt,min", "εt"),
    ("Aleta: acero minimo", "requirements", "As,min", "As"),
    ("Aleta: separacion", "requirements", "s", "s,máx"),
    ("Viga T: refuerzo del ala", "requirements", "", ""),
    ("Altura minima de la zarpa", "requirements", "h,mín", "h"),
    ("Cortante: interaccion", "shear", "", ""),
    ("Cortante V3: resistencia", "shear", "Vu3", "φVn3"),
    ("Cortante: resistencia", "shear", "Vu", "φVn"),
    ("Cortante V3: dimensiones", "shear", "Vu3", "φ(Vc + Vs,máx)"),
    ("Cortante: dimensiones", "shear", "Vu", "φ(Vc + Vs,máx)"),
    ("Cortante V3: refuerzo minimo", "requirements", "Av,min/s", "Av/s"),
    ("Cortante: refuerzo minimo", "requirements", "Av,min/s", "Av/s"),
    ("Cortante V3: separacion", "requirements", "s", "s,máx"),
    ("Cortante: separacion", "requirements", "s", "s,máx"),
    ("Torsion: umbral", "torsion", "", ""),
    ("Torsion: dimensiones", "torsion", "esfuerzo combinado", "límite"),
    ("Torsion: refuerzo transversal minimo", "requirements", "(Av + 2At)min/s", "(Av + 2At)/s"),
    ("Torsion: refuerzo transversal", "torsion", "(Av + 2At)/s requerido", "(Av + 2At)/s"),
    ("Torsion: refuerzo longitudinal", "torsion", "Aℓ requerido", "Aℓ"),
    ("Torsion: distribucion", "requirements", "", ""),
    ("Presion admisible", "geotechnical", "pmax", "qa"),
    ("Contacto con el suelo", "geotechnical", "fracción mínima", "fracción en contacto"),
    ("Deslizamiento", "geotechnical", "FS·V", "R"),
    ("Volcamiento", "geotechnical", "FS·Mo", "Mr"),
    ("Zapata: equilibrio", "geotechnical", "", ""),
    ("Zapata: verificacion estructural", "flexure", "", ""),
    ("Zapata combinada: verificacion estructural", "flexure", "", ""),
    ("Viga larga: separacion", "requirements", "s", "s,máx"),
    ("Malla inferior y: acero minimo", "requirements", "As,min", "As"),
    ("Malla inferior y: separacion", "requirements", "s", "s,máx"),
    ("Flexion malla", "flexure", "Mu", "φMn"),
    ("Flexion concreto simple", "flexure", "Mu", "φMn"),
    ("Deformacion neta de traccion malla", "requirements", "εt,min", "εt"),
    ("Acero minimo por punzonamiento", "requirements", "As,min", "As en bslab"),
    ("Transferencia de momento por flexion", "punching", "γf·Msc", "φMn en bslab"),
    ("Transferencia de momento: parte negativa", "punching", "γf·Msc", "φMn superior o simple en bslab"),
    ("Fuera de la franja central", "requirements", "(1 − γs)·As", "As fuera de la franja"),
    ("Acero minimo malla", "requirements", "As,min", "As"),
    ("Separacion maxima malla", "requirements", "s", "s,máx"),
    ("Franja central", "requirements", "γs·As", "As en la franja"),
    ("Altura minima", "requirements", "mínimo", "medido"),
    ("Pasadores: area minima", "requirements", "0.005·Ag", "As de pasadores"),
    ("Cortante en una direccion", "one_way", "Vu", "φVc"),
    ("Punzonamiento", "punching", "vu", "φvc"),
    ("Desarrollo malla", "development", "ℓ requerida", "ℓ disponible"),
    ("Desarrollo barras", "development", "ℓ requerida", "ℓ disponible"),
    ("Desarrollo refuerzo band", "development", "ℓ requerida", "ℓ disponible"),
    ("Pasadores: anclaje", "development", "ℓdc", "espacio disponible"),
    ("Aplastamiento", "bearing", "Pu", "φBn"),
    ("Pasadores: compresion", "bearing", "As requerida", "As de pasadores"),
)

VALUES = {
    "phi": ("Factor de reducción de resistencia", "φ"),
    "Msc x": ("Momento transferido por cortante que varía a lo largo de X", "Msc,x"),
    "Msc": ("Momento transferido entre la columna y la zapata", "Msc"),
    "gamma f": ("Fracción del momento transferida por flexión", "γf"),
    "gamma f Msc": ("Momento transferido por flexión (para la viga de cimentación en su parte negativa)", "γf·Msc"),
    "As bslab": ("Acero inferior dentro de bslab", "As,bslab"),
    "para la viga": ("Momento que debe tomar la viga de cimentación", "M viga"),
    "Msc y": ("Momento transferido por cortante que varía a lo largo de Y", "Msc,y"),
    "Jc x": ("Propiedad Jc de la sección crítica (esfuerzo que varía a lo largo de X)", "Jc,x"),
    "Jc y": ("Propiedad Jc de la sección crítica (esfuerzo que varía a lo largo de Y)", "Jc,y"),
    "xc": ("Centroide del perímetro crítico en X", "xc"),
    "yc": ("Centroide del perímetro crítico en Y", "yc"),
    "cc": ("Recubrimiento libre a la cara en tracción o lateral", "cc"),
    "As,min": ("Acero mínimo", "As,min"),
    "As analisis": ("Acero requerido por análisis", "As,req"),
    "barras": ("Barras en la capa en tracción", "n"),
    "x": ("Posición de la sección", "x"),
    "Mn3": ("Momento nominal respecto del eje 3", "Mn3"),
    "Mn2": ("Momento nominal respecto del eje 2", "Mn2"),
    "Mn": ("Momento nominal", "Mn"),
    "theta": ("Inclinación del eje neutro", "θ"),
    "c": ("Profundidad del eje neutro", "c"),
    "et": ("Deformación neta de tracción", "εt"),
    "Vc": ("Resistencia del concreto a cortante", "Vc"),
    "Vs": ("Resistencia del refuerzo transversal", "Vs"),
    "d": ("Altura efectiva", "d"),
    "At/s": ("Refuerzo de torsión por rama y por unidad de longitud", "At/s"),
    "Av/s": ("Refuerzo de cortante por unidad de longitud", "Av/s"),
    "At/s rama exterior": ("Refuerzo de torsión en la rama exterior", "At/s ext"),
    "across": ("Separación entre ramas a lo ancho", "s ancho"),
    "across_max": ("Separación máxima entre ramas a lo ancho", "s ancho,máx"),
    "Vu2/phiVn2": ("Razón de cortante en la dirección 2", "Vu2/φVn2"),
    "Vu3/phiVn3": ("Razón de cortante en la dirección 3", "Vu3/φVn3"),
    "Tu": ("Momento torsional mayorado", "Tu"),
    "phi Tth": ("Umbral de torsión de diseño", "φTth"),
    "Aoh": ("Área encerrada por el eje del refuerzo transversal", "Aoh"),
    "ph": ("Perímetro del eje del refuerzo transversal", "ph"),
    "N": ("Resultante vertical sobre la base", "N"),
    "mu N": ("Fricción en la base (μ·N)", "μ·N"),
    "ca Ac": ("Adherencia sobre el área en contacto", "ca·Ac"),
    "Pp x": ("Empuje pasivo sobre la cara normal a X", "Pp,x"),
    "Pp y": ("Empuje pasivo sobre la cara normal a Y", "Pp,y"),
    "V": ("Fuerza horizontal en la dirección que gobierna", "V"),
    "R": ("Resistencia al deslizamiento (μ·N + ca·Ac + fp·Pp)", "R"),
    "Mo": ("Momento volcador respecto del borde", "Mo"),
    "Mr": ("Momento resistente respecto del borde (N·L/2)", "Mr"),
    "FS requerido": ("Factor de seguridad mínimo declarado", "FS,mín"),
    "qa": ("Presión admisible bruta sin aumento", "qa"),
    "p esquina -x-y": ("Presión en la esquina (−x, −y)", "p1"),
    "p esquina +x-y": ("Presión en la esquina (+x, −y)", "p2"),
    "p esquina +x+y": ("Presión en la esquina (+x, +y)", "p3"),
    "p esquina -x+y": ("Presión en la esquina (−x, +y)", "p4"),
    "factor sismo qa": ("Factor de aumento de qa con sismo (D-079)", "f"),
    "FS": ("Factor de seguridad obtenido", "FS"),
    "Mx base": ("Momento respecto de X en el centroide de la base", "Mx,base"),
    "My base": ("Momento respecto de Y en el centroide de la base", "My,base"),
    "ex": ("Excentricidad en X", "ex"),
    "ey": ("Excentricidad en Y", "ey"),
    "contacto": ("Fracción de la base en contacto", "Ac/A"),
    "As": ("Área de acero", "As"),
    "cuantia minima": ("Cuantía mínima", "ρmin"),
    "gamma s": ("Fracción del refuerzo en la franja central", "γs"),
    "h calculo": ("Espesor de cálculo del concreto simple (h − 50 mm contra el suelo)", "h"),
    "Sm": ("Módulo elástico de la sección", "Sm"),
    "psi e": ("Factor por recubrimiento de las barras", "ψe"),
    "psi cc": ("Factor por recubrimiento del gancho", "ψcc"),
    "As,req/As,sum": ("Razón As requerido / As suministrado", "As,req/As,sum"),
    "factor exceso": ("Factor por refuerzo en exceso aplicado", "factor exceso"),
    "Vu": ("Fuerza que atraviesa el perímetro crítico", "Vu"),
    "b0": ("Perímetro crítico", "b0"),
    "alpha s": ("Factor de ubicación de la columna", "αs"),
    "gamma v x": ("Fracción del momento transferida por cortante, a lo largo de x", "γv,x"),
    "gamma v y": ("Fracción del momento transferida por cortante, a lo largo de y", "γv,y"),
    "vuv": ("Esfuerzo de cortante sin transferencia de momento", "vuv"),
    "bslab": ("Ancho efectivo para el acero mínimo", "bslab"),
    "A1": ("Área cargada", "A1"),
    "A2": ("Base del tronco de pirámide de apoyo", "A2"),
    "beta1": ("Factor del bloque de esfuerzos", "β1"),
    "ecu": ("Deformación máxima del concreto", "εcu"),
    "alpha1": ("Factor de esfuerzo del bloque equivalente", "0.85"),
    "Es": ("Módulo de elasticidad del acero", "Es"),
    "ety": ("Deformación de fluencia del acero", "εty"),
    "lambda": ("Factor de concreto liviano", "λ"),
    "A": ("Área de la base", "A"),
    "Ix": ("Inercia de la base respecto de X", "Ix"),
    "Iy": ("Inercia de la base respecto de Y", "Iy"),
    "Sx": ("Módulo de sección respecto de X", "Sx"),
    "Sy": ("Módulo de sección respecto de Y", "Sy"),
    "nucleo lx/6": ("Semidiagonal del núcleo central en X", "lx/6"),
    "nucleo ly/6": ("Semidiagonal del núcleo central en Y", "ly/6"),
    "W zapata": ("Peso de la zapata", "Wz"),
    "W pedestal": ("Peso del pedestal", "Wp"),
    "W relleno": ("Peso del relleno", "Wr"),
    "Sobrecarga muerta": ("Fuerza de la sobrecarga muerta", "QD"),
    "Sobrecarga viva": ("Fuerza de la sobrecarga viva", "QL"),
}

# Palabras de los nombres de las verificaciones, escritas sin tilde en el dominio (identificadores estables).
_ACCENTS = {"Presion": "Presión", "Flexion": "Flexión", "Deformacion": "Deformación", "traccion": "tracción",
            "minimo": "mínimo", "minima": "mínima", "Separacion": "Separación", "separacion": "separación",
            "maxima": "máxima", "direccion": "dirección", "area": "área", "compresion": "compresión",
            "Torsion": "Torsión", "seccion": "sección", "interaccion": "interacción", "verificacion": "verificación",
            "Validacion": "Validación", "distribucion": "distribución", "Area": "Área"}


def display(name: str) -> str:
    """Nombre de una verificación para la memoria, con tildes."""
    words = []
    for word in name.split(" "):
        core = word.rstrip(":")
        words.append(_ACCENTS.get(core, core) + word[len(core):])
    return " ".join(words)


def classify(name: str) -> tuple[str, str, str]:
    """Capítulo y símbolos de demanda y capacidad de una verificación; si no está en CHECKS, capítulo "other"."""
    for prefix, chapter, demand, capacity in CHECKS:
        if name.startswith(prefix):
            return chapter, demand, capacity
    return "other", "", ""


def unit_of(key: str) -> tuple[str, str]:
    """Nombre y unidad de presentación de una clave como "Mn [kN-m]"."""
    if "[" not in key:
        return key, "–"
    name, unit = key.split(" [", 1)
    unit = unit[:-1]
    return name, UNITS.get(unit, unit)


def describe(name: str) -> tuple[str, str]:
    """Descripción en palabras y símbolo de un valor; los desconocidos se muestran tal cual."""
    return VALUES.get(name, (name, name))


def number(value: float | None, unit: str) -> str:
    if value is None:
        return "–"
    return f"{value:.{DECIMALS.get(unit, 4)}f}"
