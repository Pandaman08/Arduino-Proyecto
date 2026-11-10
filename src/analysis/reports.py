"""Exportadores deterministas para la interfaz y el informe universitario."""

from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Iterable

import pandas as pd


def dataframe_csv(data: Iterable[dict[str, Any]] | pd.DataFrame) -> bytes:
    frame = data if isinstance(data, pd.DataFrame) else pd.DataFrame(list(data))
    return frame.to_csv(index=False).encode("utf-8")


def dataframe_excel(data: Iterable[dict[str, Any]] | pd.DataFrame, sheet_name: str = "resumen") -> bytes:
    frame = data if isinstance(data, pd.DataFrame) else pd.DataFrame(list(data))
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False, sheet_name=sheet_name[:31])
    return buffer.getvalue()


def comparison_pdf(title: str, summary: pd.DataFrame, statistics: pd.DataFrame, grain_type: str, origin: str) -> bytes:
    """Genera un PDF textual; no agrega resultados que no existan."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.5 * cm, leftMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    story = [Paragraph(title, styles["Title"]), Paragraph(f"Grano: {grain_type} · Origen: {origin} · Generado: {datetime.now(timezone.utc).isoformat()}", styles["Normal"]), Spacer(1, 0.4 * cm)]
    for label, frame in (("Resumen de indicadores", summary), ("Pruebas estadísticas", statistics)):
        story.append(Paragraph(label, styles["Heading2"]))
        values = [list(frame.columns)] + frame.fillna("No disponible").astype(str).values.tolist() if not frame.empty else [["No disponible"]]
        table = Table(values, repeatRows=1)
        table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d3b66")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 7)]))
        story.extend([table, Spacer(1, 0.3 * cm)])
    story.append(Paragraph("Limitación: los resultados simulados no constituyen evidencia experimental real. La interpretación debe considerar tamaño muestral, diseño y calidad de medición.", styles["Normal"]))
    document.build(story)
    return buffer.getvalue()


def line_chart_png(frame: pd.DataFrame, title: str) -> bytes:
    """Exporta un gráfico simple; la visualización principal sigue siendo Streamlit."""
    import matplotlib.pyplot as plt

    buffer = BytesIO()
    figure, axis = plt.subplots(figsize=(9, 4.5))
    frame.plot(ax=axis)
    axis.set_title(title)
    axis.set_xlabel("Tiempo")
    axis.grid(True, alpha=0.25)
    figure.tight_layout()
    figure.savefig(buffer, format="png", dpi=150)
    plt.close(figure)
    return buffer.getvalue()
