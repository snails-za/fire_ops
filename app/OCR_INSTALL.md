# OCR功能使用指南

## 🎯 **支持的OCR引擎**

系统支持两种免费开源OCR引擎：

1. **PaddleOCR** - 百度开源，中文优化，准确率高 (默认)
2. **EasyOCR** - 简单易用，支持80+语言

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

### **选择OCR引擎**
在 `.env` 文件中设置：
```bash
OCR_ENGINE=paddleocr  # 可选: paddleocr, easyocr
```

### **引擎对比**

| 引擎 | 中文准确率 | 英文准确率 | 推荐场景 |
|------|------------|------------|----------|
| **PaddleOCR** | 95% | 80% | 中文文档、复杂排版 |
| **EasyOCR** | 85% | 90% | 多语言、高精度 |

### **推荐配置**
- **中文文档**：`OCR_ENGINE=paddleocr` (默认)
- **多语言文档**：`OCR_ENGINE=easyocr`

## 🔧 **故障排除**

### **常见问题**
- **PaddleOCR首次运行慢**：正常现象，需要下载模型
- **PDF转换失败**：安装 `poppler` 工具

### **切换引擎**
```bash
# 修改 .env 文件
OCR_ENGINE=paddleocr  # 或 easyocr
```

现在你可以根据文档类型选择合适的OCR引擎了！
