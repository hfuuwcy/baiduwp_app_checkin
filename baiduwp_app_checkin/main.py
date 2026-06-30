import argparse
import hashlib
import json
import logging
import secrets
import time
from typing import Any

import requests

from .common import load_accounts, load_email_config, normalize_email_config, send_email, setup_logging


LOGGER = logging.getLogger("baiduwp_app_checkin")


class BaiduWPApp:
    name = "百度网盘 App"

    def __init__(self, cookie: str, app_config: dict[str, Any], timeout: int = 30):
        if not cookie:
            raise ValueError("必须提供百度网盘 Cookie")
        if not isinstance(app_config, dict) or not app_config.get("enabled", False):
            raise ValueError("未启用 App 端配置")
        self.cookie = cookie
        self.app_config = app_config
        self.timeout = timeout
        self.session = requests.Session()
        self.headers = {
            "User-Agent": str(
                self.app_config.get("user_agent")
                or "netdisk;13.20.7;android;android-android;15;JSbridge4.4.0;jointBridge;1.1.0;"
            ),
            "Accept": "application/json, text/plain, */*",
            "Connection": "keep-alive",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Cookie": self.cookie,
        }

    @staticmethod
    def _param_value(value: Any) -> str:
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    @classmethod
    def _normalize_params(cls, params: dict[str, Any]) -> dict[str, str]:
        return {key: cls._param_value(value) for key, value in params.items() if value is not None}

    def _get(self, path: str, params: dict[str, Any]) -> tuple[int, Any, str]:
        response = self.session.get(
            f"https://pan.baidu.com{path}",
            headers=self.headers,
            params=self._normalize_params(params),
            timeout=self.timeout,
        )
        text = response.text
        try:
            data = response.json()
        except ValueError:
            data = None
        return response.status_code, data, text

    def _common_params(self) -> dict[str, Any]:
        missing = [key for key in ("z", "cuid", "devuid") if not self.app_config.get(key)]
        if missing:
            raise ValueError(f"App 端缺少配置: {', '.join(missing)}")

        rand = secrets.token_hex(20)
        params: dict[str, Any] = {
            "z": self.app_config["z"],
            "clienttype": str(self.app_config.get("clienttype", "1")),
            "channel": self.app_config.get("channel", "android_bd-netdisk"),
            "rand": rand,
            "rand2": secrets.token_hex(20),
            "time": str(int(time.time())),
            "cuid": self.app_config["cuid"],
            "devuid": self.app_config["devuid"],
            "version": self.app_config.get("version", "13.20.7"),
            "versioncode": str(self.app_config.get("versioncode", "4062")),
            "themeinfo": str(self.app_config.get("themeinfo", "0")),
            "rchannel": self.app_config.get("rchannel") or hashlib.md5(rand.encode()).hexdigest(),
            "app": self.app_config.get("app", "android"),
        }
        offlinepackage = self.app_config.get("offlinepackage")
        if offlinepackage:
            params["offlinepackage"] = offlinepackage
        return params

    def loginstatus(self) -> dict[str, Any]:
        status_code, data, _ = self._get("/api/loginstatus", self._common_params())
        if status_code != 200 or not isinstance(data, dict) or data.get("errno") not in (0, "0"):
            raise ValueError(f"App 登录状态查询失败: {status_code} {data}")
        login_info = data.get("login_info")
        return login_info if isinstance(login_info, dict) else {}

    def coin_signin(self, is_growth: int = 1) -> dict[str, Any]:
        params = self._common_params()
        task_id = str(self.app_config.get("coin_sign_task_id", "3434916321758720"))
        params.update(
            {
                "task_id": task_id,
                "task_id_str": task_id,
                "task_from": self.app_config.get("coin_sign_task_from", "task_sys_daily"),
                "is_growth": str(is_growth),
            }
        )
        status_code, data, _ = self._get("/coins/taskcenter/signin", params)
        if status_code != 200 or not isinstance(data, dict):
            raise ValueError(f"App 端签到请求失败: {status_code}")
        return data

    def coin_signin_list(self, is_growth: int = 1) -> dict[str, Any]:
        params = self._common_params()
        task_id = str(self.app_config.get("coin_sign_task_id", "3434916321758720"))
        params.update(
            {
                "task_id": task_id,
                "task_id_str": task_id,
                "task_from": self.app_config.get("coin_sign_task_from", "task_sys_daily"),
                "is_growth": str(is_growth),
            }
        )
        status_code, data, _ = self._get("/coins/taskcenter/signinlist", params)
        if status_code != 200 or not isinstance(data, dict):
            raise ValueError(f"App 端签到列表查询失败: {status_code}")
        return data

    def membership_user(self) -> dict[str, Any]:
        params = self._common_params()
        params["method"] = "query"
        status_code, data, _ = self._get("/rest/2.0/membership/user", params)
        if status_code != 200 or not isinstance(data, dict):
            raise ValueError(f"App 会员信息查询失败: {status_code}")
        level_info = data.get("level_info")
        return level_info if isinstance(level_info, dict) else {}

    def get_question(self) -> dict[str, Any]:
        status_code, data, _ = self._get("/act/v2/membergrowv2/getdailyquestion", self._common_params())
        if status_code != 200 or not isinstance(data, dict):
            raise ValueError(f"App 每日题目获取失败: {status_code}")
        question_info = data.get("data")
        return question_info if isinstance(question_info, dict) else {}

    def answer_question(self, ask_id: Any, answer: Any) -> dict[str, Any]:
        params = self._common_params()
        params.update({"ask_id": ask_id, "answer": answer})
        status_code, data, _ = self._get("/act/v2/membergrowv2/answerquestion", params)
        if status_code != 200 or not isinstance(data, dict):
            raise ValueError(f"App 每日答题提交失败: {status_code}")
        answer_info = data.get("data")
        return answer_info if isinstance(answer_info, dict) else {}

    def daily_question(self) -> str:
        question_info = self.get_question()
        ask_id = question_info.get("ask_id")
        answer = question_info.get("answer")
        question = question_info.get("question") or ""
        answer_status = question_info.get("answer_status")
        score = question_info.get("score")

        if not ask_id or answer is None:
            return "App每日答题: 未获取到题目"
        if answer_status == 1:
            return f"App每日答题: 已答题，得分{score or ''}，题目: {question}"

        answer_info = self.answer_question(ask_id, answer)
        answer_score = answer_info.get("score")
        show_msg = answer_info.get("show_msg") or ""
        return f"App每日答题: 提交完成，得分{answer_score or ''}{show_msg}，题目: {question}"

    def taskscore_save(
        self,
        task_id: Any,
        task_from: Any,
        label: str,
        extra_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        common_params = self._common_params()
        if extra_params:
            common_params.update(extra_params)
        uk = self.app_config.get("uk")
        token = self.app_config.get("token")
        missing = [key for key, value in {"uk": uk, "token": token}.items() if not value]
        if missing:
            raise ValueError(f"{label}缺少配置: {', '.join(missing)}")

        params: dict[str, Any] = {
            "uk": uk,
            "task_id": task_id,
            "task_from": task_from,
            "token": token,
            "z": common_params.get("z"),
            "clienttype": common_params.get("clienttype"),
            "channel": common_params.get("channel"),
            "rand": common_params.get("rand"),
            "rand2": common_params.get("rand2"),
            "time": common_params.get("time"),
            "cuid": common_params.get("cuid"),
            "devuid": common_params.get("devuid"),
            "version": common_params.get("version"),
            "versioncode": common_params.get("versioncode"),
        }
        if common_params.get("offlinepackage") is not None:
            params["offlinepackage"] = common_params["offlinepackage"]
        params.update(
            {
                "themeinfo": common_params.get("themeinfo"),
                "rchannel": common_params.get("rchannel"),
                "app": common_params.get("app"),
            }
        )
        status_code, data, text = self._get("/api/taskscore/tasksave", params)
        if status_code != 200 or not isinstance(data, dict):
            detail = data if data is not None else text[:200]
            raise ValueError(f"{label}失败: {status_code} {detail}")
        return data

    @staticmethod
    def taskscore_status(label: str, result: dict[str, Any]) -> str:
        errno = result.get("errno")
        error_code = result.get("error_code")
        message = result.get("errmsg") or result.get("error_msg") or result.get("show_msg")
        result_data = result.get("data")
        score = result.get("score")
        if score in (None, ""):
            score = result.get("points")
        if isinstance(result_data, dict):
            message = message or result_data.get("errmsg") or result_data.get("error_msg") or result_data.get("show_msg")
            if score in (None, ""):
                score = result_data.get("score")
            if score in (None, ""):
                score = result_data.get("points")

        details = []
        if score not in (None, ""):
            details.append(f"得分{score}")
        if message:
            details.append(str(message))
        suffix = f"（{'，'.join(details)}）" if details else ""

        if errno in (0, "0") or error_code in (0, "0"):
            return f"{label}: 成功{suffix}"
        if details:
            return f"{label}: 返回提示{suffix}"
        code = errno if errno is not None else error_code
        return f"{label}: 已请求，响应码{code if code is not None else '未知'}"

    def taskscore_task_configs(self) -> list[dict[str, Any]]:
        raw_tasks = self.app_config.get("taskscore_tasks") or self.app_config.get("tasksave_tasks") or []
        if not isinstance(raw_tasks, list):
            return []

        tasks = []
        for index, item in enumerate(raw_tasks, start=1):
            if not isinstance(item, dict):
                continue
            if item.get("enabled", True) is False:
                continue
            task = dict(item)
            task.setdefault("name", f"App任务上报{index}")
            tasks.append(task)
        return tasks

    def run_taskscore_task(self, task_config: dict[str, Any]) -> str:
        label = str(task_config.get("name") or "App任务上报")
        task_id = task_config.get("task_id")
        task_from = task_config.get("task_from") or ["task_sys_task_growth"]
        if not task_id:
            return f"{label}: 已跳过，缺少 task_id"

        delay_seconds = int(task_config.get("delay_seconds") or 0)
        if delay_seconds > 0:
            time.sleep(delay_seconds)

        extra_params = task_config.get("extra_params")
        if extra_params is not None and not isinstance(extra_params, dict):
            return f"{label}: 已跳过，extra_params 必须是对象"

        result = self.taskscore_save(
            task_id=task_id,
            task_from=task_from,
            label=label,
            extra_params=extra_params,
        )
        return self.taskscore_status(label, result)

    def run_taskscore_tasks(self) -> list[str]:
        results = []
        for task_config in self.taskscore_task_configs():
            label = str(task_config.get("name") or "App任务上报")
            try:
                results.append(self.run_taskscore_task(task_config))
            except Exception as exc:
                results.append(f"{label}: 执行失败: {exc}")
                LOGGER.exception("%s执行失败", label)
        return results

    @staticmethod
    def signin_status(signin_result: dict[str, Any], signin_info: dict[str, Any]) -> str:
        signed_today = signin_info.get("signed_today")
        if signed_today is True or signed_today == 1:
            return "已签到"

        errno = signin_result.get("errno")
        error_code = signin_result.get("error_code")
        errmsg = signin_result.get("errmsg") or signin_result.get("error_msg") or signin_result.get("show_msg")
        result_data = signin_result.get("data")
        if isinstance(result_data, dict):
            errmsg = errmsg or result_data.get("errmsg") or result_data.get("error_msg") or result_data.get("show_msg")
            if result_data.get("signed_today") is True or result_data.get("signed_today") == 1:
                return "已签到"

        if errno in (0, "0") or error_code in (0, "0"):
            if errmsg:
                return f"请求成功，列表未确认（{errmsg}）"
            return "请求成功，列表未确认"
        if errmsg:
            return f"请求已返回提示: {errmsg}"
        return "已请求，待确认"

    def run(self) -> str:
        login_info = self.loginstatus()
        before_level_info = self.membership_user()
        is_growth = int(self.app_config.get("is_growth", 1))
        signin_result = self.coin_signin(is_growth=is_growth)
        signin_list_data = self.coin_signin_list(is_growth=is_growth)
        question_result = self.daily_question()
        taskscore_results = self.run_taskscore_tasks()
        after_level_info = self.membership_user()

        signin_result_info = signin_result.get("data") if isinstance(signin_result, dict) else {}
        signin_info = signin_list_data.get("data") if isinstance(signin_list_data, dict) else {}
        if not isinstance(signin_result_info, dict):
            signin_result_info = {}
        if not isinstance(signin_info, dict):
            signin_info = {}

        signin_days = signin_info.get("signin_days") or signin_result_info.get("signin_days")
        signin_status = self.signin_status(signin_result, signin_info)
        current_level = after_level_info.get("current_level")
        current_value = after_level_info.get("current_value")
        before_value = before_level_info.get("current_value")
        growth_delta = ""
        if isinstance(before_value, int) and isinstance(current_value, int):
            delta = current_value - before_value
            growth_delta = f"（本次变化{delta:+d}）"
        username = login_info.get("username") or ""
        lines = [
            f"App账号{username}",
            f"App连续签到: {signin_status}",
            f"App签到天数: {signin_days or ''}",
            question_result,
        ]
        lines.extend(taskscore_results)
        lines.extend(
            [
                f"当前会员等级: {current_level if current_level is not None else ''}",
                f"当前成长值: {current_value if current_value is not None else ''}{growth_delta}",
            ]
        )
        return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="百度网盘 App 端签到与任务上报")
    parser.add_argument("-c", "--config", help="配置文件路径，默认自动查找 config.json")
    parser.add_argument("--email-config", help="邮箱配置文件路径，默认自动查找 email.json")
    parser.add_argument("--timeout", type=int, default=30, help="请求超时时间，默认 30 秒")
    parser.add_argument("--log-file", default="logs/baiduwp_app_checkin.log", help="日志文件路径")
    parser.add_argument("--no-email", action="store_true", help="禁用邮箱通知")
    parser.add_argument("--test-email", action="store_true", help="只测试邮箱通知，不执行 App 签到")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    log_path = setup_logging(args.log_file)
    accounts, _, loaded_config_path = load_accounts(args.config)
    email_data, loaded_email_config_path = load_email_config(args.email_config)
    if loaded_config_path:
        LOGGER.info("使用配置文件: %s", loaded_config_path)
    if loaded_email_config_path:
        LOGGER.info("使用邮箱配置文件: %s", loaded_email_config_path)
    LOGGER.info("日志文件: %s", log_path)

    if args.test_email:
        email_config = normalize_email_config(email_data)
        if not email_config:
            raise SystemExit("邮箱通知未启用或未配置，请在 email.json 中配置 enabled=true")
        send_email(
            email_config,
            "百度网盘 App 签到邮箱测试",
            (
                "这是一封 App 端测试邮件。\n\n"
                f"配置文件: {loaded_config_path}\n"
                f"邮箱配置文件: {loaded_email_config_path}\n"
                f"日志文件: {log_path}"
            ),
        )
        LOGGER.info("App 端邮箱测试完成")
        return

    if not accounts:
        raise SystemExit("未找到 App 账号配置，请提供 config.json 或 BAIDUWP_APP_CONFIG")

    content_list = []
    start_time = time.time()
    for index, account in enumerate(accounts, start=1):
        app_config = account.get("app")
        if not isinstance(app_config, dict) or not app_config.get("enabled", False):
            message = f"百度网盘 App 账号 {index}\n未启用，已跳过"
            content_list.append(message)
            LOGGER.info(message)
            continue
        try:
            result = BaiduWPApp(
                cookie=str(account["cookie"]),
                app_config=app_config,
                timeout=args.timeout,
            ).run()
            content_list.append(f"百度网盘 App 账号 {index}\n{result}")
            LOGGER.info("百度网盘 App 账号 %s 执行完成\n%s", index, result)
            print(result)
        except Exception as exc:
            content_list.append(f"百度网盘 App 账号 {index}\n执行失败: {exc}")
            LOGGER.exception("百度网盘 App 账号 %s 执行失败", index)

    elapsed = int(time.time() - start_time)
    content_list.append(f"任务用时: {elapsed} 秒\n日志文件: {log_path}")
    content = "\n\n".join(content_list)

    email_config = normalize_email_config(email_data)
    if email_config and not args.no_email:
        try:
            send_email(email_config, "百度网盘 App 签到通知", content)
        except Exception:
            LOGGER.exception("邮箱通知发送失败")
    elif args.no_email:
        LOGGER.info("已通过 --no-email 禁用邮箱通知")
    else:
        LOGGER.info("未启用邮箱通知")

    LOGGER.info("App 端任务结束，用时 %s 秒", elapsed)


if __name__ == "__main__":
    main()
