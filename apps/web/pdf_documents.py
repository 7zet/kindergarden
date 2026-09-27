"""Rasmiy moliyaviy hujjatlarni Unicode PDF ko'rinishida yaratish."""

from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from django.conf import settings
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)


def _font():
    name = "DocumentSans"
    if name in pdfmetrics.getRegisteredFontNames():
        return name
    candidates = [
        Path(settings.BASE_DIR) / "assets" / "fonts" / "DejaVuSans.ttf",
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for path in candidates:
        if path.exists():
            pdfmetrics.registerFont(TTFont(name, str(path)))
            pdfmetrics.registerFontFamily(name, normal=name, bold=name, italic=name,
                                          boldItalic=name)
            return name
    return "Helvetica"


def _money(value):
    return f"{value:,.0f}".replace(",", " ") + " so'm"


def _text(value, empty="—"):
    return escape(str(value)) if value not in (None, "") else empty


def _styles():
    font = _font()
    base = getSampleStyleSheet()
    return {
        "normal": ParagraphStyle("DocNormal", parent=base["Normal"], fontName=font,
                                 fontSize=9.5, leading=14, textColor=colors.HexColor("#172033")),
        "small": ParagraphStyle("DocSmall", parent=base["Normal"], fontName=font,
                                fontSize=8, leading=11, textColor=colors.HexColor("#526077")),
        "title": ParagraphStyle("DocTitle", parent=base["Title"], fontName=font,
                                fontSize=17, leading=22, alignment=TA_CENTER,
                                textColor=colors.HexColor("#173f5f"), spaceAfter=7 * mm),
        "right": ParagraphStyle("DocRight", parent=base["Normal"], fontName=font,
                                fontSize=9, leading=13, alignment=TA_RIGHT),
    }


def _p(value, style):
    return Paragraph(_text(value), style)


def _header(story, kg, title, number, styles):
    legal = kg.legal_name or kg.name
    story.append(Table([
        [_p(legal, styles["normal"]), _p(f"№ {number}", styles["right"])],
        [_p(kg.address, styles["small"]), _p(timezone.localdate().strftime("%d.%m.%Y"), styles["right"])],
        [_p(kg.phone, styles["small"]), ""],
    ], colWidths=[120 * mm, 50 * mm], style=TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, -1), (-1, -1), .7, colors.HexColor("#c8d2df")),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 5 * mm),
    ])))
    story.append(Spacer(1, 7 * mm))
    story.append(Paragraph(title, styles["title"]))


def _details(story, rows, styles):
    data = [[_p(label, styles["small"]), _p(value, styles["normal"])] for label, value in rows]
    story.append(Table(data, colWidths=[48 * mm, 122 * mm], style=TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f3f6fa")),
        ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#d7dee8")),
        ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 2.2 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2 * mm),
    ])))


def _items(story, headers, rows, widths, styles):
    data = [[_p(x, styles["small"]) for x in headers]]
    data += [[_p(x, styles["normal"]) for x in row] for row in rows]
    story.append(Table(data, colWidths=widths, repeatRows=1, style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#173f5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#ccd5e0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (-1, 1), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.4 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.4 * mm),
    ])))


def _signatures(story, kg, styles, parent_label="To'lovchi / ota-ona"):
    story.append(Spacer(1, 16 * mm))
    story.append(Table([
        [_p(f"Direktor: {_text(kg.director_name, '________________')}", styles["normal"]),
         _p(f"{parent_label}: __________________", styles["normal"])],
        [_p("Imzo: __________________", styles["small"]),
         _p("Imzo: __________________", styles["small"])],
    ], colWidths=[85 * mm, 85 * mm]))


def _build(title, number, kg, story):
    output = BytesIO()
    styles = _styles()
    doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm,
                            topMargin=16 * mm, bottomMargin=18 * mm,
                            title=title, author=kg.legal_name or kg.name,
                            subject=number)
    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont(_font(), 7.5)
        canvas.setFillColor(colors.HexColor("#6d7888"))
        canvas.drawString(20 * mm, 9 * mm, f"{kg.name} · elektron hujjat")
        canvas.drawRightString(190 * mm, 9 * mm, f"Sahifa {document.page}")
        canvas.restoreState()
    doc.build(story(styles), onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()


def invoice_pdf(invoice):
    kg, child = invoice.kindergarten, invoice.enrollment.child
    def story(s):
        out = []
        _header(out, kg, "INVOYS", invoice.number, s)
        _details(out, [
            ("Bola", child.full_name), ("Bola ID", child.code),
            ("Guruh", invoice.enrollment.group.name),
            ("Hisob davri", invoice.period.strftime("%m.%Y")),
            ("Berilgan sana", invoice.issued_at.strftime("%d.%m.%Y")),
            ("To'lov muddati", invoice.due_at.strftime("%d.%m.%Y")),
            ("Holat", invoice.get_status_display()),
        ], s)
        out.append(Spacer(1, 6 * mm))
        rows = [(line.title, line.get_kind_display(), _money(line.amount))
                for line in invoice.lines.all()]
        _items(out, ["Tavsif", "Turi", "Summa"], rows, [90 * mm, 40 * mm, 40 * mm], s)
        out.append(Spacer(1, 5 * mm))
        _details(out, [("Jami", _money(invoice.total_amount)),
                       ("To'langan", _money(invoice.paid)),
                       ("To'lanishi kerak", _money(invoice.balance))], s)
        _signatures(out, kg, s)
        return out
    return _build("Invoys", invoice.number, kg, story)


def receipt_pdf(payment):
    kg, child = payment.kindergarten, payment.child
    number = f"KV-{payment.created_at:%Y%m%d}-{str(payment.id)[:8].upper()}"
    def story(s):
        out = []
        _header(out, kg, "TO'LOV KVITANSIYASI", number, s)
        _details(out, [
            ("To'lovchi bola", child.full_name if child else "Umumiy to'lov"),
            ("Bola ID", child.code if child else "—"),
            ("Qabul qilingan", timezone.localtime(payment.received_at).strftime("%d.%m.%Y %H:%M")),
            ("To'lov usuli", payment.get_method_display()),
            ("Summa", _money(payment.amount)),
            ("Izoh", payment.note),
            ("Qabul qilgan", payment.created_by.full_name if payment.created_by else "Tizim"),
        ], s)
        allocations = [(a.invoice.number, a.invoice.period.strftime("%m.%Y"), _money(a.amount))
                       for a in payment.allocations.select_related("invoice")]
        if allocations:
            out.append(Spacer(1, 6 * mm))
            _items(out, ["Invoys", "Davr", "Taqsimlangan"], allocations,
                   [75 * mm, 45 * mm, 50 * mm], s)
        if payment.unallocated:
            out.append(Spacer(1, 4 * mm))
            _details(out, [("Avansda qolgan", _money(payment.unallocated))], s)
        _signatures(out, kg, s, "To'lovchi")
        return out
    return _build("To'lov kvitansiyasi", number, kg, story)


def contract_pdf(enrollment):
    kg, child = enrollment.group.kindergarten, enrollment.child
    number = f"SH-{enrollment.started_at:%Y}-{str(enrollment.id)[:8].upper()}"
    payer = child.payer
    def story(s):
        out = []
        _header(out, kg, "MAKTABGACHA TA'LIM XIZMATI SHARTNOMASI", number, s)
        intro = (f"{_text(kg.legal_name or kg.name)} nomidan direktor "
                 f"{_text(kg.director_name, '________________')} va bolaning qonuniy vakili "
                 f"{_text(payer.full_name if payer else None, '________________')} ushbu shartnomani tuzdilar.")
        out.append(Paragraph(intro, s["normal"]))
        out.append(Spacer(1, 5 * mm))
        _details(out, [
            ("Tarbiyalanuvchi", child.full_name), ("Tug'ilgan sana", child.birth_date.strftime("%d.%m.%Y")),
            ("Guruh", enrollment.group.name), ("Tarif", enrollment.tariff.name),
            ("Oylik to'lov", _money(enrollment.tariff.monthly_amount)),
            ("Chegirma", enrollment.discount.name if enrollment.discount else "Mavjud emas"),
            ("Boshlanish", enrollment.started_at.strftime("%d.%m.%Y")),
            ("Tugash", enrollment.ended_at.strftime("%d.%m.%Y") if enrollment.ended_at else "Muddatsiz"),
            ("Vakil telefoni", payer.phone if payer else "—"),
        ], s)
        clauses = [
            ("1. Shartnoma predmeti", "Bog'cha tarbiyalanuvchiga maktabgacha ta'lim va parvarish xizmatlarini ko'rsatadi, vakil esa belgilangan to'lovlarni o'z vaqtida amalga oshiradi."),
            ("2. To'lov tartibi", "To'lov amaldagi tarif, chegirma va bog'chaning moliyaviy siyosati asosida har oy chiqarilgan invoys bo'yicha amalga oshiriladi."),
            ("3. Tomonlarning majburiyatlari", "Bog'cha bolaning xavfsizligi va xizmat sifatini ta'minlaydi. Vakil bola sog'lig'i, allergiyasi va olib ketishga vakolatli shaxslar haqidagi ma'lumotlarni to'g'ri taqdim etadi."),
            ("4. Davomat va olib ketish", "Bolaning kirish-chiqishi tizimda qayd etiladi. Bola faqat vakolat berilgan kontaktga topshiriladi."),
            ("5. Amal qilish va bekor qilish", "Shartnoma ko'rsatilgan sanadan kuchga kiradi. Uni to'xtatish va yakunlash bog'chaning tasdiqlangan qoidalari hamda tomonlar kelishuvi asosida amalga oshiriladi."),
        ]
        for title, body in clauses:
            out.append(Spacer(1, 4 * mm)); out.append(Paragraph(f"<b>{title}</b>", s["normal"])); out.append(Paragraph(body, s["normal"]))
        out.append(PageBreak())
        out.append(Paragraph("TOMONLARNING REKVIZITLARI", s["title"]))
        _details(out, [("Tashkilot", kg.legal_name or kg.name), ("STIR", kg.inn),
                       ("Bank", kg.bank_name), ("Hisob raqami", kg.bank_account),
                       ("MFO", kg.bank_mfo), ("Manzil", kg.address), ("Telefon", kg.phone)], s)
        _signatures(out, kg, s, payer.full_name if payer else "Qonuniy vakil")
        return out
    return _build("Xizmat shartnomasi", number, kg, story)


def debt_statement_pdf(kg, child, invoices, as_of):
    number = f"QD-{as_of:%Y%m%d}-{str(child.id)[:8].upper()}"
    rows = [(i.number, i.period.strftime("%m.%Y"), i.due_at.strftime("%d.%m.%Y"),
             _money(i.total_amount), _money(i.paid_amount), _money(i.total_amount - i.paid_amount))
            for i in invoices]
    total = sum((i.total_amount - i.paid_amount for i in invoices), 0)
    def story(s):
        out = []
        _header(out, kg, "QARZDORLIK BO'YICHA SOLISHTIRMA DALOLATNOMA", number, s)
        _details(out, [("Bola", child.full_name), ("Bola ID", child.code),
                       ("Holat sanasi", as_of.strftime("%d.%m.%Y")),
                       ("Ochiq invoyslar", str(len(rows))), ("Jami qarz", _money(total))], s)
        out.append(Spacer(1, 6 * mm))
        _items(out, ["Invoys", "Davr", "Muddat", "Hisob", "To'lov", "Qoldiq"], rows,
               [35 * mm, 22 * mm, 27 * mm, 30 * mm, 28 * mm, 28 * mm], s)
        out.append(Spacer(1, 5 * mm))
        out.append(Paragraph(f"Mazkur dalolatnoma {as_of:%d.%m.%Y} holatiga tizimdagi hisob-kitoblar asosida tuzildi.", s["normal"]))
        _signatures(out, kg, s)
        return out
    return _build("Qarzdorlik dalolatnomasi", number, kg, story)
