def soma_lista(numeros):
    total = 0
    for n in numeros:
        total += n
    return total

lista = [1, 2, 3, 4]

# BUG: estamos a chamar a função com um valor inteiro,
# quando ela espera uma lista — isso vai gerar um TypeError.
resultado = soma_lista(5)

print("Resultado:", resultado)
