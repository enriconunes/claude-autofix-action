import pytest
from concatena_listas import concatena_listas

def test_concatena_listas_ok():
    assert concatena_listas([1], [2, 3]) == [1, 2, 3]

def test_concatena_listas_type_error():
    with pytest.raises(TypeError):
        concatena_listas([1, 2, 3], None)
