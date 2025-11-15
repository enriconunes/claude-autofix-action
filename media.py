def media(numeros):
    if not numeros:
        raise ZeroDivisionError("Lista vazia")
    return sum(numeros) / len(numeros)


if __name__ == "__main__":
    resultado = media([1, 2, 3, 4])
    print("Média: ", resultado)

