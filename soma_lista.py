def soma_lista(numeros):
    total = 0
    for n in numeros:
        total += n
    return total


if __name__ == "__main__":
    lista = [1, 2, 3, 4]
    resultado = soma_lista(lista)
    print("Resultado:", resultado)
