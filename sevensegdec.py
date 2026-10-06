#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Decodificador de 7 segmentos basado en una tabla de búsqueda (LUT).

Parte del script base del curso (dargor0/usbbog, digitales_2026_2). Se mantiene
la estructura original (sevensegdec, sevensegdec_tb, sevensegdec_nexys,
read_table, run) y se hicieron estos cambios:

  * read_table valida el archivo (16 líneas, 7 bits cada una) y lanza un error
    claro en vez de devolver una tabla de ceros sin avisar.
  * El testbench cuenta los errores, imprime el resultado de cada caso y tiene
    en cuenta --invert al comparar (en el original, con --invert marcaba error
    en todos los casos).
  * Nuevas opciones --outdir (donde se escriben el VCD y el HDL) y la tabla por
    defecto es tabla.txt.
  * Las pruebas unitarias viven aparte, en test_sevensegdec.py.
"""

import argparse
import os

from myhdl import Signal, always_comb, block, delay, instance, instances, intbv, now

# ---------------------------------------------------------------------------
# Implementación
# ---------------------------------------------------------------------------


@block
def sevensegdec(bcd: Signal, sseg: Signal, decod_table: tuple, invert: bool = False):
    """Decodificador de 7 segmentos"""

    # señal interna para la inversión opcional de la salida
    ssegout = Signal(intbv(0)[7:])

    @always_comb
    def logic():
        """Implementación de la LUT: se basa en la tabla de decodificación"""
        ssegout.next = decod_table[int(bcd)]

    @always_comb
    def invertproc():
        """Proceso de inversión de la salida"""
        if invert:
            sseg.next = ~ssegout
        else:
            sseg.next = ssegout

    # incluye logic e invertproc
    return instances()


# ---------------------------------------------------------------------------
# Testbench (chequeo ad-hoc del curso; las pruebas formales están en pytest)
# ---------------------------------------------------------------------------


@block
def sevensegdec_tb(decod_table: tuple, invert: bool = False, errors: list = None,
                   verbose: bool = True):
    """Testbench del decodificador.

    Recorre las 16 entradas y compara la salida con la tabla. Cada diferencia
    se agrega a la lista `errors` (si se pasa una) y se imprime como ERROR.
    """

    if errors is None:
        errors = []

    bcd_tb = Signal(intbv(0)[4:])
    sseg_tb = Signal(intbv(0)[7:])

    uut = sevensegdec(bcd_tb, sseg_tb, decod_table, invert)

    @instance
    def stimulus():
        """Generación de estímulos"""
        for bcd_in in range(len(decod_table)):
            bcd_tb.next = bcd_in
            yield delay(10)

            sseg_readed = int(sseg_tb.val)
            sseg_expect = decod_table[int(bcd_tb.val)]
            if invert:
                # con --invert la salida llega negada, así que se espera la negada
                sseg_expect = ~sseg_expect & 0x7F

            if sseg_readed != sseg_expect:
                errors.append((bcd_in, sseg_expect, sseg_readed))
                print(f"ERROR: en ({now()}) entrada bcd '{bcd_tb.val}': "
                      f"esperado {sseg_expect:07b} != leído {sseg_readed:07b}")
            elif verbose:
                print(f"OK:    en ({now()}) entrada bcd {bcd_in:2d} ({bcd_in:04b}) -> "
                      f"sseg = {sseg_readed:07b}")

    return instances()


# ---------------------------------------------------------------------------
# Envoltura para la tarjeta Nexys4 DDR (es el módulo que se convierte a HDL)
# ---------------------------------------------------------------------------


@block
def sevensegdec_nexys(bcd: Signal, sseg: Signal, bcdled: Signal, ssanodes: Signal,
                      decod_table: tuple, invert: bool = False):
    """Envoltura para correr la demo en la Nexys4 DDR"""

    ssdec = sevensegdec(bcd, sseg, decod_table, invert)

    @always_comb
    def logic():
        """Llena los LEDs con el valor de los switches y selecciona el display"""
        bcdled.next = bcd
        ssanodes.next = intbv(0xfe)[8:]  # solo se enciende el primer display (activo en 0)

    return instances()


# ---------------------------------------------------------------------------
# Lectura de la tabla
# ---------------------------------------------------------------------------


def read_table(table_file: str) -> tuple:
    """Lee la tabla de decodificación desde un archivo de texto.

    * Cada línea es una cadena de 0 y 1 en el orden "abcdefg".
    * Debe haber exactamente 16 líneas, una por cada valor de 4 bits.
    * Se ignoran las líneas en blanco al final del archivo.

    Lanza ValueError si el formato no es el esperado.
    """
    with open(table_file) as f:
        lines = [line.strip() for line in f.read().splitlines()]

    # se descartan líneas vacías al final (p. ej. un salto de línea de más)
    while lines and lines[-1] == "":
        lines.pop()

    if len(lines) != 16:
        raise ValueError(f"La tabla debe tener 16 líneas y tiene {len(lines)}")

    table = []
    for number, line in enumerate(lines):
        if len(line) != 7 or any(c not in "01" for c in line):
            raise ValueError(f"Línea {number}: se esperaban 7 bits (0/1) y llegó '{line}'")
        table.append(int(line, base=2))
    return tuple(table)


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------


def run():
    """Entrada principal"""

    parser = argparse.ArgumentParser(description="Decodificador de 7 segmentos")
    parser.add_argument("--simulation", action="store_true",
                        help="Si se activa, corre la simulación en Python y genera el VCD")
    parser.add_argument("--invert", action="store_true",
                        help="Invierte las salidas (solo simulación)")
    parser.add_argument("--verilog", action="store_true",
                        help="Convierte a Verilog en lugar de VHDL")
    parser.add_argument("--table", type=str, default="tabla.txt",
                        help="Tabla de decodificación (por defecto: tabla.txt)")
    parser.add_argument("--outdir", type=str, default=".",
                        help="Carpeta de salida para el VCD y el HDL (por defecto: .)")
    args = parser.parse_args()

    table = read_table(args.table)
    os.makedirs(args.outdir, exist_ok=True)

    if args.simulation:
        errors = []
        tb = sevensegdec_tb(table, args.invert, errors)
        tb.config_sim(trace=True, directory=args.outdir)
        tb.run_sim()
        print(f"Simulación terminada: {len(table)} casos, {len(errors)} errores.")

    # Señales para la conversión de sevensegdec_nexys
    ss_sig = {
        "bcd": Signal(intbv(0)[4:]),
        "sseg": Signal(intbv(0)[7:]),
        "bcdled": Signal(intbv(0)[4:]),
        "ssanodes": Signal(intbv(0)[8:]),
        "invert": Signal(False),
        "decod_table": table,
    }
    sscomponent = sevensegdec_nexys(**ss_sig)

    langout = "Verilog" if args.verilog else "VHDL"
    sscomponent.convert(hdl=langout, path=args.outdir)
    print(f"Conversión terminada ({langout}) en '{args.outdir}'.")


if __name__ == "__main__":
    run()
