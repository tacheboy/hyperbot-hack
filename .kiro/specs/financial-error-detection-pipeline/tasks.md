# Implementation Plan: Financial Error Detection Pipeline

## Overview

This plan implements a complete 5-stage AI-powered financial error detection pipeline that processes gauntlet.pdf (1,000 pages) and produces findings.json with up to 200 detected financial errors across 20 categories. The implementation uses Python with PyMuPDF for document processing, the HyperAPI SDK for OCR/extraction, and includes robust error handling, caching, parallelization, and comprehensive testing.

## Tasks

- [x] 1. Set up project structure and dependencies
  - Create logic/__init__.py to make logic a package
  - Create requirements.txt at repo root with pymupdf>=1.23.0 and httpx>=0.27.0
  - Fix all import statements from `from stages.X` to `from logic.X` in pipeline.py, parser.py, and detectors.py
  - Add environment variable loading for HYPERAPI_KEY, GAUNTLET_PDF, and CACHE_DIR
  - _Requirements: 30.1, 30.2, 30.3, 30.4, 31.1, 31.2, 31.3, 32.1, 32.2, 32.3_

- [x] 2. Implement Stage 1: Vendor Master Extraction
  - [x] 2.1 Implement extract_vendor_master function in vendor_master.py
    - Call client.parse() for pages 3-4 to get OCR text
    - Call client.extract() to get structured vendor data
    - Build vendor_master dict with vendors, by_name, and by_gstin indexes
    - Implement cache read/write with cache key vendor_master_{hash}.json
    - Add warning log when fewer than 30 vendors extracted
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 4.2, 4.3, 33.3_

- [x] 3. Implement Stage 2: Document Splitter
  - [x] 3.1 Implement split_and_classify function in splitter.py
    - Use PyMuPDF text layer extraction (no API calls)
    - Classify documents into 8 types: invoice, po, bank_statement, expense_report, credit_note, debit_note, receipt, other
    - Extract document IDs from text patterns
    - Return List[DocSegment] with doc_type, pages, and doc_id populated
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 34.3_

- [x] 4. Implement Stage 3: Parser with API calls and caching
  - [x] 4.1 Implement cache helper functions in parser.py
    - Implement _get_cache_path(cache_dir, cache_key) to generate cache file paths
    - Implement _read_cache(cache_path) to load cached JSON responses
    - Implement _write_cache(cache_path, data) to save API responses
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

  - [x] 4.2 Implement retry logic with exponential backoff in parser.py
    - Implement _call_with_retry(fn, *args, label) with MAX_RETRIES=4
    - Use backoff delays [2, 5, 15, 30] seconds
    - Catch ParseError and ExtractError from hyperapi.exceptions
    - Log warnings on retry attempts with attempt number and delay
    - Return empty dict on exhaustion, log warning, continue pipeline
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 33.1, 33.2_

  - [x] 4.3 Implement _parse_pages function for OCR in parser.py
    - For each page, check cache with key ocr_{page_no:04d}.json
    - On cache miss, render page to PNG and call client.parse() with retry
    - Write response to cache on success
    - Concatenate OCR text from all pages
    - _Requirements: 3.1, 4.4, 6.1, 6.2, 6.3, 6.4_

  - [x] 4.4 Implement _extract_all function for structured extraction in parser.py
    - Check cache for extract_{doc_hash}.json, entities_{doc_hash}.json, lineitems_{doc_hash}.json
    - On cache miss, call client.extract() with retry
    - On cache miss, call client.extract_entities() with retry
    - For invoices, call client.extract_lineitems() with retry
    - Merge results with later calls overwriting earlier values
    - Prefer extract_lineitems line_items over extract line_items for invoices
    - Write all responses to cache on success
    - _Requirements: 3.2, 3.3, 3.4, 3.5, 3.6, 4.5, 4.6, 4.7_

  - [x] 4.5 Implement parse_all_docs with ThreadPoolExecutor in parser.py
    - Create ThreadPoolExecutor with max_workers=8
    - Create Semaphore with limit 8 for API rate limiting
    - Implement _parse_one helper that acquires semaphore, calls _parse_pages and _extract_all
    - Submit all segments to thread pool
    - Use as_completed to wait for all futures and re-raise exceptions
    - Mutate segments in-place to populate raw_text and parsed fields
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 34.1, 34.2_

- [ ] 5. Checkpoint - Verify parsing infrastructure
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement Easy-tier detectors (single-document)
  - [x] 6.1 Implement detect_arithmetic_errors in detectors.py
    - For each line item, verify qty × rate == amount (tolerance 0.05)
    - Verify sum(line amounts) == subtotal (tolerance 0.10)
    - Verify subtotal + tax == grand_total (tolerance 0.10)
    - Surface validation_errors with type="arithmetic" from extract_lineitems
    - Return findings with category "arithmetic_error"
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [ ]* 6.2 Write property test for detect_arithmetic_errors
    - **Property P1: Arithmetic detector completeness**
    - **Validates: Requirements 7.1, 7.2, 7.3**
    - Generate random qty, rate with deliberate mismatch, verify finding created

  - [x] 6.3 Implement detect_billing_typos in detectors.py
    - Surface validation_errors with type="billing_typo" from extract_lineitems
    - Fallback heuristic: check if qty in (0, 0.5), multiple of 0.05, description contains "hour"/"time"
    - Compute corrected_hrs = qty × 100 / 60
    - Verify corrected_hrs × rate is closer to amount than qty × rate
    - Return findings with category "billing_typo"
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [ ]* 6.4 Write property test for detect_billing_typos
    - **Property P2: Billing typo detection**
    - **Validates: Requirements 8.2, 8.3, 8.4**
    - Generate line items with qty=0.15, verify corrected hours calculation

  - [x] 6.5 Implement detect_duplicate_line_items in detectors.py
    - Index line items by (description.lower(), quantity, rate)
    - Flag second occurrence of same key within document
    - Return findings with category "duplicate_line_item"
    - _Requirements: 9.1, 9.2, 9.3_

  - [x] 6.6 Implement detect_invalid_dates in detectors.py
    - Implement _parse_date helper with 6 standard format patterns
    - Fallback to regex extraction and datetime validation
    - Check all date fields: invoice_date, date, po_date, due_date, delivery_date, period_start, period_end, statement_date
    - Return findings with category "invalid_date"
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

  - [x] 6.7 Implement detect_wrong_tax_rates in detectors.py
    - Create HSN_TAX_RATE dictionary with common HSN/SAC codes and expected GST rates
    - For each line item with HSN/SAC, look up expected rate
    - Flag if abs(stated_rate - expected) > 0.5
    - Return findings with category "wrong_tax_rate"
    - _Requirements: 11.1, 11.2_

- [x] 7. Implement Medium-tier detectors (cross-document)
  - [x] 7.1 Implement detect_po_invoice_mismatches in detectors.py
    - Implement _normalize_ref helper to normalize PO/invoice IDs
    - For each invoice with po_number, find matching PO by normalized ID
    - Fuzzy-match invoice line items to PO lines by description (threshold 0.8)
    - Flag if qty or rate deviates > 1% from PO line
    - Return findings with category "po_invoice_mismatch"
    - _Requirements: 12.1, 12.2, 12.3_

  - [x] 7.2 Implement detect_vendor_name_typos in detectors.py
    - For each document with vendor_name/supplier_name, compute fuzzy match against all known vendors
    - Use difflib.SequenceMatcher for fuzzy matching
    - Flag if best match score is 0.75-0.99 (typo range)
    - Skip if exact match or score < 0.75 (handled by fake_vendor detector)
    - Return findings with category "vendor_name_typo"
    - _Requirements: 13.1, 13.2, 13.3, 13.4_

  - [x] 7.3 Implement detect_double_payments in detectors.py
    - Index payments by (payee.lower(), round(amount, 2), reference)
    - Flag second occurrence of same key across different bank statement documents
    - Return findings with category "double_payment"
    - _Requirements: 14.1, 14.2_

  - [x] 7.4 Implement detect_ifsc_mismatches in detectors.py
    - Look up vendor by name in vendor_master by_name index
    - Compare document bank_ifsc/ifsc against vendor_master IFSC (case-insensitive, stripped)
    - Return findings with category "ifsc_mismatch"
    - _Requirements: 15.1, 15.2, 15.3_

  - [x] 7.5 Implement detect_duplicate_expenses in detectors.py
    - Index expense lines by (employee_id, description.lower(), round(amount, 2), date)
    - Flag second occurrence of same key across different expense report documents
    - Return findings with category "duplicate_expense"
    - _Requirements: 16.1, 16.2_

  - [x] 7.6 Implement detect_date_cascade in detectors.py
    - For each invoice with po_number, parse invoice_date and PO po_date/date
    - Flag if invoice_date < po_date
    - Return findings with category "date_cascade"
    - _Requirements: 17.1, 17.2_

  - [x] 7.7 Implement detect_gstin_state_mismatch in detectors.py
    - Look up vendor by GSTIN in vendor_master by_gstin index
    - Compare first 2 chars of document GSTIN against vendor_master state_code
    - Return findings with category "gstin_state_mismatch"
    - _Requirements: 18.1, 18.2, 18.3_

- [x] 8. Implement Evil-tier detectors (aggregated, multi-document)
  - [x] 8.1 Implement detect_quantity_accumulation in detectors.py
    - Group invoices by (po_ref, description_key) using fuzzy matching
    - Sum quantity across all invoices in each group
    - Find matching PO line quantity
    - Flag if cumulative_inv_qty / po_qty > 1.20
    - Return findings with category "quantity_accumulation"
    - _Requirements: 19.1, 19.2, 19.3_

  - [x] 8.2 Implement detect_price_escalation in detectors.py
    - Group invoices by PO reference
    - For each PO line item, check if ALL invoices charge rate > PO rate
    - Require >= 2 invoices to avoid false positives
    - Return findings with category "price_escalation"
    - _Requirements: 20.1, 20.2, 20.3_

  - [x] 8.3 Implement detect_balance_drift in detectors.py
    - Sort bank statements by statement_date chronologically
    - Walk sorted list comparing opening_balance[N] vs closing_balance[N-1]
    - Use tolerance ±0.50 for rounding
    - Return findings with category "balance_drift"
    - _Requirements: 21.1, 21.2, 21.3_

  - [x] 8.4 Implement detect_circular_references in detectors.py
    - Build directed graph from doc_id to referenced doc_ids using references/against_invoice fields
    - Implement iterative DFS cycle detection
    - Report full cycle path in finding description
    - Return findings with category "circular_reference"
    - _Requirements: 22.1, 22.2, 22.3_

  - [x] 8.5 Implement detect_triple_expense_claims in detectors.py
    - Identify hotel expenses using keywords: hotel, stay, accommodation, lodge, room
    - Group by (employee_id, description[:40], round(amount, 2), date)
    - Flag if same key appears in >= 3 distinct expense report documents
    - Return findings with category "triple_expense_claim"
    - _Requirements: 23.1, 23.2, 23.3_

  - [x] 8.6 Implement detect_employee_id_collision in detectors.py
    - Index employee_id to (employee_name, doc_id, page)
    - When same employee_id appears with different name, compute fuzzy similarity
    - Flag if similarity < 0.85
    - Return findings with category "employee_id_collision"
    - _Requirements: 24.1, 24.2_

  - [x] 8.7 Implement detect_fake_vendors in detectors.py
    - For invoice/receipt segments only
    - Check if vendor GSTIN is in vendor_master by_gstin index
    - If not found, compute best fuzzy match against all known vendor names
    - Flag if best match score < 0.70
    - Return findings with category "fake_vendor"
    - _Requirements: 25.1, 25.2, 25.3, 25.4_

  - [x] 8.8 Implement detect_phantom_po_references in detectors.py
    - Build set of all known normalized PO IDs from PO documents
    - For each invoice with po_number, check if normalized po_number is in set
    - Only flag if po_number matches PO ID pattern (well-formed)
    - Return findings with category "phantom_po_reference"
    - _Requirements: 26.1, 26.2, 26.3_

- [ ] 9. Checkpoint - Verify all detectors
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Implement detector orchestration and deduplication
  - [x] 10.1 Implement run_all_detectors in detectors.py
    - Partition parsed_docs by doc_type into invoices, pos, bank_statements, expense_reports, credit_notes, debit_notes
    - Execute all 5 Easy-tier detectors on appropriate documents
    - Execute all 7 Medium-tier detectors with appropriate subsets
    - Execute all 8 Evil-tier detectors with appropriate subsets
    - Collect all findings into single list
    - Call _deduplicate on collected findings
    - _Requirements: 27.1, 27.2, 27.3, 27.4, 27.5, 28.4_

  - [x] 10.2 Implement _deduplicate function in detectors.py
    - Compare findings by category and document_refs
    - Compute Jaccard overlap of document_refs (after normalization)
    - Consider duplicates if same category and Jaccard >= 0.5
    - Keep finding with longer description when duplicates found
    - Use index-based replacement to avoid O(n) remove operation
    - _Requirements: 28.1, 28.2, 28.3_

  - [ ]* 10.3 Write property test for deduplication idempotency
    - **Property P3: Deduplication idempotency**
    - **Validates: Requirements 28.1, 28.2, 28.3**
    - Verify _deduplicate(_deduplicate(findings)) == _deduplicate(findings)

- [x] 11. Implement Stage 5: Output generation
  - [x] 11.1 Implement build_findings_json in output.py
    - Assign sequential finding IDs: F-001, F-002, etc.
    - Validate each finding has required keys: finding_id, category, pages, document_refs, description, reported_value, correct_value
    - Validate category is in VALID_CATEGORIES list
    - Build output dict with team_id and findings array
    - Write to findings.json with proper JSON formatting
    - Raise IOError on write failure
    - _Requirements: 29.1, 29.2, 29.3, 29.4_

- [x] 12. Implement main pipeline orchestration
  - [x] 12.1 Implement main function in pipeline.py
    - Load environment variables: HYPERAPI_KEY, GAUNTLET_PDF (default gauntlet.pdf), CACHE_DIR (default .cache)
    - Initialize HyperAPIClient with API key
    - Create cache directory if not exists
    - Call extract_vendor_master for Stage 1
    - Call split_and_classify for Stage 2 (pages 5-1000)
    - Call parse_all_docs for Stage 3 with ThreadPoolExecutor
    - Call run_all_detectors for Stage 4
    - Call build_findings_json for Stage 5
    - Log total findings count and execution time
    - Handle vendor master empty error with RuntimeError
    - _Requirements: 6.5, 32.1, 32.2, 32.3, 32.4, 33.4_

  - [x] 12.2 Add __main__ entry point in pipeline.py
    - Enable execution as `python -m logic.pipeline` from repo root
    - Enable execution as `python logic/pipeline.py` with sys.path adjustment
    - _Requirements: 30.3_

- [x] 13. Add robust error handling and connection resilience
  - [x] 13.1 Add connection error handling in parser.py
    - Catch httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError in retry logic
    - Add these to the exception types that trigger retry
    - Log connection errors with clear messages
    - _Requirements: 6.1, 6.2, 6.3, 33.1_

  - [x] 13.2 Add API response validation in parser.py
    - Validate API responses have expected structure before caching
    - Check for "data" key in extract/extract_entities/extract_lineitems responses
    - Handle malformed responses gracefully by treating as cache miss
    - _Requirements: 6.3, 6.4_

  - [x] 13.3 Add PDF rendering error handling in parser.py
    - Wrap fitz page rendering in try-except
    - Log error and skip page on render failure
    - Continue with remaining pages
    - _Requirements: 6.4, 33.2_

  - [x] 13.4 Add graceful degradation for missing fields in detectors
    - Use .get() with default values for all parsed field accesses
    - Skip documents with empty parsed dicts
    - Never crash on missing/malformed data
    - _Requirements: 6.4_

- [x] 14. Fix lint errors and code quality issues
  - [x] 14.1 Run linter and fix import order issues
    - Organize imports: stdlib, third-party, local
    - Remove unused imports
    - Add missing imports

  - [x] 14.2 Fix type hints and add missing annotations
    - Add return type hints to all functions
    - Add parameter type hints where missing
    - Use Optional[] for nullable types

  - [x] 14.3 Fix line length and formatting issues
    - Break long lines to <= 100 characters
    - Fix indentation inconsistencies
    - Add proper spacing around operators

  - [x] 14.4 Add docstrings to public functions
    - Add module-level docstrings
    - Add function docstrings with Args, Returns, Raises sections
    - Document complex algorithms

- [x] 15. Optimize for gauntlet.pdf specifics
  - [x] 15.1 Add gauntlet-specific heuristics in splitter.py
    - Recognize HyperAPI Technologies Pvt Ltd document patterns
    - Improve invoice/PO/expense report classification accuracy
    - Handle multi-page document boundary detection

  - [x] 15.2 Expand HSN_TAX_RATE dictionary in detectors.py
    - Add common HSN/SAC codes found in gauntlet.pdf
    - Include rates for services (18%, 12%, 5%)
    - Include rates for goods (28%, 18%, 12%, 5%)

  - [x] 15.3 Tune fuzzy matching thresholds based on gauntlet.pdf
    - Test vendor name typo threshold (0.75-0.99 range)
    - Test fake vendor threshold (< 0.70)
    - Test PO line item description matching (0.8)
    - Adjust if needed to minimize false positives

- [x] 16. Add comprehensive logging
  - [x] 16.1 Add stage-level progress logging
    - Log start/completion of each stage with timing
    - Log document counts at each stage
    - Log cache hit/miss statistics

  - [x] 16.2 Add detector-level logging
    - Log findings count per detector
    - Log detector execution time
    - Log skipped documents due to missing data

  - [x] 16.3 Add error aggregation logging
    - Log summary of all API failures at end
    - Log summary of all parsing failures
    - Log summary of all skipped documents

- [ ]* 17. Write integration tests
  - [ ]* 17.1 Create test_pipeline_integration.py
    - Create small synthetic PDF with known errors
    - Run full pipeline end-to-end
    - Assert findings.json contains expected findings
    - Verify all 20 error categories can be detected

  - [ ]* 17.2 Create test_caching.py
    - Run pipeline twice with same input
    - Verify second run uses cache (no API calls)
    - Verify cache invalidation works correctly

  - [ ]* 17.3 Create test_error_handling.py
    - Mock API failures and verify retry logic
    - Mock connection errors and verify resilience
    - Verify pipeline continues after individual document failures

- [ ] 18. Final checkpoint and validation
  - Run full pipeline on gauntlet.pdf
  - Verify findings.json is generated with valid structure
  - Check findings count is reasonable (target ~200)
  - Verify no crashes or unhandled exceptions
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at key milestones
- Property tests validate universal correctness properties from design document
- Integration tests validate end-to-end functionality
- The implementation prioritizes robustness and error handling as requested
- Optimization tasks (15.x) are specific to gauntlet.pdf as requested
- All code will be in Python as specified in the design document
