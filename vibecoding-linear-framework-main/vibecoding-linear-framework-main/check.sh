#!/usr/bin/env bash
# check.sh - 可执行验收闸门
# 用法：bash check.sh

set -euo pipefail

# 未配置守卫：防止空项目误判为通过。
# 技术栈确认后，用真实命令替换本段。
echo "check.sh 尚未配置。"
echo "请根据 GATES.md 填入真实的安装、构建、测试、lint、冒烟测试命令，然后删除这个守卫。"
exit 1

# 配置示例：
#
# echo "==> 安装依赖"
# npm ci
#
# echo "==> 构建"
# npm run build
#
# echo "==> 测试"
# npm test
#
# echo "==> lint"
# npm run lint
#
# echo "==> 冒烟测试"
# npm run smoke
#
# echo "全部验收闸门通过。"
