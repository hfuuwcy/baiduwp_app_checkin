# 百度网盘 App 端签到与任务上报

这是独立的百度网盘 App 端项目，只负责 App 端任务：

- App 连续签到
- App 每日答题
- App 会员等级与成长值查询
- `/api/taskscore/tasksave` 多任务上报
- 支持独立邮箱通知配置

网页端签到已经拆分到另一个项目，不再和 App 端共用代码、配置或 GitHub Actions。

## 安装

```bash
pip install -r requirements.txt
```

## 本地配置

复制账号配置示例：

```bash
copy config.example.json config.json
```

编辑 `config.json`：

```json
{
  "BAIDUWP_APP": [
    {
      "cookie": "BDUSS=xxxxxx; STOKEN=xxxxxx; ...",
      "enabled": true,
      "z": "从 App 抓包参数复制",
      "cuid": "从 App 抓包参数复制",
      "devuid": "从 App 抓包参数复制",
      "channel": ["android_15_xxx_bd-netdisk_xxx"],
      "version": "13.20.7",
      "versioncode": "4062",
      "clienttype": "1",
      "uk": "从 /api/taskscore/tasksave 的 uk 参数复制",
      "token": "从 /api/taskscore/tasksave 的 token 参数复制",
      "taskscore_tasks": [
        {
          "enabled": true,
          "name": "App广告观看任务",
          "task_id": "3434632741761030",
          "task_from": ["task_sys_task_growth"],
          "delay_seconds": 0,
          "extra_params": {
            "rand": "Apifox 成功请求里的 rand",
            "rand2": "Apifox 成功请求里的 rand2",
            "time": "Apifox 成功请求里的 time",
            "rchannel": "Apifox 成功请求里的 rchannel"
          }
        }
      ]
    }
  ]
}
```

多个任务继续追加到 `taskscore_tasks`。`cookie`、`uk`、`token`、`z`、`cuid`、`devuid` 是账号级参数，会被同一账号下的多个任务共享。

如果 `/api/taskscore/tasksave` 在 Apifox 里成功、但脚本返回“参数错误”，通常是因为 `z` 和 `rand` / `rand2` / `time` / `rchannel` 属于同一组反作弊参数。把 Apifox 成功请求里的这些值放进该任务的 `extra_params`，脚本会用它们覆盖自动生成的动态值。

邮箱配置单独放在 `email.json`：

```bash
copy email.example.json email.json
```

## 运行

```bash
python -m baiduwp_app_checkin
```

指定配置文件：

```bash
python -m baiduwp_app_checkin --config config.json --email-config email.json
```

只测试邮箱通知：

```bash
python -m baiduwp_app_checkin --test-email
```

## GitHub Actions

工作流在 `.github/workflows/checkin.yml`，默认每天北京时间 07:30 运行 App 端入口。

在仓库的 `Settings` -> `Secrets and variables` -> `Actions` -> `Secrets` 中新增：

- `BAIDUWP_APP_CONFIG`：完整 App 账号 JSON，内容可以按 `config.example.json` 填写。
- `BAIDUWP_APP_EMAIL_CONFIG`：完整邮箱 JSON，内容可以按 `email.example.json` 填写。

`BAIDUWP_APP_CONFIG` 可以配置多账号：

```json
{
  "BAIDUWP_APP": [
    {
      "cookie": "账号1 Cookie",
      "enabled": true,
      "z": "账号1 z",
      "cuid": "账号1 cuid",
      "devuid": "账号1 devuid",
      "uk": "账号1 uk",
      "token": "账号1 token",
      "taskscore_tasks": []
    },
    {
      "cookie": "账号2 Cookie",
      "enabled": true,
      "z": "账号2 z",
      "cuid": "账号2 cuid",
      "devuid": "账号2 devuid",
      "uk": "账号2 uk",
      "token": "账号2 token",
      "taskscore_tasks": []
    }
  ]
}
```

## 配置读取顺序

账号配置会按顺序读取：

- `--config` 指定的配置文件
- 环境变量 `BAIDUWP_APP_CONFIG` 或 `BAIDUWP_APP_CONFIG_JSON`
- 当前目录下的 `config.json`
- 当前目录下的 `config/config.json`

邮箱配置会按顺序读取：

- `--email-config` 指定的配置文件
- 环境变量 `BAIDUWP_APP_EMAIL_CONFIG` 或 `BAIDUWP_APP_EMAIL_CONFIG_JSON`
- 当前目录下的 `email.json`
- 当前目录下的 `config/email.json`

不要把本地 `config.json` 或 `email.json` 提交到仓库；它们已经被 `.gitignore` 忽略。
