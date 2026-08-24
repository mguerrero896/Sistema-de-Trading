"""El reloj de bolsa: toda decisión de fechas de mercado nombra su zona, explícita.

Esta máquina corre en UTC+10 (Sídney): su medianoche local es media mañana en el
piso del NYSE. Un ``date.today()`` tomado del reloj local nombra, durante ~14 horas
de cada día, una sesión de Nueva York que aún no ha terminado — y una descarga de
históricos acotada por esa fecha puede traer la barra parcial del día como si fuera
un cierre. Ese error ya mordió en MDS650 (auditoría adversarial del 2026-08-25) y
la regla registrada con el propietario es la misma en todos los proyectos de
mercado: NUNCA se cambia la zona horaria de la máquina (la automatización local
depende de ella); el CÓDIGO pregunta a este módulo, que responde en la zona de la
bolsa sin importar dónde corra.
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

#: La plaza de todos los activos actuales del sistema.
NUEVA_YORK = ZoneInfo("America/New_York")

#: Cierre de la sesión regular del NYSE.
_CIERRE = dt.time(16, 0)


def ahora_ny() -> dt.datetime:
    """El instante actual en el reloj de la bolsa, con zona explícita."""

    return dt.datetime.now(NUEVA_YORK)


def hoy_ny() -> dt.date:
    """Hoy como lo ve la bolsa — el único «hoy» que una decisión de mercado usa."""

    return ahora_ny().date()


def ultima_sesion_completada() -> dt.date:
    """La última fecha cuya sesión regular del NYSE ya cerró (16:00 NY).

    Es la cota superior honesta para descargar históricos diarios: antes del
    cierre, la barra de «hoy» está incompleta y no debe entrar al dataset. Los
    fines de semana se saltan; un festivo puntual es inocuo como cota (el
    proveedor simplemente no tiene fila para esa fecha).
    """

    momento = ahora_ny()
    fecha = momento.date()
    if momento.time() < _CIERRE:
        fecha -= dt.timedelta(days=1)
    while fecha.weekday() >= 5:
        fecha -= dt.timedelta(days=1)
    return fecha
