import pytest
from unittest.mock import patch, mock_open
import os
import yaml
from config.settings import Settings


# Fixtures
@pytest.fixture
def mock_base_config():
    return {
        "LLM_API_URL": "https://api.example.com",
        "LLM_MODEL": "gpt-4",
        "CANN_FORUM_PROMPT": "CANN论坛提示词",
        "OPENUBMC_FORUM_PROMPT": "OpenUBMC论坛提示词"
    }


@pytest.fixture
def mock_secret_config():
    return {
        "APP_ENV": "production",
        "ACCOUNT": "admin",
        "DB_PASSWORD": "secure_password",
        "LLM_API_KEY": "sk-123456"
    }


@pytest.fixture
def mock_env(monkeypatch, tmp_path):
    # 创建临时配置文件
    base_conf = tmp_path / "conf.yaml"
    base_conf.write_text("base_config: test")

    secret_conf = tmp_path / "secret.yaml"
    secret_conf.write_text("secret: data")

    monkeypatch.setenv("SECRET_CONFIG", str(secret_conf))
    return tmp_path


# Positive Tests
class TestSettingsSuccess:
    def test_full_initialization(self, mock_env, mock_base_config, mock_secret_config):
        # 模拟配置文件内容
        mocked_yaml = mock_open(read_data=yaml.dump(mock_base_config))
        mocked_yaml_secret = mock_open(read_data=yaml.dump(mock_secret_config))

        with patch("builtins.open", side_effect=[mocked_yaml.return_value, mocked_yaml_secret.return_value]):
            instance = Settings()

            # 验证基础配置
            assert instance.llm_api_url == mock_base_config["LLM_API_URL"]
            assert instance.cann_forum_prompt == mock_base_config["CANN_FORUM_PROMPT"]

            # 验证密钥配置
            assert instance.account == mock_secret_config["ACCOUNT"]
            assert instance.db_password == mock_secret_config["DB_PASSWORD"]
            assert instance.env == "production"

    def test_partial_config(self, mock_env):
        # 模拟不完全配置
        partial_config = {"LLM_MODEL": "gpt-3.5"}
        with patch("yaml.safe_load", side_effect=[partial_config, {}]):
            instance = Settings()
            assert instance.llm_model == "gpt-3.5"
            assert instance.llm_api_url is None


# Negative Tests
class TestSettingsFailure:
    def test_missing_secret_env(self, monkeypatch):
        monkeypatch.delenv("SECRET_CONFIG", raising=False)
        with pytest.raises(ValueError) as excinfo:
            Settings()
        assert "SECRET_CONFIG environment variable" in str(excinfo.value)

    def test_invalid_yaml_format(self, mock_env):
        with patch("builtins.open", mock_open(read_data="invalid: yaml: data")):
            with pytest.raises(yaml.YAMLError):
                Settings()

    def test_missing_config_file(self, monkeypatch):
        monkeypatch.setenv("SECRET_CONFIG", "/non/existent/path.yaml")
        with pytest.raises(FileNotFoundError):
            Settings()


# Edge Cases
class TestEdgeCases:
    def test_empty_config_files(self, mock_env):
        with patch("yaml.safe_load", side_effect=[{}, {}]):
            instance = Settings()
            assert instance.llm_api_url is None
            assert instance.account is None

    def test_special_characters(self, mock_env):
        special_config = {
            "PASSWORD": "p@ssw0rd!",
            "DB_HOST": "db-01.example.com"
        }
        with patch("yaml.safe_load", side_effect=[{}, special_config]):
            instance = Settings()
            assert instance.password == "p@ssw0rd!"
            assert instance.db_host == "db-01.example.com"


# Logging Tests
class TestLogging:
    def test_config_logging(self, mock_env, caplog):
        test_config = {"APP_ENV": "staging"}
        with patch("yaml.safe_load", side_effect=[{}, test_config]):
            with caplog.at_level(logging.INFO):
                Settings()

            assert "secret_config_path" in caplog.text
            assert "APP_ENV" in caplog.text


# Singleton Test
def test_singleton_pattern():
    instance1 = Settings()
    instance2 = Settings()
    assert instance1 is not instance2  # 验证不是单例模式


# Integration Tests
class TestRealFiles:
    def test_with_real_yaml(self, tmp_path):
        # 准备真实配置文件
        base_conf = tmp_path / "conf.yaml"
        base_content = {"LLM_MODEL": "test-model"}
        with open(base_conf, 'w') as f:
            yaml.dump(base_content, f)

        secret_conf = tmp_path / "secret.yaml"
        secret_content = {"ACCOUNT": "test-user"}
        with open(secret_conf, 'w') as f:
            yaml.dump(secret_content, f)

        # 执行测试
        with patch("os.path.dirname", return_value=str(tmp_path)):
            os.environ["SECRET_CONFIG"] = str(secret_conf)
            instance = Settings()
            assert instance.llm_model == "test-model"
            assert instance.account == "test-user"


# Property Type Tests
@pytest.mark.parametrize("property_name, expected_type", [
    ("llm_api_url", str),
    ("db_port", str),
    ("env", str)
])
def test_property_types(property_name, expected_type, mock_env):
    with patch("yaml.safe_load", side_effect=[{}, {}]):
        instance = Settings()
        assert isinstance(getattr(instance, property_name), expected_type)
