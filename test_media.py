import pytest
from media import media

def test_media_ok():
    assert media([1, 2, 3, 4]) == 2.5

def test_media_zero_division():
    with pytest.raises(ZeroDivisionError):
        media([])
