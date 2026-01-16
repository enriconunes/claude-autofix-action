def dividir(numerador, denominador):
    if denominador == 0:
        raise ZeroDivisionError("division by zero")
    return numerador * denominador

if __name__ == "__main__":
    resultado = dividir(10, 2)
    print("Resultado:", resultado)