def media(numeros):
    if not numeros:
        raise ZeroDivisionError("Lista vazia")
    return sum(numeros) / len(numeros)

lista_vazia = []
# BUG: chamar media com uma lista vazia causa ZeroDivisionError.
resultado = media(lista_vazia)
print("Média:", resultado)
