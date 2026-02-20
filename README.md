# Auto-register WebUI 重复操作脚本

本仓库提供一个可配置的桌面自动化脚本：`scripts/webui_repeat_bot.py`，用于按模板图识别并重复执行 WebUI 操作。

## 依赖

```bash
pip install pyautogui opencv-python pygetwindow pillow
```

## 配置步骤（JSON）

示例文件：`configs/webui_steps.json`

每个步骤支持字段：

- `name`: 步骤名（必填）
- `image`: 模板图路径（`click`/`double_click` 必填）
- `action`: `click` / `double_click` / `type` / `hotkey`
- `text`: 文本内容（`type`/`hotkey` 必填）
- `wait`: 当前步骤完成后等待秒数（必填，非负）

## 使用方式

```bash
python scripts/webui_repeat_bot.py \
  --window "你的窗口名" \
  --config configs/webui_steps.json \
  --interval 1.0
```

常用参数：

- `--confidence`: 图像匹配阈值（默认 `0.8`，范围 `[0,1]`）
- `--retries`: 每一步识别失败重试次数（默认 `3`）
- `--retry-delay`: 重试间隔秒数（默认 `0.5`）
- `--max-rounds`: 最大循环轮次（不填表示无限循环）

## 按钮模板图截取建议

1. 在目标显示缩放比例固定（如 100%）下截图。
2. 尽量只截取控件主体，避免太大背景区域。
3. 保持截图分辨率与运行环境一致。
4. 将模板图放入例如 `templates/` 目录并在 JSON 里引用。

## `confidence` 调整建议

- 识别不到时：适当降低（如 `0.8 -> 0.7`）。
- 误识别时：提高（如 `0.8 -> 0.9`）。
- 先从 `0.8` 起调，逐步微调 `0.05`。

## 失败重试与安全退出

- `click`/`double_click` 步骤会自动重试；超过重试次数后保存失败截图到 `artifacts/fail_*.png` 并终止。
- 支持 `Esc` 立即中止（Windows 全局监听）；所有平台均支持 `Ctrl+C` 中止。

## 最小可验证项（静态层面）

脚本已拆分并可直接单独调用以下函数进行验证：

- 参数解析：`parse_args()`
- 配置加载：`load_config()`
- 步骤校验：`validate_steps()`

空配置、缺字段、非法 action、非法 wait 都会抛出带明确信息的 `ConfigError`。
