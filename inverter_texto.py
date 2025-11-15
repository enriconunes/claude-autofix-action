def inverter_texto(texto):
    return texto[::-1]


if __name__ == "__main__":
    texto_invertido = inverter_texto("abc")
    print("Texto invertido:", texto_invertido)
