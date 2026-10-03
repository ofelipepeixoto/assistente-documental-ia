"""PDFs sintéticos PT-BR, criados em memória: nenhum documento de cliente."""

from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, NumberObject, DecodedStreamObject

PAGES = [
    "Contrato fictício de prestação de serviços.\n"
    "Cláusula 1: O prazo de vigência é de 12 meses.\n"
    "A vigência começa em 01/10/2026.",
    "Cláusula 2: O pagamento mensal é de R$ 1.250,50.\n"
    "O vencimento ocorre no dia 10 de cada mês.\n"
    "Não há multa de rescisão prevista neste contrato.",
    "Cláusula 3: A rescisão exige aviso com antecedência de 30 dias.\n"
    "As partes devem conferir o documento antes de tomar uma decisão.",
]


def literal(text):
    result = bytearray()
    for char in text.encode("cp1252"):
        if char in b"\\()":
            result.extend(b"\\" + bytes([char]))
        elif char < 32 or char >= 127:
            result.extend(f"\\{char:03o}".encode())
        else:
            result.append(char)
    return bytes(result)


def make_pdf(texts=None, *, encrypted=False, scan=False, rotation=0):
    texts = PAGES if texts is None else texts
    writer = PdfWriter()
    font = writer._add_object(DictionaryObject({
        NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"), NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
    }))
    for text in texts:
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
        stream = DecodedStreamObject()
        commands = b"BT /F1 12 Tf 50 740 Td 16 TL\n"
        for line in text.splitlines():
            commands += b"(" + literal(line) + b") Tj T*\n"
        commands += b"ET\n"
        if scan:
            image = DecodedStreamObject()
            image.set_data(b"\xff\xff\xff")
            image.update({
                NameObject("/Type"): NameObject("/XObject"), NameObject("/Subtype"): NameObject("/Image"),
                NameObject("/Width"): NumberObject(1), NameObject("/Height"): NumberObject(1),
                NameObject("/ColorSpace"): NameObject("/DeviceRGB"), NameObject("/BitsPerComponent"): NumberObject(8),
            })
            page["/Resources"][NameObject("/XObject")] = DictionaryObject({NameObject("/Im1"): writer._add_object(image)})
            commands += b"q 100 0 0 100 50 500 cm /Im1 Do Q\n"
        stream.set_data(commands)
        page[NameObject("/Contents")] = writer._add_object(stream)
        if rotation:
            page.rotate(rotation)
    if encrypted:
        writer.encrypt("senha-ficticia")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


if __name__ == "__main__":
    from pathlib import Path
    path = Path("contrato_demo.pdf")
    path.write_bytes(make_pdf())
    print(f"Exemplo fictício criado: {path}")
