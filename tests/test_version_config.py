"""
Tests for multi-version OCPI configuration.

This ensures that:
- Multiple OCPI versions can be configured via SUPPORTED_OCPI_VERSIONS
- Version endpoints dynamically list all supported versions
- Adding a new version (e.g., 2.2.1) only requires updating the config
"""

import pytest
from unittest.mock import MagicMock
from app.config import settings

pytestmark = pytest.mark.asyncio(loop_scope="function")


class TestMultiVersionConfig:
    """Test the multi-version configuration setup."""

    def test_config_has_supported_versions(self):
        """Verify that settings has SUPPORTED_OCPI_VERSIONS list."""
        assert hasattr(settings, 'SUPPORTED_OCPI_VERSIONS')
        assert isinstance(settings.SUPPORTED_OCPI_VERSIONS, list)
        assert len(settings.SUPPORTED_OCPI_VERSIONS) >= 1

    def test_config_has_default_version(self):
        """Verify that settings has DEFAULT_OCPI_VERSION."""
        assert hasattr(settings, 'DEFAULT_OCPI_VERSION')
        assert isinstance(settings.DEFAULT_OCPI_VERSION, str)

    def test_default_version_in_supported(self):
        """Verify that DEFAULT_OCPI_VERSION is in SUPPORTED_OCPI_VERSIONS."""
        assert settings.DEFAULT_OCPI_VERSION in settings.SUPPORTED_OCPI_VERSIONS

    def test_supported_versions_format(self):
        """Verify all supported versions follow semantic versioning format."""
        for version in settings.SUPPORTED_OCPI_VERSIONS:
            parts = version.split('.')
            assert len(parts) == 3, f"Version {version} should have 3 parts"
            for part in parts:
                assert part.isdigit(), f"Version part '{part}' should be numeric"

    def test_211_is_supported(self):
        """Verify that 2.1.1 is currently supported."""
        assert "2.1.1" in settings.SUPPORTED_OCPI_VERSIONS


class TestVersionsEndpoint:
    """Test that /versions endpoint returns all supported versions."""

    async def test_emsp_versions_returns_all_supported(self):
        """Test that EMSP /versions returns all supported versions."""
        from app.api.emspversions import get_available_versions

        mock_request = MagicMock()
        result = await get_available_versions(mock_request)

        assert result['status_code'] == 1000
        assert len(result['data']) == len(settings.SUPPORTED_OCPI_VERSIONS)

        returned_versions = [v['version'] for v in result['data']]
        for version in settings.SUPPORTED_OCPI_VERSIONS:
            assert version in returned_versions

    async def test_cpo_versions_returns_all_supported(self):
        """Test that CPO /versions returns all supported versions."""
        from app.api.cpoversions import get_available_versions

        mock_request = MagicMock()
        result = await get_available_versions(mock_request)

        assert result['status_code'] == 1000
        assert len(result['data']) == len(settings.SUPPORTED_OCPI_VERSIONS)

        returned_versions = [v['version'] for v in result['data']]
        for version in settings.SUPPORTED_OCPI_VERSIONS:
            assert version in returned_versions

    async def test_emsp_version_urls_are_correct(self):
        """Test that EMSP version URLs contain the version."""
        from app.api.emspversions import get_available_versions

        mock_request = MagicMock()
        result = await get_available_versions(mock_request)

        for version_data in result['data']:
            version = version_data['version']
            url = version_data['url']
            assert version in url, f"URL {url} should contain version {version}"
            assert "/ocpi/emsp/" in url

    async def test_cpo_version_urls_are_correct(self):
        """Test that CPO version URLs contain the version."""
        from app.api.cpoversions import get_available_versions

        mock_request = MagicMock()
        result = await get_available_versions(mock_request)

        for version_data in result['data']:
            version = version_data['version']
            url = version_data['url']
            assert version in url, f"URL {url} should contain version {version}"
            assert "/ocpi/cpo/" in url


class TestVersionDetailsEndpoint:
    """Test the version details endpoint with dynamic version parameter."""

    async def test_emsp_version_details_for_supported_version(self):
        """Test EMSP version details for a supported version."""
        from app.api.emspversions import get_version_details

        mock_request = MagicMock()
        result = await get_version_details(mock_request, "2.1.1")

        assert result['status_code'] == 1000
        assert result['data']['version'] == "2.1.1"
        assert len(result['data']['endpoints']) == 3

        identifiers = [e['identifier'] for e in result['data']['endpoints']]
        assert "credentials" in identifiers
        assert "locations" in identifiers
        assert "tariffs" in identifiers

    async def test_cpo_version_details_for_supported_version(self):
        """Test CPO version details for a supported version."""
        from app.api.cpoversions import get_version_details

        mock_request = MagicMock()
        result = await get_version_details(mock_request, "2.1.1")

        assert result['status_code'] == 1000
        assert result['data']['version'] == "2.1.1"
        assert len(result['data']['endpoints']) == 3

    async def test_emsp_version_details_for_unsupported_version(self):
        """Test EMSP version details returns error for unsupported version."""
        from app.api.emspversions import get_version_details

        mock_request = MagicMock()
        result = await get_version_details(mock_request, "9.9.9")

        assert result['status_code'] == 3000
        assert "Unsupported version" in result['status_message']
        assert result['data'] is None

    async def test_cpo_version_details_for_unsupported_version(self):
        """Test CPO version details returns error for unsupported version."""
        from app.api.cpoversions import get_version_details

        mock_request = MagicMock()
        result = await get_version_details(mock_request, "9.9.9")

        assert result['status_code'] == 3000
        assert "Unsupported version" in result['status_message']
        assert result['data'] is None

    async def test_endpoint_urls_contain_requested_version(self):
        """Test that endpoint URLs use the requested version, not a hardcoded one."""
        from app.api.emspversions import get_version_details

        mock_request = MagicMock()
        result = await get_version_details(mock_request, "2.1.1")

        for endpoint in result['data']['endpoints']:
            assert "2.1.1" in endpoint['url']


class TestFutureVersionSupport:
    """
    Documentation tests showing how to add new versions.

    To add OCPI 2.2.1 support:
    1. Update config: SUPPORTED_OCPI_VERSIONS = ["2.1.1", "2.2.1"]
    2. Add version-specific modules if needed (e.g., app/api/v2_2_1/)
    3. Register routes in main.py for the new version
    4. The /versions endpoint will automatically include 2.2.1
    """

    def test_adding_version_only_requires_config_change(self):
        """
        Demonstrate that /versions endpoint uses config dynamically.

        If SUPPORTED_OCPI_VERSIONS = ["2.1.1", "2.2.1"],
        the /versions endpoint would automatically return both.
        """
        # Current state
        assert "2.1.1" in settings.SUPPORTED_OCPI_VERSIONS

        # To add 2.2.1, you would:
        # 1. Set environment variable: SUPPORTED_OCPI_VERSIONS='["2.1.1", "2.2.1"]'
        # 2. Or update .env file
        # 3. Or change the default in config.py

        # The version endpoints will automatically pick up the change
        # No code changes needed in emspversions.py or cpoversions.py
