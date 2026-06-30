import json
import logging
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger("baiduwp_app_checkin")
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def setup_logging(log_file: str) -> Path:
    log_path = Path(log_file)
    if not log_path.is_absolute():
        log_path = PROJECT_ROOT / log_path
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    return log_path


def load_json_file(path: str | Path) -> Any:
    with open(path, encoding="utf-8") as file:
        return json.load(file)


def find_config_path(config_path: str | None, default_name: str) -> Path | None:
    if config_path:
        path = Path(config_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path if path.exists() else None

    candidate_paths = [
        Path.cwd() / default_name,
        Path.cwd() / "config" / default_name,
        PROJECT_ROOT / default_name,
        PROJECT_ROOT / "config" / default_name,
    ]
    for path in candidate_paths:
        if path.exists():
            return path
    return None


def load_env_json(*env_names: str) -> tuple[Any, str | None]:
    for env_name in env_names:
        env_value = os.getenv(env_name, "").strip()
        if env_value:
            return json.loads(env_value), env_name
    return None, None


def app_config_from_account(item: dict[str, Any]) -> dict[str, Any]:
    if isinstance(item.get("app"), dict):
        app_config = dict(item["app"])
    else:
        app_config = {key: value for key, value in item.items() if key != "cookie"}
    app_config.setdefault("enabled", True)
    return app_config


def normalize_app_accounts(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict) and isinstance(data.get("BAIDUWP_APP"), list):
        accounts = data["BAIDUWP_APP"]
    elif isinstance(data, dict) and isinstance(data.get("BAIDUWP"), list):
        accounts = data["BAIDUWP"]
    elif isinstance(data, list):
        accounts = data
    elif isinstance(data, dict) and data.get("cookie"):
        accounts = [data]
    else:
        accounts = []

    result = []
    for item in accounts:
        if not isinstance(item, dict):
            continue
        cookie = str(item.get("cookie", "")).strip()
        if not cookie:
            continue
        result.append({"cookie": cookie, "app": app_config_from_account(item)})
    return result


def load_config(config_path: str | None) -> tuple[Any, Path | str | None]:
    if config_path:
        path = find_config_path(config_path, "config.json")
        if not path:
            return None, None
        return load_json_file(path), path

    env_config, env_name = load_env_json("BAIDUWP_APP_CONFIG", "BAIDUWP_APP_CONFIG_JSON")
    if env_config is not None:
        return env_config, env_name

    path = find_config_path(None, "config.json")
    if not path:
        return None, None
    return load_json_file(path), path


def load_accounts(config_path: str | None) -> tuple[list[dict[str, Any]], Any, Path | str | None]:
    config_data, loaded_config_path = load_config(config_path)
    if config_data is not None:
        return normalize_app_accounts(config_data), config_data, loaded_config_path

    env_value = os.getenv("BAIDUWP_APP", "").strip()
    if env_value:
        return normalize_app_accounts(json.loads(env_value)), None, "BAIDUWP_APP"

    return [], config_data, loaded_config_path


def load_email_config(email_config_path: str | None) -> tuple[Any, Path | str | None]:
    if email_config_path:
        path = find_config_path(email_config_path, "email.json")
        if not path:
            return None, None
        return load_json_file(path), path

    env_config, env_name = load_env_json("BAIDUWP_APP_EMAIL_CONFIG", "BAIDUWP_APP_EMAIL_CONFIG_JSON")
    if env_config is not None:
        return env_config, env_name

    path = find_config_path(None, "email.json")
    if not path:
        return None, None
    return load_json_file(path), path


def normalize_email_config(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    config = data.get("EMAIL") or data.get("SMTP") or data
    if not isinstance(config, dict):
        return {}
    if not config.get("enabled", False):
        return {}
    return config


def email_recipients(config: dict[str, Any]) -> list[str]:
    recipients = config.get("to_addrs") or config.get("to_addr") or []
    if isinstance(recipients, str):
        recipients = [item.strip() for item in recipients.split(",")]
    return [str(item).strip() for item in recipients if str(item).strip()]


def send_email(config: dict[str, Any], subject: str, content: str) -> None:
    host = str(config.get("smtp_host", "")).strip()
    port = int(config.get("smtp_port", 465))
    username = str(config.get("smtp_user", "")).strip()
    password_env = str(config.get("smtp_password_env", "")).strip()
    password = str(config.get("smtp_password", "") or (os.getenv(password_env, "") if password_env else "")).strip()
    from_addr = str(config.get("from_addr", "") or username).strip()
    recipients = email_recipients(config)

    if not host or not from_addr or not recipients:
        LOGGER.warning("邮箱通知配置不完整，已跳过发送")
        return

    message = EmailMessage()
    message["Subject"] = str(config.get("subject") or subject)
    message["From"] = from_addr
    message["To"] = ", ".join(recipients)
    message.set_content(content)

    use_ssl = bool(config.get("use_ssl", port == 465))
    use_tls = bool(config.get("use_tls", not use_ssl))

    if use_ssl:
        with smtplib.SMTP_SSL(host, port, timeout=30) as smtp:
            if username:
                smtp.login(username, password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            if use_tls:
                smtp.starttls()
            if username:
                smtp.login(username, password)
            smtp.send_message(message)

    LOGGER.info("邮箱通知已发送给 %s", ", ".join(recipients))
