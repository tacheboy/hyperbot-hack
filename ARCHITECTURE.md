# Financial Gauntlet - Architecture & Data Flow

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Financial Gauntlet Pipeline                  │
│                                                                   │
│  Input: gauntlet.pdf (1,000 pages)                              │
│  Output: findings.json (200 errors across 20 categories)        │
└─────────────────────────────────────────────────────────────────┘

                              ▼

┌─────────────────────────────────────────────────────────────────┐
│ Stage 1: Vendor Master Extraction (pages 3-4)                   │
│ ─────────────────────────────────────────────────────────────── │
│                                                                   │
│  Pages 3-4 → HyperAPI parse() → OCR text                        │
│              HyperAPI extract() → 35 vendor records              │
│                                                                   │
│  Output: vendor_master = {                                       │
│    "vendors": {                                                  │
│      "V001": {name, gstin, ifsc, state_code, ...},             │
│      ...                                                         │
│    },                                                            │
│    "by_name": {name → vendor_id},                               │
│    "by_gstin": {gstin → vendor_id}                              │
│  }                                                               │
│                                                                   │
│  Time: ~15 seconds                                               │
└─────────────────────────────────────────────────────────────────┘

                              ▼

┌─────────────────────────────────────────────────────────────────┐
│ Stage 2: Document Splitting (pages 5-1000)                      │
│ ─────────────────────────────────────────────────────────────── │
│                                                                   │
│  PyMuPDF fast text layer (no API calls)                         │
│  Regex pattern matching for document boundaries                 │
│                                                                   │
│  Document Types Detected:                                        │
│  • invoice         • po              • bank_statement            │
│  • expense_report  • credit_note     • debit_note               │
│  • receipt         • delivery_note   • quotation                │
│                                                                   │
│  Output: List[DocSegment] (~750 segments)                       │
│    DocSegment(                                                   │
│      doc_type="invoice",                                         │
│      pages=[47, 48],                                             │
│      doc_id="INV-2025-0042"                                      │
│    )                                                             │
│                                                                   │
│  Time: ~8 seconds                                                │
└─────────────────────────────────────────────────────────────────┘

                              ▼

┌─────────────────────────────────────────────────────────────────┐
│ Stage 3: Parsing & Extraction (with caching)                    │
│ ─────────────────────────────────────────────────────────────── │
│                                                                   │
│  For each DocSegment:                                            │
│                                                                   │
│  1. Render pages to PNG (200 DPI)                               │
│     ├─ PyMuPDF: page → PNG                                      │
│     └─ Saved to /tmp/page_NNNN.png                              │
│                                                                   │
│  2. OCR each page (cached)                                       │
│     ├─ HyperAPI POST /api/v1/parse                              │
│     ├─ Input: PNG file                                           │
│     ├─ Output: {"ocr": "text"}                                   │
│     └─ Cache: .cache/ocr_NNNN.json                              │
│                                                                   │
│  3. Extract structured data (cached)                             │
│     ├─ HyperAPI POST /api/v1/extract                            │
│     ├─ Input: {"text": "ocr_text"}                              │
│     ├─ Output: {"data": {...}, "validation_errors": [...]}      │
│     └─ Cache: .cache/extract_{hash}.json                        │
│                                                                   │
│  Parallelization:                                                │
│  • ThreadPoolExecutor with 8 workers                             │
│  • Semaphore rate limiting (max 8 concurrent API calls)         │
│  • Thread-safe PDF rendering                                     │
│                                                                   │
│  Error Handling:                                                 │
│  • Exponential backoff retry (2s, 5s, 15s, 30s)                │
│  • Connection error resilience                                   │
│  • Graceful degradation                                          │
│                                                                   │
│  Output: List[DocSegment] with .parsed field populated          │
│    segment.parsed = {                                            │
│      "invoice_number": "INV-2025-0042",                          │
│      "vendor_name": "Acme Supplies",                             │
│      "total": 1475.00,                                           │
│      "line_items": [...],                                        │
│      "validation_errors": [...]                                  │
│    }                                                             │
│                                                                   │
│  Time: ~10 minutes (cold) / ~30 seconds (warm)                  │
└─────────────────────────────────────────────────────────────────┘

                              ▼

┌─────────────────────────────────────────────────────────────────┐
│ Stage 4: Needle Detection (20 error categories)                 │
│ ─────────────────────────────────────────────────────────────── │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ EASY Detectors (5 types, ~40 points)                    │   │
│  ├─────────────────────────────────────────────────────────┤   │
│  │ • arithmetic_error      - qty × rate ≠ amount           │   │
│  │ • billing_typo          - 0.15 vs 0:15 hours            │   │
│  │ • duplicate_line_item   - repeated lines                │   │
│  │ • invalid_date          - impossible dates              │   │
│  │ • wrong_tax_rate        - GST rate mismatch             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ MEDIUM Detectors (7 types, ~180 points)                 │   │
│  ├─────────────────────────────────────────────────────────┤   │
│  │ • po_invoice_mismatch   - PO vs invoice discrepancy     │   │
│  │ • vendor_name_typo      - fuzzy name matching           │   │
│  │ • double_payment        - duplicate payments            │   │
│  │ • ifsc_mismatch         - bank code errors              │   │
│  │ • duplicate_expense     - repeated expense claims       │   │
│  │ • date_cascade          - invoice before PO date        │   │
│  │ • gstin_state_mismatch  - tax ID state mismatch         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ EVIL Detectors (8 types, ~700 points)                   │   │
│  ├─────────────────────────────────────────────────────────┤   │
│  │ • quantity_accumulation - cumulative qty > PO by 20%    │   │
│  │ • price_escalation      - all invoices above PO rate    │   │
│  │ • balance_drift         - bank balance inconsistencies  │   │
│  │ • circular_reference    - credit/debit note loops       │   │
│  │ • triple_expense_claim  - 3+ expense claims             │   │
│  │ • employee_id_collision - same ID, different names      │   │
│  │ • fake_vendor           - vendor not in master          │   │
│  │ • phantom_po_reference  - non-existent PO reference     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
│  Deduplication:                                                  │
│  • Remove near-duplicate findings                                │
│  • Keep finding with more detail                                 │
│                                                                   │
│  Output: List[Finding] (~200 findings)                           │
│    {                                                             │
│      "category": "arithmetic_error",                             │
│      "pages": [47, 48],                                          │
│      "document_refs": ["INV-2025-0042"],                         │
│      "description": "Line 3: qty=2 × rate=100 = 200...",        │
│      "reported_value": "150",                                    │
│      "correct_value": "200"                                      │
│    }                                                             │
│                                                                   │
│  Time: ~5 seconds                                                │
└─────────────────────────────────────────────────────────────────┘

                              ▼

┌─────────────────────────────────────────────────────────────────┐
│ Stage 5: Output Formatting                                       │
│ ─────────────────────────────────────────────────────────────── │
│                                                                   │
│  • Validate categories against allowed set                       │
│  • Assign finding IDs (F-001, F-002, ...)                       │
│  • Sort pages                                                    │
│  • Clean values                                                  │
│                                                                   │
│  Output: findings.json                                           │
│  {                                                               │
│    "team_id": "your_team_name",                                 │
│    "findings": [                                                 │
│      {                                                           │
│        "finding_id": "F-001",                                    │
│        "category": "arithmetic_error",                           │
│        "pages": [47, 48],                                        │
│        "document_refs": ["INV-2025-0042"],                       │
│        "description": "...",                                     │
│        "reported_value": "150",                                  │
│        "correct_value": "200"                                    │
│      },                                                          │
│      ...                                                         │
│    ]                                                             │
│  }                                                               │
│                                                                   │
│  Time: <1 second                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## HyperAPI Integration

```
┌─────────────────────────────────────────────────────────────────┐
│                        HyperAPI Endpoints                         │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ POST /api/v1/parse                                           │
├──────────────────────────────────────────────────────────────┤
│ Purpose: Extract text from documents (OCR)                   │
│ Input:   Multipart file upload (PNG, JPG, PDF)              │
│ Output:  {"ocr": "extracted text"}                           │
│ Used in: Stage 1 (vendor master), Stage 3 (all documents)   │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ POST /api/v1/extract                                         │
├──────────────────────────────────────────────────────────────┤
│ Purpose: Extract structured data fields                      │
│ Input:   {"text": "ocr_text", "document_type": "optional"}  │
│ Output:  {"data": {...}, "validation_errors": [...]}        │
│ Used in: Stage 1 (vendor master), Stage 3 (all documents)   │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ POST /api/v1/classify                                        │
├──────────────────────────────────────────────────────────────┤
│ Purpose: Categorize document types                           │
│ Input:   Multipart file upload                              │
│ Output:  {"document_type": "invoice", "confidence": 0.95}   │
│ Used in: Optional (Stage 2 uses regex, but API available)   │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ POST /api/v1/split                                           │
├──────────────────────────────────────────────────────────────┤
│ Purpose: Split multi-page documents                          │
│ Input:   Multipart PDF upload                               │
│ Output:  {"pages": [...], "sections": [...]}                │
│ Used in: Optional (Stage 2 uses PyMuPDF, but API available) │
└──────────────────────────────────────────────────────────────┘
```

## Data Flow Diagram

```
gauntlet.pdf (1,000 pages)
    │
    ├─► Pages 1-2: Cover/Instructions (skipped)
    │
    ├─► Pages 3-4: Vendor Master
    │       │
    │       ├─► parse() → OCR text
    │       └─► extract() → 35 vendor records
    │
    └─► Pages 5-1000: Financial Documents
            │
            ├─► Stage 2: Split into ~750 segments
            │       │
            │       ├─► Invoices (~300)
            │       ├─► Purchase Orders (~200)
            │       ├─► Bank Statements (~100)
            │       ├─► Expense Reports (~80)
            │       ├─► Credit/Debit Notes (~50)
            │       └─► Other (~20)
            │
            ├─► Stage 3: Parse each segment
            │       │
            │       ├─► Render pages to PNG
            │       ├─► parse() → OCR text (cached)
            │       └─► extract() → structured data (cached)
            │
            ├─► Stage 4: Run 20 detectors
            │       │
            │       ├─► EASY detectors (single-doc)
            │       ├─► MEDIUM detectors (cross-doc)
            │       ├─► EVIL detectors (aggregated)
            │       └─► Deduplicate findings
            │
            └─► Stage 5: Format output
                    │
                    └─► findings.json (200 errors)
```

## Caching Strategy

```
.cache/
├── ocr_0003.json          ← Page 3 OCR (vendor master)
├── ocr_0004.json          ← Page 4 OCR (vendor master)
├── ocr_0005.json          ← Page 5 OCR (first document)
├── ...
├── ocr_1000.json          ← Page 1000 OCR (last document)
│
├── extract_abc123.json    ← Document 1 extraction
├── extract_def456.json    ← Document 2 extraction
└── ...

Cache Keys:
• OCR: page number (0001-1000)
• Extract: MD5 hash of (doc_id + pages)

Cache Hit Rate:
• First run: 0% (cold cache)
• Second run: 100% (warm cache)
• Speedup: 20x faster (10 min → 30 sec)
```

## Error Detection Flow

```
For each document segment:

1. Single-Document Checks (EASY)
   ├─► Check arithmetic: qty × rate = amount?
   ├─► Check dates: valid calendar dates?
   ├─► Check duplicates: repeated line items?
   ├─► Check tax rates: HSN/SAC → correct GST%?
   └─► Check billing: 0.15 hours vs 0:15 hours?

2. Cross-Document Checks (MEDIUM)
   ├─► Compare invoice vs PO: qty/rate match?
   ├─► Compare vendor names: typos?
   ├─► Compare bank statements: duplicate payments?
   ├─► Compare dates: invoice after PO?
   └─► Compare GSTIN/IFSC: match vendor master?

3. Aggregated Checks (EVIL)
   ├─► Sum quantities: cumulative > PO by 20%?
   ├─► Check all invoices: all above PO rate?
   ├─► Check bank balances: opening = prev closing?
   ├─► Check credit/debit notes: circular references?
   ├─► Check expenses: claimed 3+ times?
   ├─► Check employee IDs: same ID, different names?
   ├─► Check vendors: in master? (fuzzy match)
   └─► Check PO references: PO exists?

4. Deduplication
   ├─► Group by category + document overlap
   └─► Keep finding with more detail
```

## Performance Characteristics

```
Stage 1: Vendor Master
├─ API Calls: 4 (2 parse + 2 extract)
├─ Time: ~15 seconds
└─ Cache: Yes (vendor_master_v1.json)

Stage 2: Document Splitting
├─ API Calls: 0 (pure PyMuPDF)
├─ Time: ~8 seconds
└─ Cache: No (fast enough)

Stage 3: Parsing & Extraction
├─ API Calls: ~2,000 (1,000 parse + 750 extract)
├─ Time: ~10 minutes (cold) / ~30 seconds (warm)
├─ Cache: Yes (per page + per document)
└─ Parallelization: 8 workers

Stage 4: Needle Detection
├─ API Calls: 0 (pure Python logic)
├─ Time: ~5 seconds
└─ Cache: No (fast enough)

Stage 5: Output Formatting
├─ API Calls: 0 (pure Python)
├─ Time: <1 second
└─ Cache: No (always regenerate)

Total Time:
├─ First run: ~10-12 minutes
└─ Subsequent runs: ~1 minute
```

## Scoring Strategy

```
Error Category Distribution:
├─ EASY (5 types):    ~40 points   (4%)
├─ MEDIUM (7 types):  ~180 points  (19%)
└─ EVIL (8 types):    ~700 points  (77%)

Total Available: ~920 points

False Positive Penalty:
├─ -0.5 points per unmatched finding
└─ Capped at 20% of earned score

Strategy:
1. Run EASY detectors first (fast wins)
2. Focus on EVIL detectors (highest value)
3. Minimize false positives (high confidence only)
4. Tune thresholds for precision vs recall
```

This architecture provides a robust, scalable pipeline for detecting financial errors in large document bundles using AI-powered OCR and structured data extraction.
