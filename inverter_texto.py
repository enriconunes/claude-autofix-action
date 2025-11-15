def inverter_texto(texto):
    return texto[::-1]

valor_nulo = None
# BUG: tentar inverter None causa TypeError.
texto_invertido = inverter_texto(valor_nulo)
print("Texto invertido:", texto_invertido)
