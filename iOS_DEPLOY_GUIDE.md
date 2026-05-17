# 📱 石头旅行记编辑器 - iOS 部署指南

## 前提条件

- ✅ Mac（已完成开发）
- ✅ iPhone（用于安装）
- ✅ Apple 开发者账号（$99/年，你已有）
- ✅ Xcode 16+（已安装）

---

## 第一步：准备 GitHub 访问令牌

> 编辑器在手机上不能写本地文件，需要通过 GitHub API 推送到网站

1. 打开 https://github.com/settings/tokens
2. 点击 **Generate new token (classic)**
3. 设置：
   - **Note**: `StoneTravelAdmin`
   - **Expiration**: 选 `No expiration`（永不过期，省事）
   - **Scopes**: 勾选 `repo`（全选所有子项）
4. 点击 **Generate token**
5. **⚠️ 立即复制这个 Token！**（页面关闭后就看不到了）
6. 保存到备忘录或密码管理器

---

## 第二步：用 Xcode 打开项目

**⚠️ 不要打开 `StoneTravelAdmin.xcodeproj`！** 那个是旧版 macOS-only 项目。

### 正确方式：

1. 打开 **Xcode**
2. 点击 **File → Open**
3. 选择文件：
   ```
   /Users/wanglong/Developer/StoneTravelAdmin/Package.swift
   ```
4. 点击 **Open**

Xcode 会自动识别这是一个 **Swift Package**，支持 iOS + macOS 双平台。

---

## 第三步：配置签名

1. 在 Xcode 顶部的工具栏中：
   - **Scheme 菜单**（左边）：选择 `StoneTravelAdmin`
   - **Destination 菜单**（右边）：**选择你的 iPhone**（不是模拟器）

2. 如果 Xcode 弹出签名错误：
   - 点击 **Signing & Capabilities** tab
   - 在 **Team** 下拉菜单中选择你的 Apple 账号
   - Bundle Identifier 会自动生成：`com.dragonknight.StoneTravelAdmin`（别改）

3. 如果提示"Add Account"：
   - 去 **Xcode → Settings → Accounts**
   - 点击 **+** 添加你的 Apple ID
   - 加入 Apple Developer Program 账号

---

## 第四步：首次运行

1. 用 USB 线连接 iPhone 到 Mac
2. 在 iPhone 上信任此电脑（如果提示）
3. 在 Xcode 中按 **`Cmd + R`** 或点击 ▶️ 按钮
4. Xcode 会：
   - 编译项目
   - 自动签名
   - 安装到你的 iPhone
5. **iPhone 上可能会弹窗**："Untrusted Developer"
   - 去 **设置 → 通用 → VPN与设备管理 → Apple Development: 你的邮箱**
   - 点击 **"信任"**

---

## 第五步：在 App 中设置 Token

1. 打开 iPhone 上的 **石头旅行记编辑器**
2. 点击左上角的 **⚙️ 齿轮图标**
3. 在 **GitHub Personal Access Token** 输入框粘贴刚才复制的 Token
4. 点击 **"完成"**

---

## 第六步：后续更新（不需要再连电脑）

当你想更新 App 版本时，有两种方式：

### 方式 A：TestFlight（推荐，需先配置）

1. Xcode 打开 Package.swift
2. 选择 **Any iOS Device (arm64)** 作为目标
3. 点击 **Product → Archive**
4. 在 Organizer 窗口中点击 **Distribute App**
5. 选择 **App Store Connect**
6. 上传后，在 App Store Connect 中启用 TestFlight
7. 你的 iPhone 上安装 TestFlight App 即可收到更新

### 方式 B：连电脑重新运行

每次修改代码后：
1. 连 iPhone 到 Mac
2. Xcode 按 `Cmd+R`

---

## 常见问题

### ❌ "Cannot find 'Destination' in scope"

**原因**：打开了旧的 `StoneTravelAdmin.xcodeproj`，而不是 `Package.swift`

**解决**：关闭 Xcode，用 File → Open → 选择 `Package.swift`

### ❌ "Failed to register bundle identifier"

**原因**：Bundle ID 和别人冲突了

**解决**：在 Signing & Capabilities 中把 Bundle Identifier 改成独特的，比如：
```
com.dragonknight.StoneTravelAdmin.你的名字
```

### ❌ 在 iPhone 上闪退

**原因**：代码中用的本地路径（`/Users/wanglong/...`）在手机上不存在

**解决**：手机上保存走的是 GitHub API，不是本地文件。iOS 版本的 `LocalFileService` 被 `#if os(macOS)` 保护，不会在 iOS 上运行。如果闪退，检查：
1. 是否设置了 GitHub Token
2. 网络是否正常

### ⚠️ DataService.swift 不见了？

如果你看到这个错误说明打开了旧版 Xcode 项目。**只用 `Package.swift` 打开项目**，Xcode 会自动识别 Sources 目录下所有文件。

---

## 文件结构说明

```
StoneTravelAdmin/
├── Package.swift          ← 用 Xcode 打开这个文件！
├── Sources/
│   └── StoneTravelAdmin/
│       ├── StoneTravelAdminApp.swift    ← App 入口
│       ├── ContentView.swift            ← 主界面
│       ├── DestinationManager.swift     ← 数据模型 & 管理器 & 云服务
│       ├── DestinationEditorView.swift  ← 编辑区
│       └── AddDestinationSheet.swift    ← 新增表单
├── StoneTravelAdmin/      ← 旧版 macOS 项目（忽略）
└── StoneTravelAdmin.xcodeproj ← 旧版项目（忽略）
```
