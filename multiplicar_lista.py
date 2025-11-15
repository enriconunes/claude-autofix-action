def multiplicar_lista(numeros):
    resultado = 1
    for n in numeros:
        resultado *= n
    return resultado

texto = "123"
# BUG: iterar sobre uma string gera um TypeError durante a multiplicação.
produto = multiplicar_lista(texto)
print("Produto:", produto)
