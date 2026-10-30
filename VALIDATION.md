# 验证记录

2026-10-31 在 Apple Silicon、macOS 27.0、Xcode 27.2 (27B52) 环境完成一次原始 IPA → 独立 Catalyst App 的完整构建。

输入：Null's Royale 15.535.13，SHA-256：

```text
aa894e27e993adabad14768baef01ded1fda53c888a684fac2a7196a440e39af
```

结果：

- 40 个原有 ARM64 二进制转换完成。
- 全部原有具有文件内容的 Mach-O section 的地址、长度及内容 SHA-256 一致，包括主程序 `__TEXT,__text`，没有游戏指令补丁。
- 10,124 个原有文件内容不变；41 个原有文件修改（40 个 Mach-O 加 Info.plist）；新增 41 个文件（2 个兼容库加 39 个签名资源文件）；没有删除文件。
- 主程序只新增 `libnr_portrait.dylib`、`libnr_keychain.dylib` 两项依赖，使用包内相对路径。
- 实际签名权限只有 App Sandbox 和出站网络，无 `network.server`。
- 逐二进制 `codesign --verify --strict` 及整包 `codesign --verify --deep --strict` 通过。
- 4 项转换安全测试通过：注入保持代码且可重复调用、拒绝头部溢出且不写坏文件、section 指纹识别代码变动、ZIP 路径穿越在解压前拒绝。

机器可读的构建摘要见 [validation-summary.json](validation-summary.json)。生成目录还会包含逐文件输出哈希的完整 `conversion-report.json`，不提交生成的 App 或 IPA。

此次纯移植产物未启动，因此不将静态构建成功描述为运行时全功能验证。较旧 macOS、Finder 启动、完整对局、登录持久化及不同 IPA 版本仍需要相应环境实测。

运行转换安全测试：

```bash
python3 -m unittest discover -s tests -v
```
