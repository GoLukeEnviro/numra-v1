"""Minimale, deterministische Test-PDFs (Helvetica, WinAnsi) ohne zusaetzliche Abhaengigkeit."""


def _escape(line: str) -> str:
    out = []
    for ch in line:
        if ch in "()\\":
            out.append("\\" + ch)
        elif ord(ch) < 128:
            out.append(ch)
        else:
            out.append("\\" + format(ch.encode("cp1252")[0], "03o"))
    return "".join(out)


def make_pdf(pages: list[list[str]]) -> bytes:
    """pages: je Seite eine Liste von Textzeilen."""
    objects: list[bytes] = []
    n = len(pages)
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(n))
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode())
    font_id = 3 + 2 * n
    for i, lines in enumerate(pages):
        content = "BT /F1 10 Tf 40 780 Td 14 TL\n"
        content += "".join(f"({_escape(line)}) Tj T*\n" for line in lines) + "ET"
        data = content.encode("ascii")
        page = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {4 + 2 * i} 0 R >>"
        )
        objects.append(page.encode())
        objects.append(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(data), data))
    objects.append(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    )
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return bytes(out)


GERMAN = [
    "Dein persönlicher Bericht zeigt, wie du mit Veränderungen umgehst und was dir dabei",
    "Kraft gibt. Die Zahlen beschreiben keine feste Prognose, sondern eine Einladung, die",
    "eigenen Muster bewusst wahrzunehmen. Wenn du dich überfordert fühlst, hilft es oft,",
    "kleine Schritte zu planen und Pausen ernst zu nehmen. Auch in schwierigen Wochen kann",
    "man sich auf das besinnen, was bereits gut funktioniert. Das Ergebnis ist nicht endgültig",
    "und wird mit deiner Entwicklung nach und nach klarer, sodass du neue Entscheidungen",
    "mit mehr Ruhe und einem guten Gefühl für deine Stärken treffen kannst und dabei nicht",
    "vergisst, dass es auch Zeit für Erholung und für die Menschen braucht, die dir wichtig sind.",
]
