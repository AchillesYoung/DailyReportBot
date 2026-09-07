#!/usr/bin/env bash
set -euo pipefail

BOT_DIR="/opt/dailybot"

# ---------- 克隆或拉取 ----------
if [ ! -d "$BOT_DIR/.git" ]; then
    echo "==> 克隆仓库到 $BOT_DIR"
    sudo mkdir -p "$BOT_DIR"
    sudo chown "$USER":"$USER" "$BOT_DIR"
    git clone https://github.com/AchillesYoung/DailyReportBot.git "$BOT_DIR"
fi

cd "$BOT_DIR"
echo "==> 拉取最新代码"
git pull

# ---------- Python 虚拟环境 ----------
if [ ! -x "$BOT_DIR/.venv/bin/python" ]; then
    echo "==> 创建虚拟环境"
    python3 -m venv "$BOT_DIR/.venv"
fi

echo "==> 安装依赖"
"$BOT_DIR/.venv/bin/pip" install -r requirements.txt -q

# ---------- systemd ----------
echo "==> 部署 systemd 服务"
sudo cp deploy/systemd/*.service /etc/systemd/system/
sudo cp deploy/systemd/*.timer /etc/systemd/system/

echo "==> 重载并启动定时器"
sudo systemctl daemon-reload
sudo systemctl enable --now \
    dailybot-morning.timer \
    dailybot-evening.timer \
    dailybot-aihot.timer \
    dailybot-telegram.timer

# ---------- 完成 ----------
echo ""
echo "==> 部署完成！定时器状态："
systemctl list-timers dailybot-*
echo ""
echo "==> 手动验证："
echo "  日报测试:  $BOT_DIR/.venv/bin/python -m dailybot --edition morning --dry-run"
echo "  查看日志:  journalctl -u dailybot-morning.service -f"
