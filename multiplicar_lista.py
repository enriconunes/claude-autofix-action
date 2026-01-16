def multiplicar_lista(numeros):
    resultado = 1
    for n in numeros:
        resultado *= n
    return resultado


if __name__ == "__main__":
    produto = multiplicar_lista([1, 2, 3, 4])
    print("Produto:", produto)