"""
Pruebas unitarias (pytest) del decodificador de 7 segmentos.

Se ejecutan con:  pytest -v

A diferencia del testbench del script, que compara la salida contra la misma
tabla que usa el decodificador, aquí los valores esperados están escritos a
mano en este archivo (ESPERADO). Así, un error de digitación en tabla.txt sí
hace fallar las pruebas.
"""
from pathlib import Path

import pytest
from myhdl import Signal, Simulation, delay, instance, intbv

from sevensegdec import read_table, sevensegdec, sevensegdec_nexys, sevensegdec_tb

TABLA_TXT = Path(__file__).parent / "tabla.txt"

# Orden de bits: abcdefg (a es el bit más significativo)
ESPERADO = [
    ("0000", "1111110"),  # 0
    ("0001", "0110000"),  # 1 (a la derecha: b y c)
    ("0010", "1101101"),  # 2
    ("0011", "1111001"),  # 3
    ("0100", "0110011"),  # 4
    ("0101", "1011011"),  # 5
    ("0110", "1011111"),  # 6 cerrado (con segmento a)
    ("0111", "1110000"),  # 7
    ("1000", "1111111"),  # 8
    ("1001", "1111011"),  # 9 cerrado (con segmento d)
    ("1010", "0000001"),  # 10: signo menos (solo g)
    ("1011", "0110110"),  # 11: dos barras verticales (b, c, e, f)
    ("1100", "1100011"),  # 12: cuadro superior (a, b, f, g)
    ("1101", "0011101"),  # 13: cuadro inferior (c, d, e, g)
    ("1110", "1001001"),  # 14: tres rayas (a, d, g)
    ("1111", "0011100"),  # 15: u minúscula (c, d, e)
]
CASOS = [(int(entrada, 2), int(salida, 2)) for entrada, salida in ESPERADO]


@pytest.fixture(scope="module")
def tabla():
    return read_table(TABLA_TXT)


def simular(tabla, valor, invert=False):
    """Instancia el decodificador, aplica `valor` en la entrada y devuelve sseg."""
    bcd = Signal(intbv(0)[4:])
    sseg = Signal(intbv(0)[7:])
    dut = sevensegdec(bcd, sseg, tabla, invert)
    leido = []

    @instance
    def estimulo():
        bcd.next = valor
        yield delay(5)
        leido.append(int(sseg))  # se lee antes de cerrar la simulación

    sim = Simulation(dut, estimulo)
    sim.run(10, quiet=1)
    sim.quit()
    return leido[0]


# --- 1. La tabla del archivo coincide con lo diseñado -----------------------

@pytest.mark.parametrize("entrada, esperado", CASOS, ids=[f"bcd={e}" for e, _ in CASOS])
def test_tabla_archivo(tabla, entrada, esperado):
    assert tabla[entrada] == esperado, (
        f"tabla.txt, línea {entrada}: {tabla[entrada]:07b} != {esperado:07b}")


# --- 2. El hardware simulado produce la salida esperada ---------------------

@pytest.mark.parametrize("entrada, esperado", CASOS, ids=[f"bcd={e}" for e, _ in CASOS])
def test_decodificador(tabla, entrada, esperado):
    assert simular(tabla, entrada) == esperado


@pytest.mark.parametrize("entrada, esperado", CASOS, ids=[f"bcd={e}" for e, _ in CASOS])
def test_decodificador_invertido(tabla, entrada, esperado):
    assert simular(tabla, entrada, invert=True) == (~esperado & 0x7F)


# --- 3. Propiedades del diseño ----------------------------------------------

def test_16_patrones_distintos(tabla):
    assert len(tabla) == 16
    assert len(set(tabla)) == 16, "dos entradas dibujan la misma figura"


def test_ningun_patron_apagado(tabla):
    assert all(valor != 0 for valor in tabla)


def test_decisiones_de_diseno(tabla):
    a, b, c, d, e, f, g = (1 << bit for bit in range(6, -1, -1))
    assert tabla[1] == b | c, "el 1 debe dibujarse a la derecha"
    assert tabla[6] & a, "el 6 es cerrado: debe encender el segmento superior"
    assert tabla[9] & d, "el 9 es cerrado: debe encender el segmento inferior"


# --- 4. Lectura de la tabla -------------------------------------------------

def escribir(ruta, lineas):
    ruta.write_text("\n".join(lineas) + "\n")
    return ruta


def test_read_table_acepta_linea_en_blanco_final(tmp_path):
    ruta = escribir(tmp_path / "t.txt", ["1111110"] * 16 + [""])
    assert len(read_table(ruta)) == 16


def test_read_table_rechaza_menos_de_16_lineas(tmp_path):
    ruta = escribir(tmp_path / "t.txt", ["1111110"] * 15)
    with pytest.raises(ValueError, match="16 líneas"):
        read_table(ruta)


def test_read_table_rechaza_ancho_incorrecto(tmp_path):
    ruta = escribir(tmp_path / "t.txt", ["1111110"] * 15 + ["111111"])
    with pytest.raises(ValueError, match="7 bits"):
        read_table(ruta)


def test_read_table_rechaza_caracteres_no_binarios(tmp_path):
    ruta = escribir(tmp_path / "t.txt", ["1111110"] * 15 + ["11111a0"])
    with pytest.raises(ValueError, match="7 bits"):
        read_table(ruta)


# --- 5. Testbench y conversión a HDL ----------------------------------------

def test_testbench_del_script_sin_errores(tabla):
    errores = []
    tb = sevensegdec_tb(tabla, False, errores, verbose=False)
    tb.run_sim()
    tb.quit_sim()
    assert errores == []


@pytest.mark.parametrize("lenguaje, archivo, palabra", [
    ("VHDL", "sevensegdec_nexys.vhd", "case to_integer(bcd) is"),
    ("Verilog", "sevensegdec_nexys.v", "case (bcd)"),
], ids=["vhdl", "verilog"])
def test_conversion_a_hdl(tabla, tmp_path, lenguaje, archivo, palabra):
    senales = dict(
        bcd=Signal(intbv(0)[4:]), sseg=Signal(intbv(0)[7:]),
        bcdled=Signal(intbv(0)[4:]), ssanodes=Signal(intbv(0)[8:]),
        invert=Signal(False), decod_table=tabla,
    )
    sevensegdec_nexys(**senales).convert(hdl=lenguaje, path=str(tmp_path))
    texto = (tmp_path / archivo).read_text()
    assert palabra in texto
