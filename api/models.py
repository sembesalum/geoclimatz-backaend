from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UserProfile(TimeStampedModel):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        CEO = "ceo", "CEO"
        COO = "coo", "COO"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INVITED = "invited", "Invited"
        SUSPENDED = "suspended", "Suspended"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.COO)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    avatar_file = models.FileField(upload_to="profile_images/", blank=True, null=True)
    avatar_url = models.URLField(blank=True)


class TrafficPoint(TimeStampedModel):
    class Period(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"

    period = models.CharField(max_length=20, choices=Period.choices)
    label = models.CharField(max_length=32)
    visitors = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["period", "id"]


class UserGrowthPoint(TimeStampedModel):
    label = models.CharField(max_length=32)
    users = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["id"]


class TopPage(TimeStampedModel):
    path = models.CharField(max_length=255)
    views = models.PositiveIntegerField(default=0)
    trend_pct = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    class Meta:
        ordering = ["-views"]


class BlogPost(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    class BodyFormat(models.TextChoices):
        PLAIN = "plain", "Plain"
        MARKDOWN = "markdown", "Markdown"
        HTML = "html", "HTML"

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    body = models.TextField(blank=True)
    body_format = models.CharField(max_length=20, choices=BodyFormat.choices, default=BodyFormat.MARKDOWN)
    hero_image_url = models.URLField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class GalleryImage(TimeStampedModel):
    caption = models.CharField(max_length=255)
    image_url = models.URLField()
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class Task(TimeStampedModel):
    class Column(models.TextChoices):
        PENDING = "pending", "Pending"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"

    class Priority(models.TextChoices):
        HIGH = "high", "High"
        MEDIUM = "medium", "Medium"
        LOW = "low", "Low"

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    column = models.CharField(max_length=20, choices=Column.choices, default=Column.PENDING)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    due_date = models.DateField(null=True, blank=True)
    position = models.DecimalField(max_digits=10, decimal_places=3, default=1000)
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="subtasks")
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_tasks")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_tasks")
    properties = models.JSONField(default=dict, blank=True)
    labels = models.JSONField(default=list, blank=True)
    content = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["column", "position", "id"]


class TaskComment(TimeStampedModel):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    message = models.TextField()

    class Meta:
        ordering = ["created_at"]


class PerformanceMetric(TimeStampedModel):
    label = models.CharField(max_length=32)
    page_load_ms = models.PositiveIntegerField(default=0)
    api_response_ms = models.PositiveIntegerField(default=0)
    error_rate_pct = models.DecimalField(max_digits=6, decimal_places=3, default=0)

    class Meta:
        ordering = ["id"]


class ServerStatus(TimeStampedModel):
    class Status(models.TextChoices):
        ONLINE = "online", "Online"
        OFFLINE = "offline", "Offline"

    name = models.CharField(max_length=64)
    region = models.CharField(max_length=64)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ONLINE)


class ActivityLog(TimeStampedModel):
    class Kind(models.TextChoices):
        CREATE = "create", "Create"
        DELETE = "delete", "Delete"
        UPDATE = "update", "Update"
        SECURITY = "security", "Security"
        AUTH = "auth", "Auth"

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    message = models.CharField(max_length=255)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.UPDATE)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]


class ContentAnalytics(TimeStampedModel):
    post = models.OneToOneField(BlogPost, on_delete=models.CASCADE, related_name="analytics")
    views = models.PositiveIntegerField(default=0)
    likes = models.PositiveIntegerField(default=0)
    comments = models.PositiveIntegerField(default=0)


class TaskFollowUp(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        RESOLVED = "resolved", "Resolved"

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="followups")
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)

    class Meta:
        ordering = ["-created_at"]


class MemberRequest(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    class RequestedRole(models.TextChoices):
        COO = "coo", "COO"
        STAFF = "staff", "Staff"

    name = models.CharField(max_length=120)
    email = models.EmailField()
    message = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    requested_role = models.CharField(max_length=20, choices=RequestedRole.choices, default=RequestedRole.STAFF)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="member_requests"
    )

    class Meta:
        ordering = ["-created_at"]


class NewsletterSubscriber(TimeStampedModel):
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["-created_at"]


class Donation(TimeStampedModel):
    donor_name = models.CharField(max_length=120)
    donor_email = models.EmailField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")
    message = models.TextField(blank=True)
    anonymous = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]


class Testimonial(TimeStampedModel):
    name = models.CharField(max_length=120)
    role_title = models.CharField(max_length=120, blank=True)
    company = models.CharField(max_length=120, blank=True)
    quote = models.TextField()
    avatar_url = models.URLField(blank=True)
    rating = models.PositiveSmallIntegerField(default=5)
    featured = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["-featured", "-created_at"]


class TeamMember(TimeStampedModel):
    name = models.CharField(max_length=120)
    role_title = models.CharField(max_length=120)
    bio = models.TextField(blank=True)
    image_url = models.URLField(blank=True)
    email = models.EmailField(blank=True)
    linkedin_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "name"]


class BrainstormIdea(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SHARED = "shared", "Shared"
        PUBLISHED = "published", "Published"

    title = models.CharField(max_length=255)
    content = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="brainstorm_ideas")
    shared_with = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="shared_brainstorm_ideas")
    share_with_all = models.BooleanField(default=False)

    class Meta:
        ordering = ["-updated_at"]
