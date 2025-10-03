#!/usr/bin/env python3
"""
OCR依赖检查脚本
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from apps.utils.ocr_engines import check_and_install_dependencies, list_available_engines, test_ocr_engine

def main():
    print("🔍 OCR依赖检查工具")
    print("=" * 50)
    
    # 检查依赖
    all_ok = check_and_install_dependencies()
    
    if not all_ok:
        print("\n⚠️ 请先安装缺失的依赖，然后重新运行此脚本")
        return
    
    # 列出可用引擎
    print("\n📋 可用的OCR引擎:")
    engines = list_available_engines()
    for engine in engines:
        print(f"  ✅ {engine}")
    
    # 测试每个引擎
    print("\n🧪 测试OCR引擎:")
    for engine in engines:
        test_ocr_engine(engine)
    
    print("\n✅ OCR依赖检查完成！")

if __name__ == "__main__":
    main()
