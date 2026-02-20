#!/usr/bin/env python3
"""Desktop WebUI repeat bot driven by JSON step configs."""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any



def _require_pyautogui():
    try:
        import pyautogui  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError("缺少依赖 pyautogui，请先执行: pip install pyautogui opencv-python pillow") from exc
    return pyautogui


def _require_pygetwindow():
    try:
        import pygetwindow as gw  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError("缺少依赖 pygetwindow，请先执行: pip install pygetwindow") from exc
    return gw


VALID_ACTIONS = {"click", "double_click", "type", "hotkey"}


@dataclass
class BotSettings:
    confidence: float
    retries: int
    retry_delay: float
    artifacts_dir: Path


SETTINGS = BotSettings(confidence=0.8, retries=3, retry_delay=0.5, artifacts_dir=Path("artifacts"))
_STOP_REQUESTED = False


class ConfigError(ValueError):
    """Raised when config file content is invalid."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repeat WebUI actions by locating template images on screen.")
    parser.add_argument("--window", required=True, help="Target window title keyword to focus.")
    parser.add_argument("--config", required=True, help="Path to JSON step config.")
    parser.add_argument("--interval", type=float, default=1.0, help="Sleep seconds after each round.")
    parser.add_argument("--max-rounds", type=int, default=None, help="Maximum loop rounds. Omit for infinite.")
    parser.add_argument("--confidence", type=float, default=0.8, help="Image match confidence [0, 1].")
    parser.add_argument("--retries", type=int, default=3, help="Retries per locate operation when matching fails.")
    parser.add_argument("--retry-delay", type=float, default=0.5, help="Delay seconds between retries.")
    return parser.parse_args(argv)


def load_config(config_path: str) -> list[dict[str, Any]]:
    path = Path(config_path)
    if not path.exists():
        raise ConfigError(f"配置文件不存在: {path}")

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"配置 JSON 解析失败: {exc}") from exc

    if isinstance(raw, dict) and "steps" in raw:
        steps = raw["steps"]
    else:
        steps = raw

    validate_steps(steps)
    return steps


def validate_steps(steps: Any) -> None:
    if not isinstance(steps, list):
        raise ConfigError("配置必须是步骤列表，或含有 steps 列表字段。")
    if not steps:
        raise ConfigError("步骤配置不能为空。")

    required = {"name", "action", "wait"}
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            raise ConfigError(f"第 {index} 步必须是对象。")

        missing = sorted(required - set(step.keys()))
        if missing:
            raise ConfigError(f"第 {index} 步缺少字段: {', '.join(missing)}")

        action = step.get("action")
        if action not in VALID_ACTIONS:
            raise ConfigError(f"第 {index} 步 action 无效: {action}，必须是 {sorted(VALID_ACTIONS)}")

        if action in {"click", "double_click"} and not step.get("image"):
            raise ConfigError(f"第 {index} 步 action={action} 时必须提供 image")
        if action in {"type", "hotkey"} and not step.get("text"):
            raise ConfigError(f"第 {index} 步 action={action} 时必须提供 text")

        wait = step.get("wait")
        if not isinstance(wait, (int, float)) or wait < 0:
            raise ConfigError(f"第 {index} 步 wait 必须是非负数字。")


def _request_stop(_sig: int | None = None, _frame: Any = None) -> None:
    global _STOP_REQUESTED
    _STOP_REQUESTED = True


def _esc_pressed() -> bool:
    """Check ESC key state.

    - On Windows uses GetAsyncKeyState for global key state.
    - On non-Windows, rely on Ctrl+C/SIGINT as fallback.
    """
    if os.name != "nt":
        return False

    import ctypes

    VK_ESCAPE = 0x1B
    return bool(ctypes.windll.user32.GetAsyncKeyState(VK_ESCAPE) & 0x8000)


def _check_abort() -> None:
    if _STOP_REQUESTED or _esc_pressed():
        raise KeyboardInterrupt("检测到 Esc/Ctrl+C，中止执行。")


def focus_window(window_title: str) -> None:
    gw = _require_pygetwindow()
    matches = gw.getWindowsWithTitle(window_title)
    if not matches:
        available = [title for title in gw.getAllTitles() if title.strip()]
        preview = ", ".join(available[:10])
        raise RuntimeError(f"未找到窗口: {window_title}。可见窗口示例: {preview}")

    window = matches[0]
    if window.isMinimized:
        window.restore()
    window.activate()
    time.sleep(0.2)


def _save_failure_screenshot(step_name: str) -> Path:
    SETTINGS.artifacts_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = SETTINGS.artifacts_dir / f"fail_{step_name}_{ts}.png"
    pyautogui = _require_pyautogui()
    pyautogui.screenshot(str(path))
    return path


def _locate_center(image_path: str, confidence: float) -> Any | None:
    pyautogui = _require_pyautogui()
    return pyautogui.locateCenterOnScreen(image_path, confidence=confidence)


def locate_and_click(image_path: str, confidence: float = 0.8) -> bool:
    point = _locate_center(image_path=image_path, confidence=confidence)
    if not point:
        return False
    pyautogui = _require_pyautogui()
    pyautogui.click(point.x, point.y)
    return True


def _execute_step(step: dict[str, Any]) -> None:
    name = step["name"]
    action = step["action"]

    if action in {"click", "double_click"}:
        image = step["image"]
        matched = False
        point = None
        for attempt in range(1, SETTINGS.retries + 1):
            _check_abort()
            point = _locate_center(image_path=image, confidence=SETTINGS.confidence)
            if point:
                matched = True
                break
            if attempt < SETTINGS.retries:
                time.sleep(SETTINGS.retry_delay)

        if not matched:
            artifact = _save_failure_screenshot(name)
            raise RuntimeError(f"步骤 {name} 识别失败，截图已保存: {artifact}")

        pyautogui = _require_pyautogui()
        if action == "double_click":
            pyautogui.doubleClick(point.x, point.y)
        else:
            pyautogui.click(point.x, point.y)

    elif action == "type":
        pyautogui = _require_pyautogui()
        pyautogui.write(str(step["text"]))
    elif action == "hotkey":
        keys = [k.strip() for k in str(step["text"]).split("+") if k.strip()]
        if not keys:
            raise RuntimeError(f"步骤 {name} hotkey 未提供有效按键")
        pyautogui = _require_pyautogui()
        pyautogui.hotkey(*keys)

    time.sleep(float(step.get("wait", 0)))


def run_loop(steps: list[dict], interval_sec: float, max_rounds: int | None) -> None:
    round_no = 0
    while True:
        _check_abort()
        round_no += 1
        if max_rounds is not None and round_no > max_rounds:
            print(f"已达到最大轮次: {max_rounds}，结束。")
            return

        print(f"开始第 {round_no} 轮，共 {len(steps)} 步")
        for step in steps:
            _check_abort()
            print(f"执行步骤: {step['name']}")
            _execute_step(step)

        time.sleep(interval_sec)


def main() -> int:
    signal.signal(signal.SIGINT, _request_stop)
    signal.signal(signal.SIGTERM, _request_stop)

    args = parse_args()
    if not 0 <= args.confidence <= 1:
        raise ConfigError("--confidence 必须在 [0, 1] 之间")
    if args.retries < 1:
        raise ConfigError("--retries 必须 >= 1")
    if args.interval < 0 or args.retry_delay < 0:
        raise ConfigError("--interval 和 --retry-delay 必须为非负数")

    SETTINGS.confidence = args.confidence
    SETTINGS.retries = args.retries
    SETTINGS.retry_delay = args.retry_delay

    steps = load_config(args.config)
    focus_window(args.window)
    run_loop(steps, interval_sec=args.interval, max_rounds=args.max_rounds)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt as exc:
        print(str(exc))
        raise SystemExit(130)
    except ConfigError as exc:
        print(f"配置错误: {exc}", file=sys.stderr)
        raise SystemExit(2)
    except Exception as exc:  # noqa: BLE001
        print(f"运行失败: {exc}", file=sys.stderr)
        raise SystemExit(1)
