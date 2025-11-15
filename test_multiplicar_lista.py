import pytest
from multiplicar_lista import multiplicar_lista

def test_multiplicar_lista_ok():
    assert multiplicar_lista([1, 2, 3, 4]) == 24

def test_multiplicar_lista_type_error():
    with pytest.raises(TypeError):
        multiplicar_lista("123")
