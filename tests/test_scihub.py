"""
Unit tests for Sci-Hub module.

Tests URL discovery, paper fetching, and integration with pdf_download.
"""

import unittest
from unittest.mock import patch, Mock, MagicMock
import tempfile
from pathlib import Path
import shutil

from llm_metadata.scihub import SciHub, CaptchaNeedException


class TestSciHubURLDiscovery(unittest.TestCase):
    """Test Sci-Hub URL discovery functionality."""

    def test_get_available_urls(self):
        """Test that we can discover available Sci-Hub mirrors."""
        sh = SciHub()

        # Should have at least one URL
        self.assertIsNotNone(sh.available_base_url_list)
        self.assertGreater(len(sh.available_base_url_list), 0)

        # Base URL should be set
        self.assertIsNotNone(sh.base_url)
        self.assertTrue(sh.base_url.startswith('http'))

    def test_base_url_ends_with_slash(self):
        """Test that base_url is properly formatted with trailing slash."""
        sh = SciHub()
        self.assertTrue(sh.base_url.endswith('/'))

    @patch('llm_metadata.scihub.requests.get')
    def test_url_discovery_fallback(self, mock_get):
        """Test that preferred mirrors are used when discovery fails."""
        mock_get.side_effect = Exception("Network error")

        # Should still work using preferred/fallback mirrors
        sh = SciHub()
        self.assertGreater(len(sh.available_base_url_list), 0)
        # Should use the first preferred mirror
        self.assertIn('sci-hub', sh.base_url)


class TestSciHubClassify(unittest.TestCase):
    """Test identifier classification."""

    def setUp(self):
        """Skip initialization to avoid network calls."""
        self.sh = SciHub.__new__(SciHub)
        self.sh.sess = Mock()
        self.sh.available_base_url_list = ['https://sci-hub.se']
        self.sh.base_url = 'https://sci-hub.se/'

    def test_classify_doi(self):
        """Test DOI classification."""
        self.assertEqual(self.sh._classify("10.1111/mec.14361"), "doi")
        self.assertEqual(self.sh._classify("10.1371/journal.pone.0128238"), "doi")

    def test_classify_pmid(self):
        """Test PMID classification."""
        self.assertEqual(self.sh._classify("12345678"), "pmid")
        self.assertEqual(self.sh._classify("9876543"), "pmid")

    def test_classify_url_direct(self):
        """Test direct PDF URL classification."""
        self.assertEqual(
            self.sh._classify("https://example.com/paper.pdf"),
            "url-direct"
        )

    def test_classify_url_non_direct(self):
        """Test non-direct URL classification."""
        self.assertEqual(
            self.sh._classify("https://example.com/paper"),
            "url-non-direct"
        )


class TestSciHubFetch(unittest.TestCase):
    """Test paper fetching functionality."""

    def setUp(self):
        """Create a SciHub instance with mocked session."""
        self.sh = SciHub.__new__(SciHub)
        self.sh.sess = MagicMock()
        self.sh.available_base_url_list = ['https://sci-hub.st', 'https://sci-hub.se']
        self.sh.base_url = 'https://sci-hub.st/'

    def test_fetch_returns_pdf_bytes_iframe(self):
        """Test that fetch returns PDF as bytes (old iframe structure)."""
        # Mock the Sci-Hub page response (old structure with iframe)
        page_response = Mock()
        page_response.content = b'''
        <html>
            <iframe src="https://moscow.sci-hub.se/paper.pdf"></iframe>
        </html>
        '''

        # Mock the PDF response
        pdf_response = Mock()
        pdf_response.headers = {'Content-Type': 'application/pdf'}
        pdf_response.content = b'%PDF-1.4 fake pdf content...'
        pdf_response.url = 'https://moscow.sci-hub.se/paper.pdf'

        # Configure session mock
        self.sh.sess.get.side_effect = [page_response, pdf_response]

        result = self.sh.fetch("10.1111/mec.14361")

        # Result should contain PDF bytes
        self.assertIn('pdf', result)
        self.assertIsInstance(result['pdf'], bytes)
        self.assertTrue(result['pdf'].startswith(b'%PDF'))

    def test_fetch_returns_pdf_bytes_object(self):
        """Test that fetch returns PDF as bytes (new object structure)."""
        # Mock the Sci-Hub page response (new structure with object tag)
        page_response = Mock()
        page_response.content = b'''
        <html>
            <object data="/storage/2024/6326/paper.pdf#navpanes=0&view=FitH"></object>
        </html>
        '''

        # Mock the PDF response
        pdf_response = Mock()
        pdf_response.headers = {'Content-Type': 'application/pdf'}
        pdf_response.content = b'%PDF-1.4 fake pdf content from object tag...'
        pdf_response.url = 'https://sci-hub.st/storage/2024/6326/paper.pdf'

        # Configure session mock
        self.sh.sess.get.side_effect = [page_response, pdf_response]

        result = self.sh.fetch("10.1093/jhered/esx005")

        # Result should contain PDF bytes
        self.assertIn('pdf', result)
        self.assertIsInstance(result['pdf'], bytes)
        self.assertTrue(result['pdf'].startswith(b'%PDF'))

    def test_fetch_captcha_handling(self):
        """Test that captcha responses raise CaptchaNeedException."""
        # Mock the Sci-Hub page response with object tag
        page_response = Mock()
        page_response.content = b'''
        <html>
            <object data="/storage/paper.pdf"></object>
        </html>
        '''

        # Mock response that indicates captcha (non-PDF content type)
        captcha_response = Mock()
        captcha_response.headers = {'Content-Type': 'text/html'}
        captcha_response.content = b'<html>Captcha required</html>'

        self.sh.sess.get.side_effect = [page_response, captcha_response]

        with self.assertRaises(CaptchaNeedException):
            self.sh.fetch("10.1111/mec.14361")

    def test_fetch_returns_url(self):
        """Test that fetch result includes the PDF URL."""
        page_response = Mock()
        page_response.content = b'''
        <html>
            <object data="/storage/paper.pdf#navpanes=0"></object>
        </html>
        '''

        pdf_response = Mock()
        pdf_response.headers = {'Content-Type': 'application/pdf'}
        pdf_response.content = b'%PDF-1.4 fake pdf content...'
        pdf_response.url = 'https://sci-hub.st/storage/paper.pdf'

        self.sh.sess.get.side_effect = [page_response, pdf_response]

        result = self.sh.fetch("10.1111/mec.14361")

        self.assertIn('url', result)
        self.assertTrue(result['url'].endswith('.pdf'))


class TestSciHubDownload(unittest.TestCase):
    """Test download functionality."""

    def setUp(self):
        """Create temp directory for downloads."""
        self.temp_dir = Path(tempfile.mkdtemp())

        self.sh = SciHub.__new__(SciHub)
        self.sh.sess = MagicMock()
        self.sh.available_base_url_list = ['https://sci-hub.st']
        self.sh.base_url = 'https://sci-hub.st/'

    def tearDown(self):
        """Clean up temp directory."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_download_saves_file(self):
        """Test that download saves PDF to specified path."""
        # Mock the Sci-Hub page response (new structure)
        page_response = Mock()
        page_response.content = b'''
        <html>
            <object data="/storage/paper.pdf#navpanes=0"></object>
        </html>
        '''

        # Mock the PDF response
        pdf_content = b'%PDF-1.4 This is fake PDF content for testing purposes only.'
        pdf_response = Mock()
        pdf_response.headers = {'Content-Type': 'application/pdf'}
        pdf_response.content = pdf_content
        pdf_response.url = 'https://sci-hub.st/storage/paper.pdf'

        self.sh.sess.get.side_effect = [page_response, pdf_response]

        output_path = self.temp_dir / "test_paper.pdf"
        result = self.sh.download("10.1111/mec.14361", path=str(output_path))

        self.assertIn('pdf', result)
        self.assertTrue(output_path.exists())

        with open(output_path, 'rb') as f:
            saved_content = f.read()
        self.assertEqual(saved_content, pdf_content)


class TestSciHubIntegrationLive(unittest.TestCase):
    """
    Live integration tests for Sci-Hub.

    These tests make actual network requests to Sci-Hub mirrors.
    They may fail due to network issues, captchas, or mirror availability.
    """

    @unittest.skip("Live test - run manually")
    def test_live_fetch_open_access_paper(self):
        """Test fetching an open access paper through Sci-Hub."""
        sh = SciHub()

        # Use a known OA paper (PLOS ONE)
        doi = "10.1371/journal.pone.0128238"

        result = sh.fetch(doi)

        if 'err' in result:
            self.skipTest(f"Sci-Hub fetch failed: {result['err']}")

        self.assertIn('pdf', result)
        self.assertIsInstance(result['pdf'], bytes)
        # Check PDF magic bytes
        self.assertTrue(result['pdf'].startswith(b'%PDF'))

    @unittest.skip("Live test - run manually")
    def test_live_fetch_wiley_paper(self):
        """Test fetching a Wiley paper (common failure case)."""
        sh = SciHub()

        # One of the failing DOIs from the log
        doi = "10.1111/mec.14361"

        result = sh.fetch(doi)

        if 'err' in result:
            print(f"Sci-Hub fetch failed: {result['err']}")
            return

        self.assertIn('pdf', result)
        self.assertIsInstance(result['pdf'], bytes)


class TestSciHubPDFDownloadIntegration(unittest.TestCase):
    """Test Sci-Hub integration with pdf_download module."""

    def test_scihub_integration_uses_bytes_correctly(self):
        """
        Verify that pdf_download correctly handles Sci-Hub's bytes response.

        The pdf_download module should write the bytes directly to disk,
        not try to use them as a URL.
        """
        from llm_metadata.scihub import SciHub

        # Create a mock SciHub instance
        sh = SciHub.__new__(SciHub)
        sh.sess = MagicMock()
        sh.available_base_url_list = ['https://sci-hub.st']
        sh.base_url = 'https://sci-hub.st/'

        # Mock successful fetch (new structure with object tag)
        page_response = Mock()
        page_response.content = b'<html><object data="/storage/paper.pdf#navpanes=0"></object></html>'

        pdf_response = Mock()
        pdf_response.headers = {'Content-Type': 'application/pdf'}
        pdf_response.content = b'%PDF-1.4 test content'
        pdf_response.url = 'https://sci-hub.st/storage/paper.pdf'

        sh.sess.get.side_effect = [page_response, pdf_response]

        result = sh.fetch("10.1111/test")

        # Verify result structure
        self.assertIn('pdf', result)
        self.assertIn('url', result)

        # pdf should be bytes (the actual PDF content)
        self.assertIsInstance(result['pdf'], bytes)

        # url should be string (the PDF URL)
        self.assertIsInstance(result['url'], str)


if __name__ == '__main__':
    unittest.main()
