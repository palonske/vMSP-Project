"""
Tests for using the config constant for OCPI version.

This ensures that the version string comes from settings.OCPI_VERSION
rather than being hardcoded, making it easier to update versions in the future.
"""

import pytest
from unittest.mock import patch, MagicMock
from app.config import settings

pytestmark = pytest.mark.asyncio(loop_scope="function")


class TestVersionConfigUsage:
    """Test that version endpoints use the config constant."""

    def test_config_has_ocpi_version(self):
        """Verify that settings has an OCPI_VERSION attribute."""
        assert hasattr(settings, 'OCPI_VERSION')
        assert settings.OCPI_VERSION == "2.1.1"

    def test_config_version_is_string(self):
        """Verify that OCPI_VERSION is a string."""
        assert isinstance(settings.OCPI_VERSION, str)

    def test_config_version_format(self):
        """Verify that OCPI_VERSION follows semantic versioning format."""
        version = settings.OCPI_VERSION
        parts = version.split('.')
        assert len(parts) == 3, "Version should have 3 parts (major.minor.patch)"
        for part in parts:
            assert part.isdigit(), f"Version part '{part}' should be numeric"


class TestVersionEndpointResponses:
    """Test that version endpoint functions build URLs correctly."""

    async def test_emsp_version_url_uses_config(self):
        """Test that EMSP version URL uses config constant."""
        from app.api.emspversions import get_available_version

        # Create a mock request
        mock_request = MagicMock()

        # Run the async function
        result = await get_available_version(mock_request)

        # Check that the version in the response matches config
        assert result['data'][0]['version'] == settings.OCPI_VERSION
        assert settings.OCPI_VERSION in result['data'][0]['url']

    async def test_cpo_version_url_uses_config(self):
        """Test that CPO version URL uses config constant."""
        from app.api.cpoversions import get_available_version

        # Create a mock request
        mock_request = MagicMock()

        # Run the async function
        result = await get_available_version(mock_request)

        # Check that the version in the response matches config
        assert result['data'][0]['version'] == settings.OCPI_VERSION
        assert settings.OCPI_VERSION in result['data'][0]['url']

    async def test_emsp_version_details_uses_config(self):
        """Test that EMSP version details endpoint uses config constant."""
        from app.api.emspversions import get_211_version_details

        mock_request = MagicMock()

        result = await get_211_version_details(mock_request)

        # Check version in response
        assert result['data']['version'] == settings.OCPI_VERSION

        # Check all endpoint URLs contain the version
        for endpoint in result['data']['endpoints']:
            assert settings.OCPI_VERSION in endpoint['url'], \
                f"Endpoint {endpoint['identifier']} URL should contain version"

    async def test_cpo_version_details_uses_config(self):
        """Test that CPO version details endpoint uses config constant."""
        from app.api.cpoversions import get_211_version_details

        mock_request = MagicMock()

        result = await get_211_version_details(mock_request)

        # Check version in response
        assert result['data']['version'] == settings.OCPI_VERSION

        # Check all endpoint URLs contain the version
        for endpoint in result['data']['endpoints']:
            assert settings.OCPI_VERSION in endpoint['url'], \
                f"Endpoint {endpoint['identifier']} URL should contain version"


class TestVersionConfigChange:
    """Test that changing config would update all version references."""

    def test_version_change_propagates(self):
        """
        Demonstrate that if we change the config, URLs would update.
        This is a documentation test showing the benefit of using the config.
        """
        # Store original
        original_version = settings.OCPI_VERSION

        # The key assertion: all our code references settings.OCPI_VERSION
        # so if we change it, everything updates automatically
        #
        # In practice, you'd update the .env file or environment variable:
        # OCPI_VERSION=2.2.1
        #
        # And all endpoints would automatically use the new version.

        assert original_version == "2.1.1"

        # Note: We don't actually change the config in tests because:
        # 1. Pydantic settings are immutable after creation
        # 2. This would affect other tests
        # 3. The route paths in main.py still use hardcoded strings
        #
        # A full version change would also require:
        # - Updating route registrations in main.py
        # - Adding new version-specific module directories
        # - Maintaining backwards compatibility routes
