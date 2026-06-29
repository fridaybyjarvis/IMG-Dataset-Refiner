"""Shared pytest fixtures and path setup for IMG Dataset Refiner tests."""

import os
import sys

# Add project root to sys.path so test modules can import lora_manager,
# ai_backends, contact_sheets, i18n, etc. directly.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)