import os
import importlib
from tortoise.models import Model
from tortoise import Tortoise

# 包路径和目录设置
package_name = "apps.models"
current_dir = os.path.dirname(__file__)

# 动态导入所有模型模块
for file in os.listdir(current_dir):
    if file.endswith(".py") and not file.startswith("__"):
        module_name = file[:-3]
        full_module_path = f"{package_name}.{module_name}"
        importlib.import_module(full_module_path)

# 使用 Tortoise.init_models() 显式注册模型
Tortoise.init_models([package_name], app_label="models")

# 自动收集所有模型类名称用于 __all__
__all__ = []

for file in os.listdir(current_dir):
    if file.endswith(".py") and not file.startswith("__"):
        module_name = file[:-3]
        module = importlib.import_module(f"{package_name}.{module_name}")
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, Model) and attr != Model:
                __all__.append(attr_name)

print(__all__)
