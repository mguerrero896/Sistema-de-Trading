"""El reloj de bolsa, fijado — y el tripwire que impide volver al reloj local.

La semántica de ``ultima_sesion_completada`` se fija con instantes controlados
(antes del cierre, después del cierre, fin de semana), y un escaneo del código
falla si cualquier módulo del sistema vuelve a leer el reloj de la máquina para
una decisión de mercado. La regla completa vive en el docstring de
``sistema_de_trading.reloj_de_bolsa``.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from sistema_de_trading import reloj_de_bolsa
from sistema_de_trading.reloj_de_bolsa import NUEVA_YORK, ultima_sesion_completada

RAIZ = Path(__file__).resolve().parents[1]


def _con_reloj(monkeypatch, momento: dt.datetime) -> None:
    monkeypatch.setattr(reloj_de_bolsa, "ahora_ny", lambda: momento)


def test_antes_del_cierre_la_sesion_de_hoy_no_cuenta(monkeypatch) -> None:
    # Martes 2026-09-01 a las 10:00 NY: la sesión del 1 sigue abierta.
    _con_reloj(monkeypatch, dt.datetime(2026, 9, 1, 10, 0, tzinfo=NUEVA_YORK))
    assert ultima_sesion_completada() == dt.date(2026, 8, 31)


def test_despues_del_cierre_la_sesion_de_hoy_ya_cuenta(monkeypatch) -> None:
    _con_reloj(monkeypatch, dt.datetime(2026, 9, 1, 16, 30, tzinfo=NUEVA_YORK))
    assert ultima_sesion_completada() == dt.date(2026, 9, 1)


def test_los_fines_de_semana_se_saltan(monkeypatch) -> None:
    # Domingo: la última sesión completada es el viernes.
    _con_reloj(monkeypatch, dt.datetime(2026, 9, 6, 12, 0, tzinfo=NUEVA_YORK))
    assert ultima_sesion_completada() == dt.date(2026, 9, 4)
    # Lunes antes del cierre: también el viernes.
    _con_reloj(monkeypatch, dt.datetime(2026, 9, 7, 9, 0, tzinfo=NUEVA_YORK))
    assert ultima_sesion_completada() == dt.date(2026, 9, 4)


def test_ningun_modulo_lee_el_reloj_de_la_maquina() -> None:
    """Tripwire: date.today() / datetime.now() sin zona quedan prohibidos aquí."""

    patron = re.compile(
        r"date\.today\(\)|datetime\.utcnow\(|datetime\.now\(\s*\)|time\.localtime\("
    )
    objetivos = sorted((RAIZ / "sistema_de_trading").rglob("*.py")) + sorted(
        RAIZ.glob("run_*.py")
    )
    assert objetivos, "el escaneo perdió sus objetivos — el glob está roto, no limpio"
    infractores = []
    for ruta in objetivos:
        if ruta.name == "reloj_de_bolsa.py":
            continue  # su docstring describe el anti-patrón; no lo comete
        for numero, linea in enumerate(
            ruta.read_text(encoding="utf-8").splitlines(), 1
        ):
            if linea.lstrip().startswith("#"):
                continue  # un comentario que menciona el patrón no lo ejecuta
            if patron.search(linea):
                infractores.append(f"{ruta.relative_to(RAIZ)}:{numero}: {linea.strip()}")
    assert not infractores, (
        "lectura del reloj local en código de mercado — usa "
        "sistema_de_trading.reloj_de_bolsa:\n" + "\n".join(infractores)
    )
