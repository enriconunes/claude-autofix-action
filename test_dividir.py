import pytest
from dividir import dividir

def test_dividir_ok():
    assert dividir(10, 2) == 5

def test_dividir_zero_division():
    with pytest.raises(ZeroDivisionError):
        dividir(10, 0)
