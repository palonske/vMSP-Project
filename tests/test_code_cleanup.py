"""
Tests for the code cleanup changes.

This validates that:
1. The crud.py file was removed (it was empty)
2. The fix_date function is imported from utils.py instead of duplicated
3. The fix_date function works correctly
"""

import pytest
import os
from datetime import datetime, timezone


class TestCrudFileRemoval:
    """Test that the empty crud.py file was removed."""

    def test_crud_file_does_not_exist(self):
        """Verify that app/crud.py no longer exists."""
        crud_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "app",
            "crud.py"
        )
        assert not os.path.exists(crud_path), \
            "crud.py should be deleted as it was empty"


class TestFixDateConsolidation:
    """Test that fix_date is properly imported from utils."""

    def test_fix_date_importable_from_utils(self):
        """Verify fix_date can be imported from utils."""
        from app.core.utils import fix_date
        assert callable(fix_date)

    def test_fix_date_in_main_is_from_utils(self):
        """Verify that main.py uses fix_date from utils."""
        # Import both modules
        from app import main
        from app.core import utils

        # Both should reference the same function
        assert main.fix_date is utils.fix_date, \
            "main.fix_date should be imported from utils, not defined locally"


class TestFixDateFunctionality:
    """Test that the fix_date function works correctly."""

    def test_fix_date_converts_z_suffix(self):
        """Test that fix_date converts 'Z' suffix to UTC offset."""
        from app.core.utils import fix_date

        data = {"last_updated": "2024-01-15T10:30:00Z"}
        fix_date(data)

        assert isinstance(data["last_updated"], datetime)
        assert data["last_updated"].tzinfo is not None

    def test_fix_date_handles_existing_datetime(self):
        """Test that fix_date doesn't break when given a datetime object."""
        from app.core.utils import fix_date

        original_dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        data = {"last_updated": original_dt}
        fix_date(data)

        # Should remain unchanged
        assert data["last_updated"] == original_dt

    def test_fix_date_handles_missing_key(self):
        """Test that fix_date handles dicts without last_updated."""
        from app.core.utils import fix_date

        data = {"name": "test"}
        fix_date(data)

        # Should not raise and should not add last_updated
        assert "last_updated" not in data or data.get("last_updated") is None

    def test_fix_date_returns_dict(self):
        """Test that fix_date returns the modified dict."""
        from app.core.utils import fix_date

        data = {"last_updated": "2024-01-15T10:30:00Z"}
        result = fix_date(data)

        assert result is data

    def test_fix_date_with_utc_offset(self):
        """Test fix_date with an already-offset timestamp."""
        from app.core.utils import fix_date

        data = {"last_updated": "2024-01-15T10:30:00+00:00"}
        fix_date(data)

        assert isinstance(data["last_updated"], datetime)


class TestMainModuleImports:
    """Test that main.py imports are correct after cleanup."""

    def test_main_module_loads(self):
        """Verify main.py loads without errors."""
        from app import main
        assert main.app is not None

    def test_main_has_fix_date(self):
        """Verify main.py has access to fix_date."""
        from app import main
        assert hasattr(main, "fix_date")
        assert callable(main.fix_date)
