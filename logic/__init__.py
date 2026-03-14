"""
Financial Gauntlet — HyperAPI Pipeline
=======================================
A 5-stage AI-powered pipeline for detecting financial errors in documents.

Stages:
  1. Vendor Master extraction (pages 3–4)
  2. Document splitting & classification (pages 5–1000)
  3. Per-doc parsing + extraction (with caching)
  4. Needle detection across all 20 categories
  5. Deduplication + JSON output
"""

__version__ = "1.0.0"
