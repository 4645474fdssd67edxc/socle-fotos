#!/usr/bin/env python3
"""Gera e valida um CSV da Catawiki a partir de um JSON de lotes.

Uso: python3 scripts/gerar_lote.py lote.json saida.csv
"""
import csv, json, re, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent / "templates"
FIXOS = {
    "Language": "Portuguese",
    "D: Era": "After 2000",
    "D: Estimated period": "2020+",
    "D: Condition": "As new - unused",
}
LEILAO = "Modern Home Decor"
MENSAGEM = "Please place this lot in the Modern Home Decor weekly auction."
TIPOS_PROIBIDOS = {"Casket"}
RE_FOTO = re.compile(r"https://[^\s;]+?\.(?:jpe?g|png|webp)", re.I)


def limpar_fotos(texto):
    if isinstance(texto, list):
        texto = " ".join(texto)
    return list(dict.fromkeys(RE_FOTO.findall(texto)))


def medida(valor):
    if isinstance(valor, (int, float)):
        return f"{valor:g}_cm"
    if re.fullmatch(r"\d+(?:\.\d+)?_cm", str(valor)):
        return str(valor)
    raise ValueError(f"medida inválida: {valor!r}")


def coluna(cabecalho, inicio):
    achadas = [c for c in cabecalho if c.startswith(inicio)]
    if len(achadas) != 1:
        raise ValueError(f"coluna não encontrada de forma única: {inicio!r}")
    return achadas[0]


def gerar(dados, saida):
    categoria = dados["categoria"]
    base = RAIZ / f"{categoria}_template.csv"
    dic = RAIZ / f"{categoria}_dictionary.csv"
    if not base.exists() or not dic.exists():
        raise ValueError(f"categoria sem template: {categoria!r}")
    with open(base, encoding="utf-8-sig", newline="") as f:
        cabecalho = next(csv.reader(f))
    with open(dic, encoding="utf-8-sig", newline="") as f:
        dicionario = list(csv.DictReader(f))
    permitido = lambda nome: {l[nome] for l in dicionario if l.get(nome)}

    linhas, avisos = [], []
    for n, lote in enumerate(dados["lotes"], 1):
        tipo, material = lote["tipo"], lote["material"]
        if tipo in TIPOS_PROIBIDOS:
            raise ValueError(f"lote {n}: tipo proibido {tipo!r}")
        if tipo not in permitido("Object Types"):
            raise ValueError(f"lote {n}: tipo fora do dicionário: {tipo!r}")
        if LEILAO not in permitido("Auction type"):
            raise ValueError(f"leilão fora do dicionário: {LEILAO!r}")
        for m in material.split(";"):
            if m not in permitido("D: Material"):
                raise ValueError(f"lote {n}: material fora do dicionário: {m!r}")
        for nome, valor in FIXOS.items():
            if valor not in permitido(nome):
                raise ValueError(f"valor fixo fora do dicionário: {nome}={valor!r}")
        fotos = limpar_fotos(lote["fotos"])
        if not fotos:
            raise ValueError(f"lote {n}: sem fotos")
        if len(fotos) < 5:
            avisos.append(f"lote {n}: só {len(fotos)} fotos")
        if not str(lote["descricao"]).strip():
            raise ValueError(f"lote {n}: sem descrição")

        linha = dict.fromkeys(cabecalho, "")
        linha.update(FIXOS)
        linha[coluna(cabecalho, "Auction Type")] = LEILAO
        linha[coluna(cabecalho, "Object type")] = tipo
        linha["Description"] = lote["descricao"]
        linha[coluna(cabecalho, "D: Title additional information")] = lote["titulo"]
        linha["D: Material"] = material
        linha["D: Height"] = medida(lote["altura"])
        linha["D: Width"] = medida(lote["largura"])
        linha["D: Depth"] = medida(lote["profundidade"])
        linha["Public photo URL"] = ";".join(fotos)
        linha["Estimated lot value"] = str(lote["valor"])
        linha[coluna(cabecalho, "Message to Expert")] = lote.get("mensagem", MENSAGEM)

        portes = lote["portes"]
        if "perfil" in portes:
            if set(portes) != {"perfil"}:
                raise ValueError(f"lote {n}: usa perfil ou custos manuais, não ambos")
            linha[coluna(cabecalho, "Shipping profile")] = str(portes["perfil"])
        else:
            linha[coluna(cabecalho, "Shipping costs - Portugal")] = str(portes["portugal"])
            linha[coluna(cabecalho, "Shipping costs - Europe")] = str(portes["europa"])
            linha[coluna(cabecalho, "Shipping costs - Rest of World")] = str(portes["mundo"])
        linhas.append([linha[c] for c in cabecalho])

    with open(saida, "w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\r\n").writerows([cabecalho, *linhas])
    with open(saida, encoding="utf-8", newline="") as f:
        lida = list(csv.reader(f))
    if lida[1:] != linhas or any(len(l) != len(cabecalho) for l in lida):
        raise ValueError("falha ao reler o CSV")
    return len(linhas), avisos


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    try:
        total, avisos = gerar(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")), sys.argv[2])
    except (KeyError, ValueError) as erro:
        sys.exit(f"ERRO: {erro}")
    print(f"OK: {total} lote(s) em {sys.argv[2]}")
    for aviso in avisos:
        print(f"AVISO: {aviso}")
