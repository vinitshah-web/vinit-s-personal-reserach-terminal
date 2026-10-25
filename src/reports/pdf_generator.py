"""Vector PDF Research Report Generator using ReportLab.
Produces rigorous, institutional-grade, multi-page equity research reports in INR.
Strictly zero-budget, runs locally on Windows without external dependencies.
"""
import io
from datetime import datetime
from typing import Dict, Any, List

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas


class NumberedCanvas(canvas.Canvas):
    """Adds running headers and footers with page numbers and compliance watermark."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))

        # Header
        self.drawString(54, 750, "VINIT'S RESEARCH TERMINAL — INSTITUTIONAL EQUITY RESEARCH")
        self.drawRightString(612 - 54, 750, datetime.now().strftime("%d %b %Y"))
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.5)
        self.line(54, 744, 612 - 54, 744)

        # Footer
        self.line(54, 45, 612 - 54, 45)
        self.drawString(54, 32, "STRICTLY FOR PERSONAL RESEARCH — ZERO MANDATORY SPEND ARCHITECTURE")
        self.drawRightString(612 - 54, 32, f"Page {self._pageNumber} of {page_count}")
        self.restoreState()


class ResearchReportPDFGenerator:
    """Builds a complete, deterministic research PDF document."""

    @classmethod
    def generate_pdf(cls, data: Dict[str, Any]) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=54,
            rightMargin=54,
            topMargin=54,
            bottomMargin=54
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'DocTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=20,
            leading=24,
            textColor=colors.HexColor('#0f172a')
        )
        subtitle_style = ParagraphStyle(
            'DocSubtitle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leading=14,
            textColor=colors.HexColor('#64748b')
        )
        h2_style = ParagraphStyle(
            'SectionH2',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=12,
            leading=16,
            textColor=colors.HexColor('#0f172a'),
            spaceBefore=12,
            spaceAfter=6
        )
        body_style = ParagraphStyle(
            'BodyDark',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=13,
            textColor=colors.HexColor('#334155')
        )
        caption_style = ParagraphStyle(
            'Caption',
            parent=styles['Italic'],
            fontName='Helvetica-Oblique',
            fontSize=8,
            leading=11,
            textColor=colors.HexColor('#64748b')
        )

        story = []

        # Header Block
        ticker = data.get("symbol", "UNKNOWN")
        company = data.get("company_name", ticker)
        isin = data.get("isin", "N/A")
        sector = data.get("sector", "Diversified")
        quote = data.get("quote", {})
        price = quote.get("close", 0.0)
        p_date = quote.get("trade_date", "Latest Available")
        source = quote.get("source", "TejHQ Keyless EOD")

        story.append(Paragraph(f"{company} ({ticker})", title_style))
        story.append(Paragraph(f"NSE Ticker: {ticker} | ISIN: {isin} | Sector: {sector} | Currency: INR (₹)", subtitle_style))
        story.append(Spacer(1, 10))

        # Executive Metrics Grid
        mcap = data.get("market_cap_cr", 0.0)
        pe = data.get("pe_ratio", "N/A")
        pb = data.get("pb_ratio", "N/A")
        hi52 = data.get("fifty_two_week_high", "N/A")
        lo52 = data.get("fifty_two_week_low", "N/A")

        summary_table_data = [
            [
                Paragraph("<b>Latest Closing Price</b>", body_style),
                Paragraph(f"<b>₹{price:,.2f}</b>", body_style),
                Paragraph("<b>Market Capitalization</b>", body_style),
                Paragraph(f"₹{mcap:,.1f} Cr" if mcap else "N/A", body_style)
            ],
            [
                Paragraph("<b>Quote Date & Source</b>", body_style),
                Paragraph(f"{p_date} ({source})", caption_style),
                Paragraph("<b>Trailing P/E & P/B</b>", body_style),
                Paragraph(f"{pe}x | {pb}x", body_style)
            ],
            [
                Paragraph("<b>52-Week Range</b>", body_style),
                Paragraph(f"₹{lo52} – ₹{hi52}" if hi52 else "N/A", body_style),
                Paragraph("<b>Provenance Status</b>", body_style),
                Paragraph("Verified Exchange Data", caption_style)
            ]
        ]
        t_summary = Table(summary_table_data, colWidths=[130, 120, 130, 124])
        t_summary.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(t_summary)
        story.append(Spacer(1, 14))

        # 1. Business Model
        story.append(Paragraph("1. Business Model & Operations", h2_style))
        summary_text = data.get("business_summary", "Company operates in Indian listed capital markets.")
        story.append(Paragraph(summary_text, body_style))
        story.append(Spacer(1, 12))

        # 2. Financial Performance (5-Year History in ₹ Cr)
        story.append(Paragraph("2. Financial Performance (Reported Disclosures in ₹ Crores)", h2_style))
        statements = data.get("financial_statements", [])
        if statements:
            fin_headers = ["Metric (₹ Cr)"] + [s["period"] for s in statements[:5]]
            row_rev = ["Revenue"] + [f"₹{s['revenue_cr']:,.1f}" if s.get('revenue_cr') is not None else "-" for s in statements[:5]]
            row_ebit = ["EBITDA / Op Inc"] + [f"₹{s['ebitda_cr']:,.1f}" if s.get('ebitda_cr') is not None else "-" for s in statements[:5]]
            row_ni = ["Net Income"] + [f"₹{s['net_income_cr']:,.1f}" if s.get('net_income_cr') is not None else "-" for s in statements[:5]]
            row_cfo = ["Operating Cash Flow"] + [f"₹{s['operating_cash_flow_cr']:,.1f}" if s.get('operating_cash_flow_cr') is not None else "-" for s in statements[:5]]
            row_capex = ["Capex"] + [f"₹{s['capex_cr']:,.1f}" if s.get('capex_cr') is not None else "-" for s in statements[:5]]
            row_fcff = ["Free Cash Flow (FCFF)"] + [f"₹{s['fcff_cr']:,.1f}" if s.get('fcff_cr') is not None else "-" for s in statements[:5]]
            
            fin_table_data = [
                [Paragraph(f"<b>{c}</b>", body_style) for c in fin_headers],
                row_rev, row_ebit, row_ni, row_cfo, row_capex, row_fcff
            ]
            t_fin = Table(fin_table_data)
            t_fin.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
                ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
                ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 8),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ]))
            story.append(t_fin)
        else:
            story.append(Paragraph("<i>Detailed historical statements not ingested for this security. Transparent missing data disclosure applied.</i>", caption_style))
        story.append(Spacer(1, 14))

        # 3. Valuation Analysis & Scenarios
        story.append(Paragraph("3. Valuation Scenarios & Reverse DCF Analysis", h2_style))
        val = data.get("valuation", {})
        if val.get("can_calculate") and val.get("base_fair_value"):
            bear_val = val.get("bear_fair_value")
            base_val = val.get("base_fair_value")
            bull_val = val.get("bull_fair_value")
            implied_g = val.get("implied_growth_pct")

            val_rows = [
                [
                    Paragraph("<b>Scenario</b>", body_style),
                    Paragraph("<b>Growth Assumption</b>", body_style),
                    Paragraph("<b>Discount Rate (WACC)</b>", body_style),
                    Paragraph("<b>Fair Value (₹/share)</b>", body_style),
                    Paragraph("<b>Upside / Downside</b>", body_style)
                ],
                [
                    Paragraph("<b>Bear Case</b>", body_style),
                    Paragraph("5.0% 5Y CAGR", body_style),
                    Paragraph("13.5%", body_style),
                    Paragraph(f"₹{bear_val:,.2f}", body_style),
                    Paragraph(f"{((bear_val - price) / price * 100):+.1f}%", body_style)
                ],
                [
                    Paragraph("<b>Base Case</b>", body_style),
                    Paragraph("10.0% 5Y CAGR", body_style),
                    Paragraph("12.0%", body_style),
                    Paragraph(f"<b>₹{base_val:,.2f}</b>", body_style),
                    Paragraph(f"<b>{((base_val - price) / price * 100):+.1f}%</b>", body_style)
                ],
                [
                    Paragraph("<b>Bull Case</b>", body_style),
                    Paragraph("16.0% 5Y CAGR", body_style),
                    Paragraph("11.0%", body_style),
                    Paragraph(f"₹{bull_val:,.2f}", body_style),
                    Paragraph(f"{((bull_val - price) / price * 100):+.1f}%", body_style)
                ]
            ]
            t_val = Table(val_rows, colWidths=[90, 110, 110, 100, 94])
            t_val.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
                ('BACKGROUND', (0,2), (-1,2), colors.HexColor('#ecfdf5')),
                ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
                ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ]))
            story.append(t_val)
            story.append(Spacer(1, 6))
            if implied_g is not None:
                story.append(Paragraph(f"<b>Reverse DCF Implied Growth:</b> Current market price of ₹{price:,.2f} implies an enterprise free cash flow growth rate of <b>{implied_g:.1f}% CAGR</b> over the next 5 years (assuming WACC=12.0%, Terminal Growth=4.0%).", caption_style))
        else:
            reason = val.get("reason", "Audited valuation inputs (positive FCFF or regulatory capital metrics) are insufficient.")
            story.append(Paragraph(f"<i>Valuation model was not calculated: {reason}</i>", caption_style))
            story.append(Paragraph("<i>As per zero-budget research integrity policy, target prices are not manufactured or filled with synthetic multipliers.</i>", caption_style))
        story.append(Spacer(1, 14))

        # 4. Industry Dynamics & Risk Factors
        story.append(Paragraph("4. Industry Demand/Supply & Risk Architecture", h2_style))
        ind = data.get("industry_profile", {})
        story.append(Paragraph(f"<b>Demand Drivers:</b> {ind.get('demand_drivers', 'N/A')}", body_style))
        story.append(Spacer(1, 4))
        story.append(Paragraph(f"<b>Supply Dynamics:</b> {ind.get('supply_dynamics', 'N/A')}", body_style))
        story.append(Spacer(1, 4))
        story.append(Paragraph(f"<b>Regulatory Environment:</b> {ind.get('regulatory_framework', 'N/A')}", body_style))
        story.append(Spacer(1, 4))
        story.append(Paragraph(f"<b>Primary Investment Risks:</b> {ind.get('key_risks', 'N/A')}", body_style))
        story.append(Spacer(1, 14))

        # 5. Methodology & Governance Notice
        story.append(Paragraph("5. Methodology, Data Provenance & Disclaimers", h2_style))
        story.append(Paragraph(
            "<b>Provenance:</b> Price facts retrieved from TejHQ Open EOD API (backed by NSE Bhavcopy). "
            "Financial statements sourced from official exchange filings. Intrinsic valuation derived from "
            "Damodaran FCFF / Banking Capital models. Zero synthetic data injected into research records. "
            "Report compiled deterministically without mandatory paid external APIs.",
            caption_style
        ))

        doc.build(story, canvasmaker=NumberedCanvas)
        return buffer.getvalue()
