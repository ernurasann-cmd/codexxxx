from io import BytesIO
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from .models import Assignment


def build_assignment_pdf(assignment: Assignment, conclusion_text: Optional[str] = None) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("<b>Отчёт по профориентационному тесту</b>", styles["Title"]))
    story.append(Spacer(1, 24))
    story.append(Paragraph(f"Клиент: {assignment.client.full_name}", styles["Normal"]))
    story.append(Paragraph(f"Профориентолог: {assignment.professional.full_name}", styles["Normal"]))
    story.append(Paragraph(f"Тест: {assignment.assessment.title}", styles["Normal"]))
    story.append(Paragraph(f"Статус: {assignment.status.value}", styles["Normal"]))

    if assignment.result:
        story.append(Spacer(1, 12))
        story.append(Paragraph("<b>Результаты</b>", styles["Heading2"]))
        story.append(Paragraph(assignment.result.summary or "", styles["Normal"]))

    if conclusion_text:
        story.append(Spacer(1, 12))
        story.append(Paragraph("<b>Заключение профориентолога</b>", styles["Heading2"]))
        story.append(Paragraph(conclusion_text, styles["Normal"]))

    doc.build(story)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf
