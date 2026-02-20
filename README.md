# 合规注册流程自动化模板

本仓库提供的是**合规用途**模板：
- 仅用于你拥有/获授权的网站注册流程测试。
- 不包含绕过风控、批量滥用、验证码破解等能力。

## 文件

- `compliant_registration_template.py`：Playwright 自动化脚本模板。

## 快速开始

1. 安装依赖：

```bash
pip install playwright
playwright install chromium
```

2. 准备 `users.csv`（至少包含 `email,password`）：

```csv
email,password,display_name
alice@example.com,Passw0rd!,Alice
```

3. （可选）本地 OTP mock 文件夹：

```bash
mkdir -p otp_inbox
echo 123456 > otp_inbox/alice@example.com.otp
```

4. 运行 dry-run（只填表，不提交）：

```bash
python compliant_registration_template.py \
  --base-url https://your-app.example.com \
  --csv users.csv \
  --dry-run
```

5. 正式运行（默认每次最多 5 个账号，安全限制）：

```bash
python compliant_registration_template.py \
  --base-url https://your-app.example.com \
  --csv users.csv
```

## 合规建议

- 在上线前由法务/安全团队确认自动化行为符合平台条款。
- 保留日志与审计记录，便于追踪。
- 使用最小权限测试账号和隔离环境。
