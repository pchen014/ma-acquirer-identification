import os
from pathlib import Path
from typing import List
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from src.schemas import AcquirerRationale, TargetProfile
from src.config import REPORTS_DIR

def generate_acquirer_pdf(
    recommendations: List[AcquirerRationale],
    target: TargetProfile,
    report_id: str,
    output_path: str = ""
) -> str:
    """
    Compiles an MD-ready investment banking pitch book PDF formatted as:
    Strictly 1 page per acquirer rationale.
    """
    if not output_path:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = str(REPORTS_DIR / f"{report_id}.pdf")
    else:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Margins: 0.4 inches (28.8 pt) to fit rich 1-page layout
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=32,
        rightMargin=32,
        topMargin=28,
        bottomMargin=28
    )

    styles = getSampleStyleSheet()

    # Custom Banking Typography & Colors
    PRIMARY = colors.HexColor("#0F172A")    # Deep Navy
    SECONDARY = colors.HexColor("#334155")  # Slate Gray
    ACCENT_BLUE = colors.HexColor("#1D4ED8")# Royal Blue
    BORDER_COLOR = colors.HexColor("#CBD5E1")
    BG_LIGHT = colors.HexColor("#F8FAFC")
    BG_CARD = colors.HexColor("#F1F5F9")
    
    # Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=PRIMARY
    )
    
    section_h2 = ParagraphStyle(
        'SectionH2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=ACCENT_BLUE,
        spaceAfter=2
    )

    body_text = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=SECONDARY,
        spaceAfter=4
    )

    badge_high = ParagraphStyle(
        'BadgeHigh',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#065F46"),
        alignment=1
    )
    
    badge_med = ParagraphStyle(
        'BadgeMed',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#92400E"),
        alignment=1
    )
    
    badge_low = ParagraphStyle(
        'BadgeLow',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#475569"),
        alignment=1
    )

    story = []

    # Build 1 page for each acquirer
    for idx, rec in enumerate(recommendations):
        page_elements = []

        # 1. Header Banner Table
        badge_style = badge_high if rec.conviction_level == "High" else (badge_med if rec.conviction_level == "Medium" else badge_low)
        badge_bg = colors.HexColor("#D1FAE5") if rec.conviction_level == "High" else (colors.HexColor("#FEF3C7") if rec.conviction_level == "Medium" else colors.HexColor("#E2E8F0"))

        score_str = f"Match: {rec.composite_score * 100:.1f}%" if rec.composite_score > 0 else ""
        score_badge = f"<font size=8 color='#1D4ED8'><b>[{score_str}]</b></font> " if score_str else ""
        header_left = Paragraph(
            f"<b>#{idx + 1} {rec.acquirer_name}</b> {score_badge}<font size=8 color='#64748B'>| {rec.acquirer_type}</font>",
            title_style
        )
        badge_text = Paragraph(f"<b>{rec.conviction_level.upper()} CONVICTION</b>", badge_style)
        
        target_info = Paragraph(
            f"<font size=7 color='#64748B'>TARGET: ${target.deal_size_mm:,.0f}M EV • {target.sector} • {target.geography} • {target.ebitda_margin_pct:.0f}% EBITDA</font>",
            body_text
        )

        header_table = Table(
            [
                [header_left, badge_text],
                [target_info, ""]
            ],
            colWidths=[420, 128]
        )
        header_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN', (1,0), (1,0), 'CENTER'),
            ('BACKGROUND', (1,0), (1,0), badge_bg),
            ('BOX', (1,0), (1,0), 0.5, colors.HexColor("#94A3B8")),
            ('TOPPADDING', (0,0), (-1,-1), 2),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ]))
        page_elements.append(header_table)
        page_elements.append(HRFlowable(width="100%", thickness=1, color=PRIMARY, spaceBefore=4, spaceAfter=6))

        # 2. Section 1: Acquirer Overview
        page_elements.append(Paragraph("1. ACQUIRER OVERVIEW & TRANSACTION FOOTPRINT", section_h2))
        page_elements.append(Paragraph(rec.acquirer_overview, body_text))
        page_elements.append(Spacer(1, 4))

        # 3. Section 2: Strategic Fit Thesis
        page_elements.append(Paragraph("2. STRATEGIC FIT THESIS", section_h2))
        page_elements.append(Paragraph(rec.strategic_fit_thesis, body_text))
        page_elements.append(Spacer(1, 4))

        # 4. Section 3: Precedent Activity
        page_elements.append(Paragraph("3. VERIFIED PRECEDENT ACTIVITY & COMPARABLE TRANSACTIONS", section_h2))
        page_elements.append(Paragraph(rec.precedent_activity, body_text))
        page_elements.append(Spacer(1, 4))

        # 5. Section 4: Valuation Context
        page_elements.append(Paragraph("4. VALUATION CONTEXT & PRICING DISCIPLINE", section_h2))
        page_elements.append(Paragraph(rec.valuation_context, body_text))
        page_elements.append(Spacer(1, 4))

        # 6. Section 5: Risk Flags
        page_elements.append(Paragraph("5. KEY DEAL EXECUTION & TRANSACTION RISKS", section_h2))
        risk_bullets = "".join([f"• <b>Risk {r_idx+1}:</b> {risk}<br/>" for r_idx, risk in enumerate(rec.risk_flags)])
        risk_table = Table([[Paragraph(risk_bullets, body_text)]], colWidths=[548])
        risk_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#FEF2F2")),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#FECACA")),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ]))
        page_elements.append(risk_table)
        page_elements.append(Spacer(1, 5))

        # 7. Section 6: Conviction Level
        page_elements.append(Paragraph("6. CONVICTION RATIONALE", section_h2))
        conviction_box = Table([[
            Paragraph(f"<b>{rec.conviction_level} Conviction Verdict:</b> {rec.conviction_rationale}", body_text)
        ]], colWidths=[548])
        conviction_box.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), BG_CARD),
            ('BOX', (0,0), (-1,-1), 0.5, BORDER_COLOR),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ]))
        page_elements.append(conviction_box)
        page_elements.append(Spacer(1, 6))

        # 8. Page Footer
        footer_p = Paragraph(
            f"<font size=6 color='#94A3B8'>CONFIDENTIAL M&A ADVISORY MEMO • PAGE {idx + 1} OF {len(recommendations)} • GENERATED FOR CLIENT PRESENTATION</font>",
            ParagraphStyle('Footer', parent=styles['Normal'], alignment=1)
        )
        page_elements.append(footer_p)

        story.extend(page_elements)

        # Break page after each acquirer except the last
        if idx < len(recommendations) - 1:
            story.append(PageBreak())

    doc.build(story)
    return output_path
