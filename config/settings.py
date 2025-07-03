import logging
import os
import yaml


class Settings:
    def __init__(self):
        base_config_path = os.path.join(os.path.dirname(__file__), "conf.yaml")
        with open(base_config_path, 'r', encoding="utf-8") as f:
            config = yaml.safe_load(f)
            self.llm_api_url: str = config.get("LLM_API_URL")
            self.llm_model: str = config.get("LLM_MODEL")
            self.cann_forum_prompt: str = config.get("CANN_FORUM_PROMPT")
            self.cann_issue_prompt: str = config.get("CANN_ISSUE_PROMPT")
            self.openubmc_forum_prompt: str = config.get("OPENUBMC_FORUM_PROMPT")
            self.openubmc_issue_prompt: str = config.get("OPENUBMC_ISSUE_PROMPT")
            self.opengauss_mail_prompt: str = config.get("OPENGAUSS_MAIL_PROMPT")
            self.opengauss_issue_prompt: str = config.get("OPENGAUSS_ISSUE_PROMPT")
            self.mindspore_forum_prompt: str = config.get("MINDSPORE_FORUM_PROMPT")
            self.mindspore_issue_prompt: str = config.get("MINDSPORE_ISSUE_PROMPT")
            self.openeuler_forum_prompt: str = config.get("OPENEULER_FORUM_PROMPT")
            self.openeuler_issue_prompt: str = config.get("OPENEULER_ISSUE_PROMPT")
            self.openeuler_mail_prompt: str = config.get("OPENEULER_MAIL_PROMPT")

        secret_config_path = os.getenv("SECRET_CONFIG")
        if not secret_config_path:
            raise ValueError("SECRET_CONFIG environment variable is not set.")
        logging.info("secret_config_path: %s", secret_config_path)
        with open(secret_config_path, 'r', encoding="utf-8") as config_file:
            config = yaml.safe_load(config_file)
            logging.info(f"config: {config}, type : {type(config)}")
            self.env = config.get("APP_ENV")
            self.account: str = config.get("ACCOUNT")
            self.password: str = config.get("PASSWORD")
            self.client_id: str = config.get("CLIENT_ID")
            self.data_api: str = config.get("DATA_API")
            self.one_id_api: str = config.get("ONE_ID_API")
            self.forum_api: str = config.get("FORUM_API")
            self.forum_topic_detail_api: str = config.get("FORUM_DETAIL_API")
            self.llm_api_key: str = config.get("LLM_API_KEY")
            self.community: str = config.get("COMMUNITY")
            self.dws_name: str = config.get("DWS_NAME")
            self.mail_dws_name: str = config.get("MAIL_DWS_NAME")
            self.db_user: str = config.get("DB_USER")
            self.db_password: str = config.get("DB_PASSWORD")
            self.db_host: str = config.get("DB_HOST")
            self.db_port: str = config.get("DB_PORT")
            self.db_name: str = config.get("DB_NAME")


settings = Settings()
