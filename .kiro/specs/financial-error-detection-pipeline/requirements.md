# Requirements Document: Financial Error Detection Pipeline

## Introduction

This document specifies the functional requirements for an AI-powered financial error detection pipeline that processes a 1,000-page Accounts Payable bundle (gauntlet.pdf) and identifies up to 200 deliberate financial errors across 20 categories. The system uses PyMuPDF for document processing and the HyperAPI SDK for OCR and structured extraction, with disk-based caching to optimize API usage across multiple runs.

## Glossary

- **Pipeline**: The complete 5-stage processing system from PDF input to findings output
- **DocSegment**: A data structure representing a classified document segment with pages, type, and extracted data
- **Vendor_Master**: A reference database of 35 known vendors extracted from pages 3-4 of the input PDF
- **Finding**: A detected financial error with category, location, description, and correction information
- **HyperAPI_Client**: The SDK client for making OCR and extraction API calls
- **Cache**: A disk-based storage system for API responses to avoid redundant calls
- **Detector**: A function that analyzes parsed documents to identify specific error categories
- **Parser**: The Stage 3 component that performs OCR and structured extraction via API calls
- **Splitter**: The Stage 2 component that segments the PDF into classified document types

## Requirements

### Requirement 1: Vendor Master Extraction

**User Story:** As a pipeline operator, I want to extract a vendor master database from the PDF, so that I can validate vendor information in subsequent documents.

#### Acceptance Criteria

1. WHEN the pipeline processes pages 3-4 of the input PDF, THE Vendor_Master SHALL extract at least 30 vendor records
2. FOR EACH vendor record, THE Vendor_Master SHALL extract name, GSTIN, state code, IFSC, bank account, address, and source page
3. THE Vendor_Master SHALL create a by_name index mapping lowercase vendor names to vendor IDs
4. THE Vendor_Master SHALL create a by_gstin index mapping GSTIN values to vendor IDs
5. WHEN fewer than 30 vendors are extracted, THE Pipeline SHALL log a warning indicating possible extraction failure

### Requirement 2: Document Segmentation

**User Story:** As a pipeline operator, I want to segment the PDF into classified document types, so that appropriate extraction strategies can be applied to each document.

#### Acceptance Criteria

1. WHEN the pipeline processes pages 5-1000, THE Splitter SHALL classify each segment as one of: invoice, po, bank_statement, expense_report, credit_note, debit_note, receipt, or other
2. FOR EACH document segment, THE Splitter SHALL record the document type, page numbers, and document ID
3. THE Splitter SHALL use PyMuPDF text layer extraction without making API calls
4. THE Splitter SHALL return approximately 750 document segments for the 996-page input range

### Requirement 3: OCR and Structured Extraction

**User Story:** As a pipeline operator, I want to extract structured data from each document segment, so that detectors can analyze the financial information.

#### Acceptance Criteria

1. FOR EACH page in a document segment, THE Parser SHALL call client.parse to obtain OCR text
2. FOR EACH invoice document, THE Parser SHALL call client.extract_lineitems to obtain validated line items
3. FOR EACH document, THE Parser SHALL call client.extract_entities to obtain vendor, GSTIN, IFSC, and date information
4. FOR EACH document, THE Parser SHALL call client.extract to obtain the full structured data dictionary
5. THE Parser SHALL merge extraction results with later calls overwriting earlier values for duplicate keys
6. WHEN line items are extracted for invoices, THE Parser SHALL use extract_lineitems results in preference to extract results

### Requirement 4: API Response Caching

**User Story:** As a pipeline operator, I want API responses to be cached on disk, so that re-running the pipeline does not incur redundant API costs.

#### Acceptance Criteria

1. WHEN an API call is about to be made, THE Parser SHALL check if a cache file exists for that request
2. WHEN a cache file exists, THE Parser SHALL load and return the cached response without making an API call
3. WHEN an API call succeeds, THE Parser SHALL write the response to a cache file with a stable hash-based filename
4. THE Parser SHALL use cache key format ocr_{page_no:04d}.json for OCR calls
5. THE Parser SHALL use cache key format extract_{doc_hash}.json for extraction calls
6. THE Parser SHALL use cache key format lineitems_{doc_hash}.json for line item extraction calls
7. THE Parser SHALL use cache key format entities_{doc_hash}.json for entity extraction calls

### Requirement 5: Concurrent API Processing

**User Story:** As a pipeline operator, I want API calls to be processed concurrently, so that the pipeline completes in reasonable time.

#### Acceptance Criteria

1. THE Parser SHALL use a ThreadPoolExecutor with 8 worker threads for concurrent processing
2. THE Parser SHALL use a semaphore to limit concurrent API calls to 8
3. WHEN any parsing task fails, THE Parser SHALL re-raise the exception after all tasks complete
4. THE Parser SHALL process approximately 2,250 API calls in approximately 10 minutes on first run with cold cache

### Requirement 6: API Error Handling and Retry

**User Story:** As a pipeline operator, I want API failures to be retried automatically, so that transient network issues do not cause pipeline failure.

#### Acceptance Criteria

1. WHEN an API call fails with ParseError or ExtractError, THE Parser SHALL retry up to 4 times total
2. THE Parser SHALL wait 2 seconds before the first retry, 5 seconds before the second, 15 seconds before the third, and 30 seconds before the fourth
3. WHEN all retries are exhausted, THE Parser SHALL set the segment parsed field to empty dict and log a warning
4. WHEN all retries are exhausted, THE Parser SHALL continue processing remaining segments
5. WHEN vendor master extraction returns empty, THE Pipeline SHALL raise RuntimeError

### Requirement 7: Arithmetic Error Detection

**User Story:** As a financial auditor, I want to detect arithmetic errors in invoices, so that I can identify calculation mistakes.

#### Acceptance Criteria

1. FOR EACH line item in an invoice, THE Detector SHALL verify that quantity times rate equals amount within tolerance 0.05
2. FOR EACH invoice, THE Detector SHALL verify that sum of line amounts equals stated subtotal within tolerance 0.10
3. FOR EACH invoice, THE Detector SHALL verify that subtotal plus tax equals grand total within tolerance 0.10
4. WHEN a validation_error with type arithmetic is present in extract_lineitems response, THE Detector SHALL create a finding
5. WHEN an arithmetic invariant is violated, THE Detector SHALL create a finding with category arithmetic_error

### Requirement 8: Billing Typo Detection

**User Story:** As a financial auditor, I want to detect billing typos where minutes are recorded as hours, so that I can identify time-billing errors.

#### Acceptance Criteria

1. WHEN a validation_error with type billing_typo is present in extract_lineitems response, THE Detector SHALL create a finding
2. FOR EACH line item with hour or time in description, THE Detector SHALL check if quantity is in range (0, 0.5) and is a multiple of 0.05
3. WHEN the heuristic conditions are met, THE Detector SHALL compute corrected_hrs as quantity times 100 divided by 60
4. WHEN corrected_hrs times rate is closer to amount than quantity times rate, THE Detector SHALL create a finding with category billing_typo

### Requirement 9: Duplicate Line Item Detection

**User Story:** As a financial auditor, I want to detect duplicate line items within a single document, so that I can identify double-billing.

#### Acceptance Criteria

1. FOR EACH document, THE Detector SHALL index line items by lowercase description, quantity, and rate
2. WHEN two line items in the same document have identical description, quantity, and rate, THE Detector SHALL create a finding for the second occurrence
3. THE Detector SHALL create findings with category duplicate_line_item

### Requirement 10: Invalid Date Detection

**User Story:** As a financial auditor, I want to detect invalid dates in documents, so that I can identify data entry errors.

#### Acceptance Criteria

1. FOR EACH date field in a document, THE Detector SHALL attempt to parse the date using 6 standard format patterns
2. WHEN standard parsing fails, THE Detector SHALL attempt regex extraction and validation
3. WHEN a date cannot be parsed or represents an invalid calendar date, THE Detector SHALL create a finding with category invalid_date
4. THE Detector SHALL check invoice_date, date, po_date, due_date, delivery_date, period_start, period_end, and statement_date fields

### Requirement 11: Wrong Tax Rate Detection

**User Story:** As a financial auditor, I want to detect incorrect GST rates on line items, so that I can identify tax calculation errors.

#### Acceptance Criteria

1. FOR EACH line item with an HSN or SAC code, THE Detector SHALL look up the expected GST rate in the HSN_TAX_RATE dictionary
2. WHEN the stated tax rate differs from the expected rate by more than 0.5 percentage points, THE Detector SHALL create a finding with category wrong_tax_rate

### Requirement 12: PO-Invoice Mismatch Detection

**User Story:** As a financial auditor, I want to detect mismatches between purchase orders and invoices, so that I can identify unauthorized charges.

#### Acceptance Criteria

1. FOR EACH invoice with a po_number field, THE Detector SHALL find the matching purchase order by normalized ID
2. FOR EACH line item in the invoice, THE Detector SHALL fuzzy-match by description to the corresponding PO line with threshold 0.8
3. WHEN quantity or rate deviates by more than 1 percent from the PO line, THE Detector SHALL create a finding with category po_invoice_mismatch

### Requirement 13: Vendor Name Typo Detection

**User Story:** As a financial auditor, I want to detect vendor name typos, so that I can identify data entry errors in vendor information.

#### Acceptance Criteria

1. FOR EACH document with a vendor_name or supplier_name field, THE Detector SHALL compute fuzzy match score against all known vendor names
2. WHEN the best match score is between 0.75 and 0.99, THE Detector SHALL create a finding with category vendor_name_typo
3. WHEN the best match score is below 0.75, THE Detector SHALL not create a vendor_name_typo finding
4. WHEN the vendor name exactly matches a known vendor, THE Detector SHALL not create a finding

### Requirement 14: Double Payment Detection

**User Story:** As a financial auditor, I want to detect duplicate payments in bank statements, so that I can identify erroneous double payments.

#### Acceptance Criteria

1. THE Detector SHALL index payments by lowercase payee, rounded amount, and reference
2. WHEN the same payment key appears in two different bank statement documents, THE Detector SHALL create a finding with category double_payment

### Requirement 15: IFSC Mismatch Detection

**User Story:** As a financial auditor, I want to detect IFSC code mismatches against the vendor master, so that I can identify incorrect banking information.

#### Acceptance Criteria

1. FOR EACH document with a bank_ifsc or ifsc field, THE Detector SHALL look up the vendor by name in the by_name index
2. WHEN the vendor is found, THE Detector SHALL compare the document IFSC against the vendor master IFSC using case-insensitive stripped comparison
3. WHEN the IFSC codes do not match, THE Detector SHALL create a finding with category ifsc_mismatch

### Requirement 16: Duplicate Expense Detection

**User Story:** As a financial auditor, I want to detect duplicate expense claims across multiple expense reports, so that I can identify fraudulent reimbursement requests.

#### Acceptance Criteria

1. THE Detector SHALL index expense lines by employee_id, lowercase description, rounded amount, and date
2. WHEN the same expense key appears in two different expense report documents, THE Detector SHALL create a finding with category duplicate_expense

### Requirement 17: Date Cascade Detection

**User Story:** As a financial auditor, I want to detect invoices dated before their referenced purchase orders, so that I can identify temporal inconsistencies.

#### Acceptance Criteria

1. FOR EACH invoice with a po_number field, THE Detector SHALL parse both the invoice_date and the PO po_date or date field
2. WHEN the invoice_date is earlier than the po_date, THE Detector SHALL create a finding with category date_cascade

### Requirement 18: GSTIN State Mismatch Detection

**User Story:** As a financial auditor, I want to detect GSTIN state code mismatches against the vendor master, so that I can identify incorrect tax identification numbers.

#### Acceptance Criteria

1. FOR EACH document with a GSTIN field, THE Detector SHALL look up the vendor by GSTIN in the by_gstin index
2. WHEN the vendor is found, THE Detector SHALL compare the first 2 characters of the document GSTIN against the vendor master state_code
3. WHEN the state codes do not match, THE Detector SHALL create a finding with category gstin_state_mismatch

### Requirement 19: Quantity Accumulation Detection

**User Story:** As a financial auditor, I want to detect over-billing where cumulative invoice quantities exceed purchase order quantities, so that I can identify quantity fraud.

#### Acceptance Criteria

1. THE Detector SHALL group invoices by po_ref and description_key
2. FOR EACH group, THE Detector SHALL sum the quantity across all invoices
3. WHEN the cumulative invoice quantity exceeds the PO quantity times threshold 1.20, THE Detector SHALL create a finding with category quantity_accumulation

### Requirement 20: Price Escalation Detection

**User Story:** As a financial auditor, I want to detect systematic price escalation where all invoices charge above the contracted PO rate, so that I can identify pricing fraud.

#### Acceptance Criteria

1. THE Detector SHALL group invoices by PO reference
2. FOR EACH PO line item, THE Detector SHALL check if every invoice against that PO charges a rate above the contracted PO rate
3. WHEN at least 2 invoices all exceed the PO rate, THE Detector SHALL create a finding with category price_escalation

### Requirement 21: Balance Drift Detection

**User Story:** As a financial auditor, I want to detect balance inconsistencies between consecutive bank statements, so that I can identify reconciliation errors.

#### Acceptance Criteria

1. THE Detector SHALL sort bank statements by statement_date in chronological order
2. FOR EACH consecutive pair of statements, THE Detector SHALL compare the opening_balance of statement N against the closing_balance of statement N-1
3. WHEN the difference exceeds tolerance 0.50, THE Detector SHALL create a finding with category balance_drift

### Requirement 22: Circular Reference Detection

**User Story:** As a financial auditor, I want to detect circular references in credit notes and debit notes, so that I can identify document chain errors.

#### Acceptance Criteria

1. THE Detector SHALL build a directed graph from doc_id to referenced doc_ids using references and against_invoice fields
2. THE Detector SHALL run iterative DFS cycle detection on the graph
3. WHEN a cycle is detected, THE Detector SHALL create a finding with category circular_reference including the full cycle path

### Requirement 23: Triple Expense Claim Detection

**User Story:** As a financial auditor, I want to detect hotel expenses claimed three or more times, so that I can identify systematic expense fraud.

#### Acceptance Criteria

1. THE Detector SHALL identify hotel expense lines using keywords hotel, stay, accommodation, lodge, or room
2. THE Detector SHALL group hotel expenses by employee_id, first 40 characters of description, rounded amount, and date
3. WHEN the same expense key appears in 3 or more distinct expense report documents, THE Detector SHALL create a finding with category triple_expense_claim

### Requirement 24: Employee ID Collision Detection

**User Story:** As a financial auditor, I want to detect employee ID collisions where the same ID is used with different names, so that I can identify identity fraud.

#### Acceptance Criteria

1. THE Detector SHALL index employee_id to employee_name, doc_id, and page
2. WHEN the same employee_id appears with a different name having fuzzy similarity below 0.85, THE Detector SHALL create a finding with category employee_id_collision

### Requirement 25: Fake Vendor Detection

**User Story:** As a financial auditor, I want to detect invoices from vendors not in the vendor master, so that I can identify fraudulent vendors.

#### Acceptance Criteria

1. FOR EACH invoice or receipt segment, THE Detector SHALL check if the vendor GSTIN is in the by_gstin index
2. WHEN the GSTIN is not found, THE Detector SHALL compute the best fuzzy match score against all known vendor names
3. WHEN the best match score is below 0.70, THE Detector SHALL create a finding with category fake_vendor
4. WHEN the best match score is 0.70 or above, THE Detector SHALL not create a fake_vendor finding

### Requirement 26: Phantom PO Reference Detection

**User Story:** As a financial auditor, I want to detect invoices referencing non-existent purchase orders, so that I can identify unauthorized purchases.

#### Acceptance Criteria

1. THE Detector SHALL build a set of all known normalized PO IDs from purchase order documents
2. FOR EACH invoice with a po_number field, THE Detector SHALL check if the normalized po_number is in the known PO set
3. WHEN the po_number is not found in the set, THE Detector SHALL create a finding with category phantom_po_reference

### Requirement 27: Detector Orchestration

**User Story:** As a pipeline operator, I want all detectors to be executed in a coordinated manner, so that all error categories are checked.

#### Acceptance Criteria

1. THE Pipeline SHALL partition parsed documents by doc_type into invoices, pos, bank_statements, expense_reports, credit_notes, and debit_notes
2. THE Pipeline SHALL execute all 5 Easy-tier detectors on appropriate document types
3. THE Pipeline SHALL execute all 7 Medium-tier detectors with appropriate document subsets
4. THE Pipeline SHALL execute all 8 Evil-tier detectors with appropriate document subsets
5. THE Pipeline SHALL collect findings from all detectors into a single list

### Requirement 28: Finding Deduplication

**User Story:** As a pipeline operator, I want duplicate findings to be removed, so that the same error is not reported multiple times.

#### Acceptance Criteria

1. THE Pipeline SHALL compare findings by category and document_refs
2. WHEN two findings have the same category and Jaccard overlap of document_refs is 0.5 or greater, THE Pipeline SHALL consider them duplicates
3. WHEN duplicates are found, THE Pipeline SHALL keep the finding with the longer description
4. THE Pipeline SHALL apply deduplication after all detectors have run

### Requirement 29: Findings Output Generation

**User Story:** As a pipeline operator, I want findings to be written to a JSON file, so that they can be submitted for scoring.

#### Acceptance Criteria

1. THE Pipeline SHALL assign sequential finding IDs in format F-001, F-002, etc.
2. FOR EACH finding, THE Pipeline SHALL include finding_id, category, pages, document_refs, description, reported_value, and correct_value
3. THE Pipeline SHALL write the findings to findings.json with team_id and findings array
4. WHEN the findings.json write fails, THE Pipeline SHALL raise IOError

### Requirement 30: Module Import Structure

**User Story:** As a developer, I want the module import structure to be correct, so that the pipeline can be executed without import errors.

#### Acceptance Criteria

1. THE Pipeline SHALL use imports in format from logic.module_name import ClassName
2. THE Pipeline SHALL include a logic/__init__.py file to make logic a package
3. THE Pipeline SHALL be executable as python -m logic.pipeline from the repository root
4. THE Pipeline SHALL not use imports in format from stages.module_name which do not match the directory structure

### Requirement 31: Dependency Management

**User Story:** As a developer, I want dependencies to be clearly specified, so that the environment can be set up correctly.

#### Acceptance Criteria

1. THE Repository SHALL include a requirements.txt file at the root
2. THE requirements.txt SHALL specify pymupdf version 1.23.0 or greater
3. THE requirements.txt SHALL specify httpx version 0.27.0 or greater
4. THE Pipeline SHALL use the hyperapi package installed from source via pip install -e hyperapi-sdk/

### Requirement 32: Configuration via Environment Variables

**User Story:** As a pipeline operator, I want to configure the pipeline via environment variables, so that sensitive information is not hardcoded.

#### Acceptance Criteria

1. THE Pipeline SHALL read the HyperAPI key from environment variable HYPERAPI_KEY
2. THE Pipeline SHALL read the PDF path from environment variable GAUNTLET_PDF with default gauntlet.pdf
3. THE Pipeline SHALL read the cache directory from environment variable CACHE_DIR with default .cache
4. THE Pipeline SHALL never hardcode API keys or credentials in source code

### Requirement 33: Logging and Diagnostics

**User Story:** As a pipeline operator, I want informative log messages, so that I can monitor pipeline progress and diagnose issues.

#### Acceptance Criteria

1. WHEN an API call is retried, THE Pipeline SHALL log a warning with the attempt number, error message, and retry delay
2. WHEN a document fails all retry attempts, THE Pipeline SHALL log a warning with the document ID and page numbers
3. WHEN fewer than 30 vendors are extracted, THE Pipeline SHALL log a warning
4. WHEN the pipeline completes, THE Pipeline SHALL log the total number of findings and execution time

### Requirement 34: Performance Targets

**User Story:** As a pipeline operator, I want the pipeline to complete in reasonable time, so that I can iterate quickly during development.

#### Acceptance Criteria

1. WHEN the cache is cold, THE Pipeline SHALL complete Stage 3 parsing in approximately 10 minutes
2. WHEN the cache is warm, THE Pipeline SHALL complete Stage 3 parsing in less than 30 seconds
3. THE Pipeline SHALL complete Stage 2 splitting in less than 10 seconds
4. THE Pipeline SHALL complete Stage 4 detection in less than 5 seconds
5. THE Pipeline SHALL complete Stage 5 output generation in less than 1 second
