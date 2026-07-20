import re


def limpar_cnpj(cnpj: str) -> str:
    return re.sub(r"\D", "", cnpj)


def formatar_cnpj(cnpj: str) -> str:
    c = limpar_cnpj(cnpj)
    if len(c) != 14:
        return cnpj
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:14]}"


def validar_cnpj(cnpj: str) -> bool:
    c = limpar_cnpj(cnpj)
    if len(c) != 14:
        return False
    if len(set(c)) == 1:
        return False

    def calc_digito(nums: str, pesos: list[int]) -> str:
        total = sum(int(n) * p for n, p in zip(nums, pesos))
        resto = total % 11
        return "0" if resto < 2 else str(11 - resto)

    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

    d1 = calc_digito(c[:12], pesos1)
    d2 = calc_digito(c[:13], pesos2)

    return c[12] == d1 and c[13] == d2
