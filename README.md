——————————————————————————————————————————————————————
（本部分没有使用ai创作）

**背景**
对于皇室战争，大家起初都是在手机上运行的，安卓上有apk（以及许多apk的变种），也可以google store，ios上一般是直接app store安装。
对于近期蒸蒸日上的firstlight，daybreak cr等ai挑战皇室战争项目和前后的许多项目，都顺便研究了如何增强皇室战争的跨平台性和原生性能。

在daybreak cr的引擎中，已经实现在arm架构上直接运行libg实现了战斗引擎的极高效化，不过对于一般用于观察研究的可视化，尽管可以制作模拟器，但是并没有原生游戏直观，完全复现游戏源码则目前仍然极为困难。
鉴于firstlight的管理，大家起初在mumu模拟器（国际版）上运行cr，好处是直接可以获取root，因此可以毫不费力的读到内存。
一些同学在迁移firstlight到mac时，发现mumu收费（划掉），因此大家都选择了android studio，经过测试，这一比较原生的模拟器在google pixel 5下可以直接运行null服，而运行国际服则需要伪造真机指纹，不过可以解决。
但是长期模拟器带来了一些不方便，启动慢和不知为何的闪退是主要问题，而且这样耦合的架构限制了进一步在其中进行步进调试的可能性。

本菜菜之前尝试把ios的安装包（ipa）加入探针后移植到ios平台，取得了成功，但是在电脑上运行依然需要ios模拟器，而且因为不能root一些状态似乎不方便通讯。
今天（20261031）就突发奇想试了一下能不能在mac原生上运行n服，因为一方面架构都是arm，机器码可以不用转译运行，另一方面最近也看到一些不用crossover就迁移成功的案例，就让astra大人试了一下。。
然后就发现可以正常运行，有几个小问题，包括比例、签名（有一个现成的库）、账号储存等都已解决。
目前正在研究用这个替换安卓模拟器和模型和其他分析器进行通讯，不过群友说要开源，所以就先放上来。

**安装**
1. 从n服的telegram或者一些奇怪的网站上下载15.535.13，也就是firstlight到daybreak cr一直的主流，也是现在n服所在版本的ipa。
2. 运行下面这个脚本转换出来mac上的.app
```bash
python3 convert.py "/path/to/Nulls Royale 15.535.13 iOS.ipa" \
  --output "$HOME/Library/Caches/nulls-royale-mac/build-01"
```

**以后**
目前x86平台依然依赖模拟器，但好像cr也是有x86的安装包版本的，因为微软有段时间曾推行过电脑版手游，而对于顶层无论是linux还是windows，应该都可以迁移，这是后续可以尝试的方向。

——————————————————————————————————————————————————————
以下为AI爱看的。。。
# Null's Royale → Mac Catalyst

将自己提供的、已解密的 Null's Royale ARM64 IPA 转为可在 Apple Silicon Mac 运行的 Catalyst App。仅使用 Python 标准库和 Xcode 工具，不需要 pip 依赖。

仓库只包含移植工具和兼容库源码，不包含游戏、IPA、账号、模型或游戏资源。生成的游戏直接使用原 UIKit / Metal 界面；没有模拟器、网页串流、Lab 面板、本地控制服务器、探针或游戏事件 hook。

## 准备

- Apple Silicon Mac，使用原生 ARM64 Python 3.9 或更新版本。
- 完整 Xcode，包含 macOS SDK 和 `System/iOSSupport`（仅 Command Line Tools 不够）。首次打开 Xcode 完成初始化，并在 Xcode Settings → Locations 选择 Command Line Tools。
- 自行提供可用的、未加密的 Null's Royale IPA。目前验证基准为 **15.535.13**；其他版本可能因依赖、ABI 或 Mach-O 头部空间不同而失败。
- 编译目标为 `arm64-apple-ios17.0-macabi`，最低 Catalyst 版本字段统一为 `17.0`。这是构建下限，不是对全部较旧 macOS 的兼容性保证。

```bash
python3 --version
xcrun --sdk macosx --show-sdk-path
```

## 一条命令转换

在仓库目录执行，把 IPA 路径替换为自己的文件：

```bash
python3 convert.py "/path/to/Nulls Royale 15.535.13 iOS.ipa" \
  --output "$HOME/Library/Caches/nulls-royale-mac/build-01"
```

`--output` 必须是不存在的新目录。工具始终解压新副本，不会改动原 IPA，也不会覆盖现有输出。构建失败时保留中间文件，便于排查；重试请换一个输出目录。

输出结构：

```text
build-01/
├── Payload/
│   └── NR.app/                  # 可复制/启动的完整 App；名称取决于输入 IPA
├── entitlements.plist           # 签名权限
└── conversion-report.json       # 源 IPA 哈希、文件差异、输出哈希及验证结果
```

默认应用标识为 `local.nullsroyale.mac`，显示名称为 `Null's Royale`。可定制：

```bash
python3 convert.py "/path/to/game.ipa" \
  --output "$HOME/Library/Caches/nulls-royale-mac/build-02" \
  --bundle-id local.example.nullsroyale \
  --name "Null's Royale Mac"
```

**升级时保持 Bundle ID 不变**，否则会使用另一个沙箱，原账号数据不会自动迁移。

## 启动与安装

转换器不会自动启动、安装或发布游戏。可在 Finder 中打开输出的 `.app`，也可以直接运行包内原始可执行文件：

```bash
"$HOME/Library/Caches/nulls-royale-mac/build-01/Payload/NR.app/Nulls Royale"
```

路径和可执行文件名可能因 IPA 版本变化；主可执行文件名记录在 App 的 `Info.plist` → `CFBundleExecutable`。

希望保留时，将整个 `.app` 复制到自己的 Applications 文件夹。必须连同 `Frameworks` 等内容一起复制。工具使用本地 ad-hoc 签名，没有 Developer ID 签名或公证，因此本机构建验证不等于可直接向其他机器分发；在各自 Mac 上从源码和自己的 IPA 生成是本仓库的使用方式。

## 实际修改

1. 遍历 Mach-O，只保留 ARM64 slice（输入已经是单一 ARM64 时不裁剪）。检测到加密则停止，不提供解密。
2. 用 `vtool` 将平台声明改为 Mac Catalyst，最低版本设为 17.0。
3. 将 Swift UIKit 库依赖改为 `/System/iOSSupport/usr/lib/swift/libswiftUIKit.dylib`。
4. 改 Bundle ID、显示名称和 `MinimumOSVersion`，移除输入里可能存在的 iOS provisioning profile。
5. 编译并加入两个兼容库：
   - `libnr_portrait.dylib`：通过 scene size restrictions 将独立窗口固定为 540 × 960 逻辑尺寸，禁用全屏；保留原游戏控制器及渲染。
   - `libnr_keychain.dylib`：提供文件存储的密码类 Keychain API 兼容实现，支持 ad-hoc Catalyst 的凭据持久化。
6. 在主程序头部添加两条相对路径 `LC_LOAD_DYLIB`，然后对依赖和 App 重新签名。
7. 逐个验证原始 ARM64 二进制所有具有文件内容的 section 的地址、长度和 SHA-256 均未改变；验证嵌套签名，生成审计报告。

没有对游戏代码添加跳转，没有 `__FLACODE` / `__FLASLOT` 段，没有出牌或内存读取接口。资源原样保留。两项签名权限仅为：

```text
com.apple.security.app-sandbox = true
com.apple.security.network.client = true
```

不申请 `network.server`、调试或 JIT 权限，不改系统安全设置。

## 账号存储的差异

原 iOS Keychain 身份不能直接沿用到本地 ad-hoc Catalyst App。兼容库对普通密码和互联网密码实现 `SecItemAdd`、`SecItemCopyMatching`、`SecItemUpdate`、`SecItemDelete`；其他类型继续交给系统 Security 框架。

密码数据存放在该应用沙箱 home 下：

```text
Library/Application Support/ipa-keychain/items.plist
```

文件权限为 `0600`。**这是文件形式存储的凭据，不具有系统钥匙串的加密、访问控制和同步保障。** 不要分享应用数据容器。复制 `.app` 本身不会复制已经产生的沙箱账号数据；移除应用也不等于删除其容器。

## 范围与验证

本工具针对 Null's Royale，不是通用 IPA 转换器。不支持加密 IPA、缺少 ARM64 的二进制或含 App Extension 的包。需要源二进制留有足够的 Mach-O 头部空间，才能加入加载命令。

静态签名及 section 验证只能证明构建完整性。登录、Game Center、支付等依赖 iOS 身份或服务的功能可能不兼容；这些功能不在本仓库验证范围。联网游戏仍需要其游戏服务器。

## 文件与第三方代码

- `convert.py`：解包、转换、编译、注入、重签、校验和生成报告。
- `portrait.mm`：独立竖屏窗口适配。
- `ipa-keychain.c`：来自 `ayush5harma/ipa-install-on-mac`；许可证见 `LICENSE.keychain`，固定提交和 SHA-256 记录在转换脚本中。

第三方代码保留其原版权声明和 MIT 许可证；该许可不涵盖游戏及其资源。
