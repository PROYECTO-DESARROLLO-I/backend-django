from io import BytesIO
from datetime import date
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer
)
from reportlab.lib.styles import getSampleStyleSheet


def generate_appointments_pdf(appointments_data, filters_applied):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm,
    )

    styles = getSampleStyleSheet()
    elements = []

    # Título
    elements.append(Paragraph("SaludAgendaX — Reporte de Citas", styles['Title']))
    elements.append(Paragraph(f"Generado: {date.today()}", styles['Normal']))
    elements.append(Spacer(1, 0.5*cm))

    # Filtros aplicados
    if filters_applied:
        elements.append(Paragraph("Filtros aplicados:", styles['Heading3']))
        for k, v in filters_applied.items():
            if v:
                elements.append(Paragraph(f"  • {k}: {v}", styles['Normal']))
        elements.append(Spacer(1, 0.5*cm))

    # Tabla
    headers = ['#', 'Paciente', 'Documento', 'Médico', 'Especialidad', 'Fecha/Hora', 'Estado']
    rows = [headers]

    for i, appt in enumerate(appointments_data, 1):
        rows.append([
            str(i),
            appt.get('patient_name', ''),
            appt.get('patient_document', ''),
            appt.get('doctor_name', ''),
            appt.get('specialty_name', ''),
            str(appt.get('scheduled_at', ''))[:16],
            appt.get('status', '').upper(),
        ])

    table = Table(rows, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')),
        ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, 0), 9),
        ('FONTSIZE',   (0, 1), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#EFF6FF')]),
        ('GRID',       (0, 0), (-1, -1), 0.4, colors.HexColor('#CBD5E1')),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING',    (0, 0), (-1, -1), 6),
    ]))

    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return buffer