import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager, Permission
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, phone, password=None, **extra):
        if not phone:
            raise ValueError("Telefon raqam kerak")
        user = self.model(phone=phone, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("is_owner", True)
        extra.setdefault("full_name", phone)
        return self.create_user(phone, password, **extra)


class Role(models.Model):
    """Ruxsatlar to'plami. Egasi yangi rol yaratib, unga ruxsat beradi."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kindergarten = models.ForeignKey(
        "school.Kindergarten", on_delete=models.CASCADE, related_name="roles"
    )
    name = models.CharField("Nomi", max_length=60)
    permissions = models.ManyToManyField(Permission, blank=True)
    is_system = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("kindergarten", "name")]
        verbose_name = "Rol"

    def __str__(self):
        return self.name


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None
    phone = models.CharField("Telefon", max_length=20, unique=True)
    full_name = models.CharField("F.I.O.", max_length=160)
    kindergarten = models.ForeignKey(
        "school.Kindergarten", on_delete=models.PROTECT,
        related_name="users", null=True, blank=True,
    )
    role = models.ForeignKey(
        Role, on_delete=models.PROTECT, null=True, blank=True, related_name="users",
        verbose_name="Rol",
    )
    is_owner = models.BooleanField("Egasi", default=False)
    must_change_password = models.BooleanField(
        "Parolni almashtirishi shart", default=False,
        help_text="Keyingi kirishda foydalanuvchi yangi parol o'rnatadi.",
    )

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def has_perm(self, perm, obj=None):
        if self.is_owner or self.is_superuser:
            return True
        if self.role_id:
            code = perm.split(".")[-1]
            if self.role.permissions.filter(codename=code).exists():
                return True
        return super().has_perm(perm, obj)

    def __str__(self):
        return self.full_name or self.phone


class AuditLog(models.Model):
    """O'chirilmaydigan jurnal."""

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.PROTECT, null=True)
    action = models.CharField(max_length=40)
    object_type = models.CharField(max_length=60)
    object_id = models.CharField(max_length=64)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["object_type", "object_id"])]

    def delete(self, *args, **kwargs):
        raise PermissionError("Audit yozuvini o'chirib bo'lmaydi.")
