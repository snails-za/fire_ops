# OCR功能使用指南

## 🎯 **OCR引擎**

系统使用 **EasyOCR** 作为OCR引擎，支持80+语言，简单易用，准确率高，支持GPU加速。

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

### 2. **GPU加速支持（可选）**
```bash
# 如需GPU加速，请安装CUDA版本的PyTorch
# 访问 https://pytorch.org/get-started/locally/ 获取安装命令
```

## ⚙️ **配置使用**

### **OCR功能配置**
在 `.env` 文件中设置：
```bash
OCR_ENABLED=true              # OCR功能开关
OCR_AUTO_FALLBACK=true        # 自动降级到OCR
OCR_MIN_TEXT_LENGTH=100       # 触发OCR的最小文本长度
OCR_MAX_FILE_SIZE=52428800    # OCR最大文件大小(50MB)

# GPU加速配置
OCR_USE_GPU=true              # 是否启用GPU加速
```

## 🔧 **故障排除**

### **常见问题**
- **EasyOCR首次运行慢**：正常现象，需要下载模型
- **PDF转换失败**：安装 `poppler` 工具
- **GPU初始化失败**：系统会自动降级到CPU模式

### **依赖检查**
```bash
# 检查OCR依赖和GPU状态
python check_ocr_deps.py
```

### **系统依赖安装**
```bash
# macOS
brew install poppler

# Ubuntu
sudo apt-get install poppler-utils
```

现在你可以使用EasyOCR进行OCR文本识别了，支持GPU加速！