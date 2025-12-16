

# Age GUI (Age Graphical User Interface)

---
![ScreenShot](https://github.com/louischang38/age-gui/blob/main/screenshot/screenshot.png)

### Introduction

**Age GUI** is a clean and simple graphical user interface (GUI) built with **PySide6**, designed to encrypt and decrypt files using the **age** encryption tool.

This application focuses on a **drag-and-drop workflow**, completely replacing the need to use the `age` command-line interface.

---

### Features

- **Drag-and-Drop Interface**  \
  Simply drag files into the main window to encrypt or decrypt them.

- **Automatic Mode Detection**  \
  Automatically switches between encryption and decryption based on file type.

- **Key Management**  \
  Supports drag-and-drop of recipient public keys (for encryption) and identity private keys (for decryption).

- **Key Memory (Encryption Mode)**  \
  Automatically remembers the last used recipient public key.

---

### System Requirements

The following command-line tool must be installed and accessible in your system `PATH`:

**Required:**

- `age`  \
  GitHub: https://github.com/FiloSottile/age

---

### Usage

#### Encryption

1. Drag one or more **non-`.age` files** into the main window  \
   The application automatically switches to **encryption mode**

2. Drag a **recipient public key** (starts with `age`) into the window

3. Corresponding `.age` encrypted files will be generated

---

#### Decryption

1. Drag one or more **`.age` files** into the main window  \
   The application automatically switches to **decryption mode**

2. Drag an **identity private key** into the window

3. Files will be decrypted automatically

---


### 簡介

**Age GUI** 是一個使用 **PySide6** 開發的簡潔圖形化使用者介面（GUI），用於透過 **age 加密工具** 進行檔案加密與解密。

本工具以 **拖放操作** 為核心設計，取代使用 `age` 指令列（CLI）的操作流程。

---

### 專案特色

- **拖放介面**  \
  將檔案拖放至主視窗即可完成加密或解密

- **模式自動判斷**  \
  依據檔案類型自動切換加密或解密模式

- **金鑰管理**  \
  支援拖放收件人公鑰（加密）與身份私鑰（解密）

- **金鑰記憶功能（加密模式）**  \
  自動記住上次使用的收件人公鑰

---

### 系統需求

系統中必須安裝以下命令列工具，並可於 `PATH` 中存取：

**必要：**

- `age`  \
  GitHub：https://github.com/FiloSottile/age

---

### 使用方式

#### 加密

1. 拖放一個或多個 **非 `.age` 檔案** 至主視窗  \
   程式會自動切換至 **加密模式**

2. 拖放收件人 **公鑰**（以 `age` 開頭）

3. 產生對應的 `.age` 加密檔案

---

#### 解密

1. 拖放一個或多個 **`.age` 檔案** 至主視窗  \
   程式會自動切換至 **解密模式**

2. 拖放 **身份私鑰**

3. 檔案即會完成解密

---
