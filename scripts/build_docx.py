"""
SoilSentinel - OpenXML (.docx) Document Generator
Builds a native Microsoft Word .docx file adhering to Open Packaging Conventions (OPC)
using only Python standard library (zipfile, xml.sax.saxutils, etc.).
"""

import os
import sys
import zipfile
import datetime
from xml.sax.saxutils import escape

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "project_documentation")
DOCX_PATH = os.path.join(OUTPUT_DIR, "SOILSENTINEL_COMPLETE_PROJECT_DOCUMENTATION.docx")

CONTENT_TYPES_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>"""

RELS_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""

WORD_RELS_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

CORE_XML = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>SoilSentinel - Complete Project Documentation</dc:title>
  <dc:subject>IBM Z Datathon 2026 Engineering Architecture</dc:subject>
  <dc:creator>SoilSentinel Engineering Team</dc:creator>
  <cp:keywords>Soil Health, Machine Learning, SHAP, Sentinel-2, Agro-climatic Assessment</cp:keywords>
  <dc:description>Comprehensive technical and operational architecture documentation for SoilSentinel.</dc:description>
  <dcterms:created xsi:type="dcterms:W3CDTF">2026-10-17T12:00:00Z</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">2026-10-17T12:00:00Z</dcterms:modified>
</cp:coreProperties>"""

APP_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Template>Normal.dotm</Template>
  <TotalTime>120</TotalTime>
  <Pages>22</Pages>
  <Words>6500</Words>
  <Characters>42000</Characters>
  <Application>SoilSentinel Document Engine</Application>
  <DocSecurity>0</DocSecurity>
  <Lines>450</Lines>
  <Paragraphs>220</Paragraphs>
  <ScaleCrop>false</ScaleCrop>
  <Company>IBM Z Datathon 2026</Company>
  <LinksUpToDate>false</LinksUpToDate>
  <CharactersWithSpaces>48500</CharactersWithSpaces>
  <SharedDoc>false</SharedDoc>
  <HyperlinksChanged>false</HyperlinksChanged>
  <AppVersion>16.0000</AppVersion>
</Properties>"""

STYLES_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault>
      <w:rPr>
        <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri"/>
        <w:sz w:val="22"/>
        <w:szCs w:val="22"/>
        <w:color w:val="222222"/>
      </w:rPr>
    </w:rPrDefault>
    <w:pPrDefault>
      <w:pPr>
        <w:spacing w:after="160" w:line="260" w:lineRule="auto"/>
      </w:pPr>
    </w:pPrDefault>
  </w:docDefaults>
  
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:qFormat/>
  </w:style>

  <w:style w:type="paragraph" w:styleId="Title">
    <w:name w:val="Title"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
    <w:pPr>
      <w:spacing w:before="360" w:after="160"/>
      <w:jc w:val="center"/>
    </w:pPr>
    <w:rPr>
      <w:rFonts w:ascii="Segoe UI" w:hAnsi="Segoe UI"/>
      <w:b/>
      <w:sz w:val="52"/>
      <w:szCs w:val="52"/>
      <w:color w:val="1B365D"/>
    </w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="Subtitle">
    <w:name w:val="Subtitle"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
    <w:pPr>
      <w:spacing w:before="0" w:after="300"/>
      <w:jc w:val="center"/>
    </w:pPr>
    <w:rPr>
      <w:rFonts w:ascii="Segoe UI" w:hAnsi="Segoe UI"/>
      <w:sz w:val="26"/>
      <w:szCs w:val="26"/>
      <w:color w:val="4A777A"/>
    </w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:qFormat/>
    <w:pPr>
      <w:spacing w:before="360" w:after="160"/>
    </w:pPr>
    <w:rPr>
      <w:rFonts w:ascii="Segoe UI" w:hAnsi="Segoe UI"/>
      <w:b/>
      <w:sz w:val="36"/>
      <w:szCs w:val="36"/>
      <w:color w:val="1B365D"/>
    </w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:qFormat/>
    <w:pPr>
      <w:spacing w:before="260" w:after="120"/>
    </w:pPr>
    <w:rPr>
      <w:rFonts w:ascii="Segoe UI" w:hAnsi="Segoe UI"/>
      <w:b/>
      <w:sz w:val="28"/>
      <w:szCs w:val="28"/>
      <w:color w:val="2B547E"/>
    </w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="Heading3">
    <w:name w:val="heading 3"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:qFormat/>
    <w:pPr>
      <w:spacing w:before="180" w:after="80"/>
    </w:pPr>
    <w:rPr>
      <w:rFonts w:ascii="Segoe UI" w:hAnsi="Segoe UI"/>
      <w:b/>
      <w:sz w:val="24"/>
      <w:szCs w:val="24"/>
      <w:color w:val="36648B"/>
    </w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="ListBullet">
    <w:name w:val="List Bullet"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
    <w:pPr>
      <w:spacing w:before="40" w:after="60"/>
      <w:ind w:left="480" w:hanging="240"/>
    </w:pPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="CodeBlock">
    <w:name w:val="Code Block"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr>
      <w:spacing w:before="100" w:after="100" w:line="220" w:lineRule="auto"/>
      <w:shd w:val="clear" w:color="auto" w:fill="F5F5F7"/>
      <w:ind w:left="360" w:right="360"/>
    </w:pPr>
    <w:rPr>
      <w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/>
      <w:sz w:val="19"/>
      <w:szCs w:val="19"/>
      <w:color w:val="2A2A2A"/>
    </w:rPr>
  </w:style>
  
  <w:style w:type="paragraph" w:styleId="Callout">
    <w:name w:val="Callout"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr>
      <w:spacing w:before="140" w:after="140"/>
      <w:shd w:val="clear" w:color="auto" w:fill="EEF3F8"/>
      <w:ind w:left="360" w:right="360"/>
      <w:pBdr>
        <w:left w:val="single" w:sz="24" w:space="12" w:color="1B365D"/>
      </w:pBdr>
    </w:pPr>
    <w:rPr>
      <w:color w:val="1B365D"/>
    </w:rPr>
  </w:style>
</w:styles>"""

class DocxBuilder:
    def __init__(self):
        self.paragraphs = []

    def p(self, text="", style="Normal", bold=False, italic=False, color=None):
        runs = []
        if text:
            rPr = []
            if bold:
                rPr.append("<w:b/>")
            if italic:
                rPr.append("<w:i/>")
            if color:
                rPr.append(f'<w:color w:val="{color}"/>')
            rPr_str = f"<w:rPr>{''.join(rPr)}</w:rPr>" if rPr else ""
            escaped = escape(text)
            runs.append(f"<w:r>{rPr_str}<w:t xml:space=\"preserve\">{escaped}</w:t></w:r>")
        pPr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>'
        self.paragraphs.append(f"<w:p>{pPr}{''.join(runs)}</w:p>")

    def heading(self, text, level=1):
        style = f"Heading{level}"
        self.p(text, style=style)

    def bullet(self, text, bold_prefix=None):
        pPr = '<w:pPr><w:pStyle w:val="ListBullet"/></w:pPr>'
        bullet_run = '<w:r><w:rPr><w:rFonts w:ascii="Symbol" w:hAnsi="Symbol"/><w:color w:val="1B365D"/></w:rPr><w:t>• </w:t></w:r>'
        runs = [bullet_run]
        if bold_prefix:
            runs.append(f'<w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">{escape(bold_prefix)} </w:t></w:r>')
        runs.append(f'<w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r>')
        self.paragraphs.append(f"<w:p>{pPr}{''.join(runs)}</w:p>")

    def callout(self, text, prefix="IMPORTANT: "):
        pPr = '<w:pPr><w:pStyle w:val="Callout"/></w:pPr>'
        runs = []
        if prefix:
            runs.append(f'<w:r><w:rPr><w:b/><w:color w:val="1B365D"/></w:rPr><w:t xml:space="preserve">{escape(prefix)}</w:t></w:r>')
        runs.append(f'<w:r><w:rPr><w:color w:val="222222"/></w:rPr><w:t xml:space="preserve">{escape(text)}</w:t></w:r>')
        self.paragraphs.append(f"<w:p>{pPr}{''.join(runs)}</w:p>")

    def code(self, text):
        lines = text.strip().split("\n")
        for line in lines:
            self.p(line, style="CodeBlock")

    def page_break(self):
        self.paragraphs.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')

    def table(self, headers, rows, col_widths=None):
        tbl_pr = """<w:tblPr>
          <w:tblStyle w:val="TableGrid"/>
          <w:tblW w:w="0" w:type="auto"/>
          <w:tblBorders>
            <w:top w:val="single" w:sz="6" w:space="0" w:color="D0D7DE"/>
            <w:left w:val="none"/>
            <w:bottom w:val="single" w:sz="6" w:space="0" w:color="D0D7DE"/>
            <w:right w:val="none"/>
            <w:insideH w:val="single" w:sz="4" w:space="0" w:color="EAECEF"/>
            <w:insideV w:val="none"/>
          </w:tblBorders>
          <w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstCol="0" w:lastCol="0" w:noHBand="0" w:noVBand="1"/>
        </w:tblPr>"""
        
        xml_rows = []
        # Header Row
        header_cells = []
        for i, h in enumerate(headers):
            w_str = f'<w:tcW w:w="{col_widths[i]}" w:type="dxa"/>' if col_widths and i < len(col_widths) else '<w:tcW w:w="0" w:type="auto"/>'
            cell = f"""<w:tc>
              <w:tcPr>
                {w_str}
                <w:shd w:val="clear" w:color="auto" w:fill="F0F4F8"/>
                <w:tcMar><w:top w:w="120"/><w:bottom w:w="120"/><w:left w:w="160"/><w:right w:w="160"/></w:tcMar>
              </w:tcPr>
              <w:p><w:pPr><w:spacing w:before="60" w:after="60"/></w:pPr><w:r><w:rPr><w:b/><w:color w:val="1B365D"/><w:sz w:val="20"/></w:rPr><w:t>{escape(str(h))}</w:t></w:r></w:p>
            </w:tc>"""
            header_cells.append(cell)
        xml_rows.append(f"<w:tr><w:trPr><w:tblHeader/></w:trPr>{''.join(header_cells)}</w:tr>")

        # Data Rows
        for r_idx, row in enumerate(rows):
            cells = []
            bg = "FFFFFF" if r_idx % 2 == 0 else "F9FBFD"
            for i, val in enumerate(row):
                w_str = f'<w:tcW w:w="{col_widths[i]}" w:type="dxa"/>' if col_widths and i < len(col_widths) else '<w:tcW w:w="0" w:type="auto"/>'
                cell = f"""<w:tc>
                  <w:tcPr>
                    {w_str}
                    <w:shd w:val="clear" w:color="auto" w:fill="{bg}"/>
                    <w:tcMar><w:top w:w="100"/><w:bottom w:w="100"/><w:left w:w="160"/><w:right w:w="160"/></w:tcMar>
                  </w:tcPr>
                  <w:p><w:pPr><w:spacing w:before="40" w:after="40"/></w:pPr><w:r><w:rPr><w:sz w:val="20"/></w:rPr><w:t>{escape(str(val))}</w:t></w:r></w:p>
                </w:tc>"""
                cells.append(cell)
            xml_rows.append(f"<w:tr>{''.join(cells)}</w:tr>")

        self.paragraphs.append(f"<w:tbl>{tbl_pr}{''.join(xml_rows)}</w:tbl><w:p><w:pPr><w:spacing w:before=\"100\" w:after=\"100\"/></w:pPr></w:p>")

    def build_xml(self):
        body = "".join(self.paragraphs)
        sect_pr = """<w:sectPr>
          <w:pgSz w:w="12240" w:h="15840"/>
          <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/>
        </w:sectPr>"""
        return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
            xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">
  <w:body>
    {body}
    {sect_pr}
  </w:body>
</w:document>"""

def generate_document():
    doc = DocxBuilder()
    
    # Title Page
    doc.p("SoilSentinel", style="Title")
    doc.p("Complete System Architecture, Algorithmic Auditing, Scientific Integrity, and Production Roadmap", style="Subtitle")
    doc.p("IBM Z Datathon 2026 Engineering Deliverable", bold=True, color="1B365D")
    doc.p("Date: October 17, 2026 | Location: Chandigarh / Punjab Basin (30.7300° N, 76.7700° E)")
    doc.p()

    meta_headers = ["Project Metadata Field", "Current Value / Specification"]
    meta_rows = [
        ["Project Title", "SoilSentinel — Agro-Climatic Soil Degradation Intelligence"],
        ["Target Hackathon", "IBM Z Datathon 2026"],
        ["Version & State", "v1.2.0-surrogate-audit (Surrogate Verified, Physical Validation Pending)"],
        ["Runtime Stack", "Python 3.10+ / Node.js 22 LTS / SQLite 3.49+ / Copernicus Sentinel-2 L2A"],
        ["Core Models", "Heuristic SDI Engine & Random Forest Surrogate (14 Features, 91.67% Acc)"],
        ["Explainability", "TreeSHAP Local Mathematical Additivity Verified (sum phi_i = f(x) - E[f(x)])"],
        ["Verified Test Suite", "211 Tests Passing (200 core engine + 11 satellite tests)"],
        ["Live Listening Ports", "Gateway: http://localhost:3000 | Microservice: http://127.0.0.1:5001"]
    ]
    doc.table(meta_headers, meta_rows, [3500, 5800])
    
    doc.callout(
        "SCIENTIFIC INTEGRITY NOTICE: SoilSentinel calculates a domain-guided Soil Degradation Index (SDI) and "
        "evaluates a calibrated Random Forest surrogate. Physical in-situ soil core validation is currently "
        "PENDING FIELD DATA ACQUISITION. The platform distinguishes between surrogate statistical attribution "
        "and physical ground truth across all APIs and dashboards.",
        prefix="SCIENTIFIC INTEGRITY DIRECTIVE: "
    )
    doc.page_break()

    # Section 1
    doc.heading("1. Executive Summary & Problem Statement", level=1)
    doc.p(
        "Soil degradation affects over 40% of agricultural lands globally, threatening long-term food security, "
        "depleting soil organic carbon (SOC), inducing severe compaction hardpans, and triggering catastrophic topsoil erosion. "
        "In the intensely cultivated Indo-Gangetic Plain (Punjab/Haryana agricultural zone), intensive double-cropping, "
        "extreme summer thermal anomalies (T_max > 42°C), and irregular monsoonal precipitation accelerate soil desiccation and crusting."
    )
    doc.p(
        "SoilSentinel was developed for the IBM Z Datathon 2026 to dismantle the persistent information asymmetry between "
        "remote earth observation science and practical field agronomy. The platform integrates NASA POWER climate reanalysis, "
        "ISRIC SoilGrids pedological maps, and high-resolution ESA Copernicus Sentinel-2 L2A multispectral imagery into a unified, "
        "interpretable decision intelligence system."
    )

    # Section 2
    doc.heading("2. Target Personas, Real-World Use Cases & Value Proposition", level=1)
    doc.p("SoilSentinel serves four distinct user cohorts, providing tailored analytical depth for each:")
    doc.bullet("Smallholder Farmers: Need plain-language risk tiers, immediate action checklists, crop suitability warnings, and zero technical jargon.", bold_prefix="Farmer Persona:")
    doc.bullet("Agronomists & Extension Officers: Require limiting-factor breakdowns, counterfactual what-if scenario modeling, and crop threshold tuning.", bold_prefix="Agronomist Persona:")
    doc.bullet("Soil Researchers & Data Scientists: Inspect raw 14-feature arrays, surrogate confidence intervals, TreeSHAP attributions, and Sentinel-2 NDVI anomalies.", bold_prefix="Researcher Persona:")
    doc.bullet("Agricultural Policy Directors: Direct conservation subsidies, audit watershed recovery trajectories, and monitor longitudinal land health.", bold_prefix="Director Persona:")

    # Section 3
    doc.heading("3. User Journeys & Operational Modes (Farmer vs. Researcher)", level=1)
    doc.p(
        "SoilSentinel implements two completely separate, role-tailored dashboard views served from a single unified API pipeline:"
    )
    doc.heading("3.1 Farmer Mode Workflow", level=2)
    doc.bullet("Instant Assessment: Defaults to registered plot coordinates (30.7300° N, 76.7700° E) and latest monthly epoch (2024-12).")
    doc.bullet("High-Contrast SVG Gauge: Displays degradation risk tier (LOW, MODERATE, HIGH, CRITICAL) using intuitive color coding.")
    doc.bullet("Plain-Language Risk Banners: Translates mathematical metrics into contextual advice (e.g. 'Recent 90-day rainfall is 42% below normal').")
    doc.bullet("Crop Suitability Cards: Real-time traffic-light indicators for staple crops (Wheat, Rice, Maize, Chickpea, Mustard, Pearl Millet).")
    doc.bullet("Seasonal Action Plan: Step-by-step prioritized agronomic recommendations (mulching, reduced tillage, green manuring).")

    doc.heading("3.2 Researcher Mode Workflow", level=2)
    doc.bullet("60-Month Historical Timeline: Full chronological slider spanning January 2020 through December 2024.")
    doc.bullet("Dual Evaluation Telemetry: Real-time side-by-side comparison of Heuristic Score (47.87) vs. ML Surrogate Severity (44.89).")
    doc.bullet("TreeSHAP Waterfall Plot: Exact local feature attribution decomposing model outputs relative to baseline E[f(x)] = 45.98.")
    doc.bullet("Counterfactual 'What-If' Simulator: Interactive sliders for bulk density, organic carbon, pH, and precipitation with < 50ms re-scoring.")
    doc.bullet("Sentinel-2 Earth Observation: Visual false-color composites and cloud-cleared monthly NDVI trajectory.")

    # Section 4
    doc.heading("4. End-to-End System Architecture & Data Flow", level=1)
    doc.p(
        "The system employs a hardened 4-tier architecture designed for deterministic reproducibility, low latency, and enterprise security:"
    )
    doc.bullet("Tier 1: Presentation — Vanilla ES6+ JavaScript, CSS3 Glassmorphism tokens, and responsive SVG charts (farmer-dashboard.html, researcher-dashboard.html).")
    doc.bullet("Tier 2: Gateway & Auth — Node.js 22 LTS / Express 4.21 server (Port 3000), Helmet HTTP headers, express-rate-limit, session auth via SQLite 3.")
    doc.bullet("Tier 3: Analytics Bridge Daemon — Python 3.10+ Flask loopback service (Port 5001) pre-loading model artifacts into memory for < 85ms inference.")
    doc.bullet("Tier 4: Persistence & Data Assets — SQLite relational database (database/soilsentinel.db), 14-feature table (data/feature_table.csv), and processed Sentinel-2 assets.")

    # Section 5
    doc.heading("5. Technology Stack & Algorithmic Foundation", level=1)
    tech_headers = ["Technology / Component", "Repository Usage", "Architectural Purpose", "Trade-Offs & Boundaries"]
    tech_rows = [
        ["Python 3.10+", "src/, scripts/, tests/", "Scientific data processing, ML surrogate inference, SHAP math", "In-memory caching mitigates subprocess overhead"],
        ["scikit-learn", "src/models/, scripts/train_model.py", "RandomForestClassifier surrogate (100 trees, 91.67% accuracy)", "Surrogate tree ensemble bounds; does not extrapolate outside feature bounds"],
        ["TreeSHAP", "src/models/predict.py", "Game-theoretic local feature attributions (sum phi_i = f(x) - base)", "Statistical attribution against model surface; does NOT prove physical causality"],
        ["NASA POWER", "data/feature_table.csv", "60-month gap-free meteorology (T2M, PRECTOTCORR, WS2M, RH2M)", "Coarse spatial grid (~50km); captures regional trends but smooths micro-storms"],
        ["ISRIC SoilGrids", "data/raw/, src/config.py", "Global 250m pedometric predictions (SOC, bulk density, clay, pH, sand)", "Modeled estimates from covariates; static over decadal horizons"],
        ["Sentinel-2 L2A", "scripts/satellite/, data/processed/", "10m B04 Red & B08 NIR for cloud-cleared monthly NDVI curves", "Cloud contamination during monsoons (June-August); requires SCL masking"],
        ["Node.js 22 LTS", "server/server.js", "Express API gateway, session cookies, rate-limiting, SQLite proxy", "Requires ABI 127 for native C++ better-sqlite3 prebuilt binary"],
        ["better-sqlite3", "server/server.js, database/", "Synchronous relational SQLite storage for credentials and audit logs", "Native compilation resolved cleanly via Node 22 LTS standalone installation"],
        ["Vanilla ES6 / CSS3", "public/", "Zero external npm frontend bundle dependencies; high-speed rendering", "No virtual DOM; requires disciplined event-driven state updates"]
    ]
    doc.table(tech_headers, tech_rows, [1800, 2200, 2800, 2500])

    # Section 6
    doc.heading("6. Risk Engine: Mathematical Specification & Scientific Integrity", level=1)
    doc.p(
        "The deterministic heuristic engine evaluates five orthogonal sub-indices representing core soil degradation mechanisms. "
        "The composite Soil Degradation Index (SDI) is given by:"
    )
    doc.code("SDI = 0.25 * I_erosion + 0.25 * I_moisture + 0.15 * I_salinity + 0.15 * I_compaction + 0.20 * I_soc")
    
    sub_headers = ["Sub-Index", "Weight", "Key Drivers", "Mathematical Formulation & Thresholds"]
    sub_rows = [
        ["Erosion Hazard (I_erosion)", "0.25", "Monthly rain, NDVI proxy", "clip((PRECTOTCORR / 250) * (1 - NDVI_proxy) * 100, 0, 100)"],
        ["Moisture Deficit (I_moisture)", "0.25", "90-day rainfall anomaly, T_max", "clip(100 - (PRECIP_90D / PRECIP_mean)*100 + max(0, T_max - 35)*3, 0, 100)"],
        ["Salinization Risk (I_salinity)", "0.15", "Soil pH, aridity index", "clip(max(0, pH - 7.5)*40 + AridityIndex*20, 0, 100)"],
        ["Subsoil Compaction (I_compaction)", "0.15", "Bulk density, clay content", "clip(((bulk_density - 1.30)/0.45)*70 + (clay/60)*30, 0, 100)"],
        ["SOC Depletion (I_soc)", "0.20", "Soil organic carbon, mean temp", "clip(((30.0 - SOC)/25.0)*80 + (T_mean/40)*20, 0, 100)"]
    ]
    doc.table(sub_headers, sub_rows, [2200, 1000, 2200, 3900])

    doc.callout(
        "SCIENTIFIC INTEGRITY DIRECTIVES:\n"
        "1. Heuristic SDI is an agro-climatic risk index, NOT an empirically calibrated probability of biological crop failure.\n"
        "2. The Random Forest model is an ML SURROGATE trained on heuristic labels to accelerate scoring, NOT an empirical model trained on laboratory ground truth.\n"
        "3. SHAP values quantify feature contributions to the surrogate model's prediction; they DO NOT prove physical or biological causality.\n"
        "4. Satellite NDVI indicates vegetation greenness; low NDVI alone DOES NOT prove soil degradation (can be bare fallow or harvesting).\n"
        "5. Physical field validation for Chandigarh (30.7300° N, 76.7700° E) is currently PENDING FIELD DATA ACQUISITION.",
        prefix="SCIENTIFIC BOUNDARIES & DISCLOSURES: "
    )

    # Section 7
    doc.heading("7. Machine Learning Surrogate Pipeline & TreeSHAP", level=1)
    doc.p(
        "To enable sub-10ms inference and counterfactual simulation, SoilSentinel fits a calibrated Random Forest surrogate "
        "over a frozen 14-feature feature schema (models/soil_risk_model.joblib). The pipeline uses StandardScaler normalization "
        "and is evaluated on a chronological holdout split (2020-2023 training vs. 2024 test)."
    )
    doc.bullet("Classification Accuracy: 91.67% across test epochs (11/12 epochs correctly classified).")
    doc.bullet("Macro-Averaged F1-Score: 0.9267 across LOW, MODERATE, HIGH severity classes.")
    doc.bullet("Exact TreeSHAP Local Additivity: Guaranteed by test_features.py (|f(x) - (base + sum phi_i)| < 1e-4).")

    # Section 8
    doc.heading("8. Geospatial & Satellite Pipeline", level=1)
    doc.p(
        "The satellite pipeline (scripts/satellite/) processes ESA Copernicus Sentinel-2 L2A bottom-of-atmosphere surface reflectance granules "
        "centered on the study location (30.7300° N, 76.7700° E) across 60 monthly epochs (2020–2024)."
    )
    doc.bullet("Band Math: Calculates Normalized Difference Vegetation Index (NDVI = (B08 - B04) / (B08 + B04)).")
    doc.bullet("Quality Filtering: Employs Scene Classification Layer (SCL) to mask clouds, cloud shadows, and cirrus.")
    doc.bullet("Architectural Separation: Satellite NDVI is maintained in data/processed/satellite/aligned_feature_table_with_satellite.csv "
               "as an independent observational layer, preserving the frozen 14-feature ML schema without artifact invalidation.")

    # Section 9
    doc.heading("9. Verification Audit, Test Results & Live Execution", level=1)
    doc.p(
        "Every layer of the SoilSentinel stack was subjected to rigorous, reproducible automated verification:"
    )
    doc.bullet("Core Backend Test Suite: 200 passed, 21 subtests passed in 10.75s (pytest tests/ -v).", bold_prefix="Pytest Core:")
    doc.bullet("Satellite Ingestion & NDVI Suite: 11 passed in 1.96s (pytest tests/satellite/ -v).", bold_prefix="Pytest Satellite:")
    doc.bullet("Frontend & Server Syntax: JavaScript syntax verified cleanly (npm.cmd run check).", bold_prefix="Syntax Check:")
    doc.bullet("Node.js Compatibility: Resolved via standalone Node.js 22 LTS (ABI 127) installation in user AppData; npm.cmd ci installed all 201 packages cleanly.", bold_prefix="Node 22 Resolution:")
    doc.bullet("Live HTTP Probing: Express running on http://localhost:3000; Python bridge running on http://127.0.0.1:5001. All authenticated routes (/api/assessment/evaluate, /api/assessment/scenario, /api/auth/login) verified 200 OK.", bold_prefix="Live Runtime:")

    # Section 10
    doc.heading("10. Evidence-Based Feature Status Matrix", level=1)
    feat_headers = ["Feature / Component", "Status", "Ground Evidence", "Acceptance Criteria"]
    feat_rows = [
        ["Deterministic Risk Engine", "Implemented & Verified", "src/engine/risk_engine.py, 48 passing tests", "Composite score in < 10ms with full sub-indices"],
        ["ML Surrogate Classifier", "Implemented & Verified", "models/soil_risk_model.joblib, 91.67% accuracy", "Predicts category & continuous severity"],
        ["TreeSHAP Explanations", "Implemented & Verified", "models/shap_explainer.joblib, additivity verified", "Local additivity error < 1e-4 across all epochs"],
        ["NASA POWER Ingestion", "Implemented & Verified", "data/feature_table.csv (60 monthly epochs)", "Gap-free meteorology spanning 2020-2024"],
        ["ISRIC SoilGrids Alignment", "Implemented & Verified", "src/config.py, static pedological features", "Correctly scaled bulk density, pH, clay, SOC"],
        ["Sentinel-2 NDVI Pipeline", "Implemented & Verified", "data/processed/satellite/, 11 tests passing", "Cloud-cleared monthly NDVI across 60 epochs"],
        ["Counterfactual Simulator", "Implemented & Verified", "src/scenarios/simulator.py, /api/scenario live", "Simulates custom soil interventions in < 50ms"],
        ["Longitudinal Recovery Tracker", "Implemented & Verified", "src/recovery/tracker.py, 5-tier engine", "Categorizes trajectories (e.g. RECOVERING)"],
        ["Role-Based Auth & SQLite", "Implemented & Verified", "server/server.js, soilsentinel.db, bcrypt auth", "Session persistence for Farmer and Researcher"],
        ["Farmer Dashboard UI", "Implemented & Verified", "public/farmer-dashboard.html, HTTP 200 live", "Accessible visual cards, risk dial, checklist"],
        ["Researcher Dashboard UI", "Implemented & Verified", "public/researcher-dashboard.html, HTTP 200 live", "SHAP charts, telemetry table, what-if sliders"],
        ["Physical Field Validation", "Blocked / Pending", "Pending Field Acquisition status banner", "In-situ laboratory soil core correlation"]
    ]
    doc.table(feat_headers, feat_rows, [2200, 2000, 2800, 2300])

    # Section 11
    doc.heading("11. Prioritized Production Readiness Roadmap", level=1)
    doc.p("The prioritized engineering roadmap guides the transition of SoilSentinel to a production-grade enterprise system:")
    doc.bullet("P0 (Mandatory MVP): Dockerize multi-stage container deployment pinning Node 22 LTS and Python 3.10-slim.")
    doc.bullet("P0 (Mandatory MVP): Enforce strict Joi/Zod input boundary validation on scenario simulation sliders.")
    doc.bullet("P0 (Mandatory MVP): Migrate credentials and session secrets to environment-variable injection with production guards.")
    doc.bullet("P1 (High Post-MVP): Partner with regional agricultural universities for physical laboratory soil core validation.")
    doc.bullet("P1 (High Post-MVP): Deploy automated Copernicus API cron worker to ingest new Sentinel-2 granules within 48 hours.")
    doc.bullet("P1 (High Post-MVP): Implement dynamic localization for Hindi (हिन्दी) and Punjabi (ਪੰਜਾਬੀ) on the Farmer Dashboard.")
    doc.bullet("P2 (Scale): Migrate from SQLite to PostgreSQL with PostGIS extension for spatial indexing.")
    doc.bullet("P2 (Scale): Add Redis session caching and BullMQ asynchronous workers for batch report generation.")
    doc.bullet("P2 (Scale): Upgrade static satellite charts to an interactive Leaflet/Mapbox vector tile map container.")

    # Section 12
    doc.heading("12. Technical Glossary & Reference", level=1)
    doc.p("Key technical terms and definitions utilized throughout SoilSentinel:")
    doc.bullet("Bulk Density: Dry soil mass per unit volume (cg/cm^3); values > 1.55 g/cm^3 indicate compaction hardpans.", bold_prefix="Bulk Density:")
    doc.bullet("TreeSHAP: Fast polynomial-time algorithm for computing exact game-theoretic Shapley values for tree ensembles.", bold_prefix="TreeSHAP:")
    doc.bullet("NDVI: (B08 - B04) / (B08 + B04); standardized vegetation vigor index indicating live green biomass.", bold_prefix="NDVI:")
    doc.bullet("Surrogate Model: An empirical ML model trained to approximate the behavior of a complex or expensive simulation engine.", bold_prefix="Surrogate:")
    doc.bullet("Counterfactual Simulation: In silico adjustment of environmental features to evaluate system sensitivity and intervention efficacy.", bold_prefix="Counterfactual:")

    # Assemble and write to docx
    xml_content = doc.build_xml()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    with zipfile.ZipFile(DOCX_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", CONTENT_TYPES_XML)
        zf.writestr("_rels/.rels", RELS_XML)
        zf.writestr("docProps/core.xml", CORE_XML)
        zf.writestr("docProps/app.xml", APP_XML)
        zf.writestr("word/_rels/document.xml.rels", WORD_RELS_XML)
        zf.writestr("word/styles.xml", STYLES_XML)
        zf.writestr("word/document.xml", xml_content)
        
    print(f"Successfully generated DOCX at: {DOCX_PATH}")
    file_size = os.path.getsize(DOCX_PATH)
    print(f"File size: {file_size} bytes")

if __name__ == "__main__":
    generate_document()
