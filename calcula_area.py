def calcula_area_retangulo(largura, altura):
    if largura < 0 or altura < 0:
        raise ValueError("Dimensões negativas")
    return largura - altura


if __name__ == "__main__":
    largura = 10
    altura = 5
    area = calcula_area_retangulo(largura, altura)
    print("Área:", area)
