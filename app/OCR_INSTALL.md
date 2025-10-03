# OCR功能使用指南

## 🎯 **OCR引擎**

系统使用 **EasyOCR** 作为OCR引擎，支持80+语言，简单易用，准确率高。

## 🚀 **快速开始**

### 1. **安装依赖**
```bash
# 安装Python依赖
uv sync

# 安装系统依赖 (macOS)
brew install poppler

# 安装系统依赖 (Ubuntu)
sudo apt-get install poppler-utils
```

## ⚙️ **配置使用**

### **OCR功能配置**
在 `.env` 文件中设置：
```bash
OCR_ENABLED=true              # OCR功能开关
OCR_AUTO_FALLBACK=true        # 自动降级到OCR
OCR_MIN_TEXT_LENGTH=100       # 触发OCR的最小文本长度
OCR_MAX_FILE_SIZE=52428800    # OCR最大文件大小(50MB)
```

### **EasyOCR特点**

| 特性 | 说明 |
|------|------|
| **多语言支持** | 支持80+语言，包括中文、英文等 |
| **准确率高** | 英文准确率90%，中文准确率85% |
| **简单易用** | 无需复杂配置，开箱即用 |
| **轻量级** | 相比其他OCR引擎更轻量 |

### **推荐场景**
- **多语言文档**：支持中英文混合文档
- **高精度需求**：对英文识别准确率要求高
- **简单部署**：无需复杂配置

## 🔧 **故障排除**

### **常见问题**
- **EasyOCR首次运行慢**：正常现象，需要下载模型
- **PDF转换失败**：安装 `poppler` 工具

### **依赖检查**
```bash
# 检查OCR依赖
python check_ocr_deps.py
```

### **系统依赖安装**
```bash
# macOS
brew install poppler

# Ubuntu
sudo apt-get install poppler-utils
```

现在你可以使用EasyOCR进行OCR文本识别了！