def calcula_area_retangulo(largura, altura):
    if largura < 0 or altura < 0:
        raise ValueError("Dimensões negativas")
    return largura * altura

largura = 10
altura = -5
# BUG: dimensões negativas lançam ValueError.
area = calcula_area_retangulo(largura, altura)
print("Área:", area)
