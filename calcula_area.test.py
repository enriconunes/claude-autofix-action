import pytest
from calcula_area import calcula_area_retangulo

def test_calcula_area_ok():
    assert calcula_area_retangulo(5, 4) == 20

def test_calcula_area_value_error():
    with pytest.raises(ValueError):
        calcula_area_retangulo(10, -5)
