import pytest
from soma_lista import soma_lista

def test_soma_lista_ok():
    assert soma_lista([1, 2, 3, 4]) == 10

def test_soma_lista_type_error():
    with pytest.raises(TypeError):
        soma_lista(5)
