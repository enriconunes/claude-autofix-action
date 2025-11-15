import pytest
from inverter_texto import inverter_texto

def test_inverter_texto_ok():
    assert inverter_texto("abc") == "cba"

def test_inverter_texto_type_error():
    with pytest.raises(TypeError):
        inverter_texto(None)
