from tortoise import fields
from tortoise.models import Model


class User(Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=20, unique=True)
    email = fields.CharField(null=True, max_length=50, unique=True)
    hashed_password = fields.CharField(max_length=128)