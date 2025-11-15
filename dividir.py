def dividir(numerador, denominador):
    return numerador / denominador

# BUG: dividir por zero gera ZeroDivisionError.
resultado = dividir(10, 0)
print("Resultado:", resultado)
