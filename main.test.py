import pytest
from arquivo import soma_lista  # substitui "arquivo" pelo nome do teu ficheiro

def test_soma_lista_ok():
    assert soma_lista([1, 2, 3, 4]) == 10

def test_soma_lista_type_error():
    # chama com um inteiro e verifica que lança TypeError
    with pytest.raises(TypeError):
        soma_lista(5)
