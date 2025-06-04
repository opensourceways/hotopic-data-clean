import requests
from config.settings import settings


def login():
    try:
        url = settings.one_id_api
        response = requests.post(
            url,
            json={
                "permission": "sigRead",
                "account": settings.account,
                "client_id": settings.client_id,
                "accept_term": 0,
                "password": settings.password,
            })
        cookies_dict = response.cookies.get_dict()
        cookie_str = ";".join([f"{k}={v}" for k, v in cookies_dict.items()])
        token_str = cookies_dict.get('_U_T_', '')
        if not token_str:
            raise ValueError("Token字段_U_T_未找到")
        return cookie_str, token_str
    except Exception as e:
        print(f"Error: {e}")
        return None, None


def fetch_issue_data(community, dws_name, start_time):
    try:
        url = settings.data_api.format(community=community)
        cookie, token = login()
        if not cookie or not token:
            raise ValueError("登录失败")
        response = requests.post(
            url,
            params={
                "page": 1,
                "page_size": 100,
            },
            headers={
                "Cookie": cookie,
                "token": token,
            },
            json={
                "community": community,
                "dim": [],
                "name": dws_name,
                "page": 1,
                "page_size": 100,
                "filters": [{"column": "is_issue", "operator": "=", "value": "1"},
                              {"column": "created_at", "operator": ">", "value": start_time}],
                "conditonsLogic": "AND", "order_field": "uuid", "order_dir": "ASC"}
        )
        response.raise_for_status()
        print(response.json())
    except Exception as e:
        print(f"Error: {e}")
        return None
