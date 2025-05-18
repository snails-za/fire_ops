from aerich.migrate import Migrate

from config import AERICH_SAFE_MODE

# ✅ 如果启用安全模式， 则拦截 DROP 语句
if AERICH_SAFE_MODE == 1:
    # 获取未绑定的原始函数
    _original_diff_models = Migrate.__dict__["diff_models"].__func__

    def safe_diff_models(cls, old_models, new_models, upgrade=True):
        _original_diff_models(cls, old_models, new_models, upgrade)

        cls.upgrade_operators = [
            op for op in cls.upgrade_operators
            if "DROP TABLE" not in op.upper() and "DROP COLUMN" not in op.upper()
        ]
        cls.downgrade_operators = [
            op for op in cls.downgrade_operators
            if "DROP TABLE" not in op.upper() and "DROP COLUMN" not in op.upper()
        ]

        print("✅ [AERICH_SAFE_MODE] DROP 语句已被拦截。")

    # 替换原始 diff_models 方法
    Migrate.diff_models = classmethod(safe_diff_models)
