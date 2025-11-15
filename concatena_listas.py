def concatena_listas(lista1, lista2):
    return lista1 + lista2

primeira = [1, 2, 3]
segunda = None
# BUG: tentar concatenar com None causa TypeError.
resultado = concatena_listas(primeira, segunda)
print("Resultado:", resultado)
