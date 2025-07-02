import pytest
from unittest.mock import Mock, patch
import requests
from app.data_collect_clean.validator import (
    BaseValidator,
    IssueValidator,
    OpenUBMCForumValidator,
    CANNForumValidator,
    MailValidator,
    GetForumValidator
)


# Fixtures
@pytest.fixture
def mock_session(monkeypatch):
    mock = Mock()
    monkeypatch.setattr("requests.Session", Mock(return_value=mock))
    return mock


@pytest.fixture
def cann_settings():
    with patch("config.settings.settings") as mock_settings:
        mock_settings.forum_topic_detail_api = "http://mock-api.com/topic"
        yield mock_settings


# Base Validator Tests
class TestBaseValidator:
    def test_common_request_success(self, mock_session):
        mock_response = Mock(status_code=200)
        mock_session.get.return_value = mock_response

        validator = BaseValidator()
        response = validator._common_request("http://test.com")
        assert response == mock_response
        mock_session.get.assert_called_with(
            "http://test.com", headers=None, timeout=30
        )

    def test_common_request_failure(self, mock_session):
        mock_session.get.side_effect = requests.exceptions.Timeout()

        validator = BaseValidator()
        response = validator._common_request("http://test.com")
        assert response is None


# IssueValidator Tests
class TestIssueValidator:
    @pytest.mark.parametrize("url,expected_api", [
        ("https://gitcode.com/owner/repo/issues/123",
         "https://web-api.gitcode.com/api/v2/projects/owner%2Frepo"),
        ("https://gitee.com/user/proj/issues/456",
         "https://gitee.com/user/proj"),
    ])
    def test_url_parsing(self, mock_session, url, expected_api):
        mock_response = Mock(status_code=200)
        mock_session.get.return_value = mock_response

        validator = IssueValidator()
        result = validator.validate(url)

        mock_session.get.assert_called()
        assert any(expected_api in call[0][0] for call in mock_session.get.call_args_list)
        assert result is True

    def test_gitcode_validation_success(self, mock_session):
        mock_response = Mock(status_code=200)
        mock_session.get.return_value = mock_response

        validator = IssueValidator()
        result = validator.validate("https://gitcode.com/owner/repo/issues/1")
        assert result is True

    def test_gitee_validation_failure(self, mock_session):
        mock_response = Mock(status_code=404)
        mock_session.get.return_value = mock_response

        validator = IssueValidator()
        result = validator.validate("https://gitee.com/user/proj/issues/456")
        assert result is False


# CANNForumValidator Tests
class TestCANNForumValidator:
    def test_topic_id_extraction(self):
        validator = CANNForumValidator()
        url = "http://forum.com/topic-12345/123.htm"
        assert validator._extract_topic_id(url) == "12345"

    @patch("logging.error")
    def test_api_validation_success(self, mock_log, mock_session, cann_settings):
        mock_response = Mock()
        mock_response.json.return_value = {"data": {"valid": True}}
        mock_response.status_code = 200
        mock_session.get.return_value = mock_response

        validator = CANNForumValidator()
        result = validator.validate("topic-12345")

        mock_session.get.assert_called_with(
            "http://mock-api.com/topic",
            params={"topicId": "12345"},
            timeout=30
        )
        assert result is True
        mock_log.assert_not_called()

    def test_error_code_handling(self, mock_session, cann_settings):
        mock_response = Mock()
        mock_response.json.return_value = {"data": {"error_code": "HD.65120026"}}
        mock_response.status_code = 200
        mock_session.get.return_value = mock_response

        validator = CANNForumValidator()
        result = validator.validate("topic-12345")
        assert result is False

    @patch("logging.error")
    def test_exception_handling(self, mock_log, mock_session, cann_settings):
        mock_session.get.side_effect = Exception("Connection error")

        validator = CANNForumValidator()
        result = validator.validate("topic-12345")

        assert result is False
        mock_log.assert_called_with("CANN论坛验证异常: Connection error")


# OpenUBMCForumValidator Tests
class TestOpenUBMCForumValidator:
    def test_validation_success(self, mock_session):
        mock_response = Mock(status_code=200)
        mock_session.get.return_value = mock_response

        validator = OpenUBMCForumValidator()
        result = validator.validate("http://valid-post.com")
        assert result is True

    def test_validation_failure(self, mock_session):
        mock_response = Mock(status_code=404)
        mock_session.get.return_value = mock_response

        validator = OpenUBMCForumValidator()
        result = validator.validate("http://invalid-post.com")
        assert result is False


# MailValidator Tests
class TestMailValidator:
    def test_always_valid(self):
        validator = MailValidator()
        assert validator.validate("invalid@email") is True
        assert validator.validate("") is True
        assert validator.validate(None) is True


# Factory Tests
class TestValidatorFactory:
    def test_get_openubmc_validator(self):
        validator = GetForumValidator("openubmc")
        assert isinstance(validator, OpenUBMCForumValidator)

    def test_get_cann_validator(self):
        validator = GetForumValidator("cann")
        assert isinstance(validator, CANNForumValidator)

    def test_invalid_community(self):
        with pytest.raises(ValueError):
            GetForumValidator("unknown")


# Parametrized Tests
@pytest.mark.parametrize("url,expected", [
    ("https://gitcode.com/a/b/issues/1", True),
    ("https://gitee.com/c/d/issues/2", True),
    ("https://invalid.com/issue", False),
])
def test_issue_validator_flow(url, expected, mock_session):
    mock_session.get.return_value = Mock(status_code=200 if expected else 404)

    validator = IssueValidator()
    assert validator.validate(url) == expected


# Performance Tests
def test_concurrent_validation(mock_session):
    mock_session.get.return_value = Mock(status_code=200)

    validator = OpenUBMCForumValidator()
    # 模拟并发验证
    results = [validator.validate(f"http://post-{i}.com") for i in range(100)]

    assert all(results)
    assert mock_session.get.call_count == 100
