#!/usr/bin/env bash
# 一键构建「车管家」完全离线自包含 APK（WebView 版）
# 用法：改完 car-maintenance/docs/ 里的网页后，双击或在 Git Bash 里运行本脚本即可出新包。
# 注意：如需升版本号，先改 android-offline/app/build.gradle 里的 versionCode / versionName。
set -e
cd "$(dirname "$0")"

echo "==> 1/3 同步最新网页到 APK assets"
cp docs/index.html docs/manifest.json docs/sw.js docs/icon-192.png docs/icon-512.png \
   android-offline/app/src/main/assets/

echo "==> 2/3 gradle 构建（直连 + 阿里云镜像）"
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
export JAVA_HOME="C:/Program Files/Eclipse Adoptium/jdk-17.0.20.101-hotspot"
export ANDROID_HOME="C:/Users/OFFICE/AppData/Local/Android/Sdk"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export no_proxy="*"
( cd android-offline && ./gradlew assembleRelease )

echo "==> 3/3 输出成品"
VER=$(grep -o 'versionName "[^"]*"' android-offline/app/build.gradle | cut -d'"' -f2)
OUT="车管家-离线自包含-v${VER}.apk"
cp android-offline/app/build/outputs/apk/release/app-release.apk "$OUT"

echo ""
echo "✅ 构建完成: $(pwd)/$OUT"
echo "   发给别人：微信/蓝牙发送 → 对方允许未知来源 → 安装（装完断网也能用）"
