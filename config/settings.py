import os
import yaml


class Settings:
    def __init__(self):
        config_path_env = os.getenv("CONFIG_PATH")
        if not config_path_env:
            raise ValueError("CONFIG_PATH environment variable is not set.")
        with open(config_path_env, 'r', encoding="utf-8") as config_file:
            config = yaml.safe_load(config_file)
            self.env: str = config.get("APP_ENV")
            self.account: str = config.get("ACCOUNT")
            self.password: str = config.get("PASSWORD")
            self.client_id: str = config.get("CLIENT_ID")
            self.data_api: str = config.get("DATA_API")
            self.one_id_api: str = config.get("ONE_ID_API")
            self.cann_forum_api: str = config.get("CANN_FORUM_API")
            self.cann_forum_topic_detail_api: str = config.get("CANN_FORUM_TOPIC_DETAIL_API")

        # os.remove(config_path_env)


settings = Settings()
