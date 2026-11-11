"""Internationalization and localization support for GT6 Launcher."""
from __future__ import annotations

from typing import Optional

# List of supported languages: (code, display_label, english_name)
LANGUAGES: list[tuple[str, str, str]] = [
    ("en", "🇬🇧 English", "English"),
    ("zh_CN", "🇨🇳 简体中文", "Simplified Chinese"),
]

_CURRENT_LANG: str = "en"


def get_current_language() -> str:
    return _CURRENT_LANG


def set_current_language(code: str) -> None:
    global _CURRENT_LANG
    valid_codes = [c for c, _, _ in LANGUAGES]
    if code in valid_codes:
        _CURRENT_LANG = code
    else:
        _CURRENT_LANG = "en"


def next_language(current_code: str) -> tuple[str, str]:
    """Cycles to the next available language, returning (code, display_label)."""
    codes = [c for c, _, _ in LANGUAGES]
    try:
        idx = (codes.index(current_code) + 1) % len(codes)
    except ValueError:
        idx = 0
    return LANGUAGES[idx][0], LANGUAGES[idx][1]


def get_language_label(code: str) -> str:
    for c, label, _ in LANGUAGES:
        if c == code:
            return label
    return LANGUAGES[0][1]


def tr(text: str, lang: Optional[str] = None) -> str:
    """Translates a string into the target language (defaults to current)."""
    target = lang or _CURRENT_LANG
    if target == "en":
        return text
    table = TRANSLATIONS.get(target, {})
    return table.get(text, text)


# Translation tables for supported non-English languages
TRANSLATIONS: dict[str, dict[str, str]] = {
    "zh_CN": {
        # Tab headers
        "Setup": "安装设置",
        "Graphics": "画面图像",
        "Patches": "游戏补丁",
        "Mods": "模组扩展",
        "LAN": "局域联机",
        "Advanced": "高级选项",
        "Log": "运行日志",

        # Left panel
        "PC edition  ·  v": "PC 移植版  ·  v",
        "PLAY": "开始游戏",
        "RUNNING": "运行中",
        "Cancel": "取消",
        "LAN mode (secret lanmode)": "局域网模式 (隐藏联机功能)",
        "No game added yet.": "尚未添加游戏镜像。",
        "Add your Gran Turismo 6 disc image in Setup.": "请在“安装设置”页面添加《GT赛车6》ISO 镜像。",
        "Preparing the emulator component...": "正在准备模拟器组件...",
        "Emulator component missing - reinstall the launcher.": "模拟器组件缺失，请重新安装启动器。",
        "Starting RPCS3...": "正在启动 RPCS3...",
        "Installing firmware...": "正在安装 PS3 固件...",
        "Installing update...": "正在安装游戏更新包...",
        "Applying patches...": "正在应用补丁...",

        # GroupBoxes
        "1. PS3 firmware": "1. PS3 系统固件",
        "2. Game disc": "2. 游戏光盘镜像",
        "3. Controllers": "3. 控制器与方向盘",
        "4. Game updates": "4. 游戏更新补丁",
        "Image quality": "画面画质优化",
        "Frame rate && display": "帧率与显示设置",
        "Camera (Extended FOV patch, 0 = stock)": "视角调整 (FOV 扩展补丁，0 为默认)",
        "Emulation": "模拟器核心参数",
        "GT6 Career Mod (+ Spec II mod)": "GT6 生涯模组 (+ Spec II Mod)",
        "Cheats (single player)": "单人作弊选项",
        "Mod readme": "模组说明文档",
        "LAN mode": "局域网对战模式",
        "Online (community server, EU disc 1.22 only)": "线上联机 (RPCN 社区服，仅限欧版 1.22)",
        "How to race over LAN": "如何进行局域网联机对战",
        "Firewall": "防火墙设置",
        "Tools": "常用工具",
        "Danger zone": "危险区域",
        "Troubleshooting": "故障排查指南",
        "About": "关于启动器",

        # Setup Tab Buttons & Text
        "Install firmware": "安装固件",
        "Reinstall firmware": "重新安装固件",
        "Choose PS3UPDAT.PUP...": "选择 PS3UPDAT.PUP 文件...",
        "If no PUP file is found locally it is downloaded from Sony's update server.": "若本地未找到 PUP 文件，将自动从索尼官方服务器下载。",
        "Installed": "已安装",
        "Not installed": "未安装",
        "Add ISO...": "添加 ISO 镜像...",
        "Add folder...": "添加文件夹...",
        "Scan for ISOs": "扫描 ISO 镜像...",
        "Add disc image (ISO)...": "添加光盘镜像 (ISO)...",
        "Scan for discs...": "扫描光盘镜像...",
        "Refresh": "刷新",
        "Select your decrypted GT6 ISO file.": "请选择已解密的《GT赛车6》ISO 镜像文件。",
        "Target version": "目标版本",
        "Download & install updates": "下载并安装更新",
        "Gamepad mode": "手柄输入模式",
        "Automatic (first connected gamepad)": "自动 (首选已连接手柄)",
        "Keyboard only": "仅键盘操作",
        "Manual (configured in RPCS3)": "手动 (在 RPCS3 中配置)",
        "Racing wheel": "力回馈方向盘",
        "Enable wheel (emulates Logitech G27)": "启用方向盘 (模拟罗技 G27)",
        "Configure wheel...": "配置方向盘向导...",

        # Graphics Tab Buttons & Controls
        "Output resolution": "输出分辨率",
        "Resolution scale": "内部渲染倍率",
        "Aspect ratio": "画面显示比例",
        "Frame rate": "帧率限制与垂直同步",
        "FidelityFX CAS sharpening": "FidelityFX CAS 画面锐化",
        "Anti-aliasing (MLAA)": "抗锯齿 (MLAA)",
        "Motion blur": "动态模糊",
        "Depth of field": "景深虚化",
        "Shadow quality": "阴影质量",
        "Street lamp glare": "路灯眩光",
        "60 FPS in Gallery / new-car screens (Unlock FPS patch)": "展厅/购车界面 60 FPS (Unlock FPS 补丁)",
        "Cockpit vertical FOV": "驾驶舱垂直视角",
        "Hood vertical FOV": "车前盖垂直视角",
        "Roof vertical FOV": "车顶垂直视角",
        "Chase vertical FOV": "第三人称追尾垂直视角",
        "Reset to recommended": "恢复默认推荐设置",
        "Restore previous graphics settings": "恢复之前的画面设置",
        "Handheld 800p preset (Steam Deck / 1280x800)": "掌机 800p 预设 (Steam Deck / 1280x800)",

        # Advanced Tab
        "GPU": "显卡 (GPU)",
        "Automatic (RPCS3 default)": "自动 (RPCS3 默认)",
        "Audio output": "音频输出声道",
        "Stereo (2.0)": "立体声 (2.0)",
        "Surround 5.1": "5.1 环绕声",
        "Render path": "渲染路径",
        "SPU block size": "SPU 块大小",
        "Thread scheduler": "线程调度器",
        "Operating System": "操作系统默认 (OS)",
        "RPCS3 Scheduler": "RPCS3 专属调度器",
        "Performance overlay": "性能监控浮层",
        "Asynchronous texture streaming": "异步纹理流式加载",
        "Z-Cull occlusion queries": "禁用 Z-Cull 遮挡查询",
        "Multithreaded RSX": "多线程 RSX",
        "Accurate RSX reservations": "精确 RSX 预留",
        "Handle tiled memory": "处理平铺显存 (Tiled Memory)",
        "Console language": "游戏主机语言",
        "Developer menu (Develop Settings)": "开发者调试菜单 (Develop Settings)",
        "System tools (Linux)": "系统增强工具 (Linux)",
        "Use GameMode (feralinteractive)": "启用 GameMode 游戏加速",
        "Use MangoHud overlay": "启用 MangoHud 监控浮层",
        "Reset RPCS3 to recommended": "重置 RPCS3 为推荐设置",

        # Tools & Danger Zone Buttons
        "Open RPCS3 directory": "打开 RPCS3 所在目录",
        "Open RPCS3 GUI": "打开 RPCS3 主界面",
        "Open GT6 save folder": "打开 GT6 存档文件夹",
        "Open shaders cache": "打开着色器缓存目录",
        "Clear shaders cache": "清空着色器缓存",
        "Install Spec II career mod": "安装 Spec II 生涯模组",
        "Uninstall Spec II mod": "卸载 Spec II 模组",
        "Download Spec II mod": "下载 Spec II 模组包",

        # LAN Tab
        "Network mode": "联机网络模式",
        "Enable LAN mode (local network / VPN)": "启用局域网对战 (本地网络 / VPN)",
        "Enable online mode (RPCN community server)": "启用线上联机 (RPCN 社区服务器)",
        "IP address": "本机 IP 地址",
        "PSID": "控制台 PSID",
        "RPCN Account": "RPCN 账号状态",
        "Open RPCS3 network settings": "打开 RPCS3 网络设置",
        "Ready for": "就绪：",
        "Not available": "不可用：",

        # Log Tab
        "Save current logs": "导出并保存日志",
        "Open RPCS3 log": "打开 RPCS3 日志文件",
        "Copy log": "复制日志内容",
        "Clear log": "清空日志窗口",

        # Common
        "Close": "关闭",
        "Continue": "继续",
        "Hardware may struggle with GT6": "硬件配置提示",
        "This PC may struggle to run Gran Turismo 6 smoothly.": "当前电脑配置在运行《GT赛车6》时可能会遇到性能瓶颈。",
        "Switch language": "切换界面语言",
    }
}
