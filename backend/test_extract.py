from app.services.extraction_service import extract_text_from_pdf
from reportlab.pdfgen import canvas

# Generate a dummy pdf
c = canvas.Canvas("dummy.pdf")
c.drawString(100, 750, "Hello World from PDF")
c.save()

print("Extracted:", repr(extract_text_from_pdf("dummy.pdf")))
