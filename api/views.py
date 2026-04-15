import json
import random
from datetime import date
from decimal import Decimal

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.db import models
from django.db.models import Count, Q
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from .models import (
    ActivityLog,
    BlogPost,
    BrainstormIdea,
    ContentAnalytics,
    Donation,
    GalleryImage,
    MemberRequest,
    NewsletterSubscriber,
    PerformanceMetric,
    ServerStatus,
    Task,
    TaskComment,
    TaskFollowUp,
    TeamMember,
    Testimonial,
    TopPage,
    TrafficPoint,
    UserGrowthPoint,
    UserProfile,
)

User = get_user_model()
ADMIN_ROLES = {UserProfile.Role.ADMIN}
CEO_ROLES = {UserProfile.Role.ADMIN, UserProfile.Role.CEO}
COO_ROLES = {UserProfile.Role.ADMIN, UserProfile.Role.CEO, UserProfile.Role.COO}
LOGIN_ALLOWED_ROLES = {UserProfile.Role.ADMIN, UserProfile.Role.CEO, UserProfile.Role.COO}


def _json_body(request: HttpRequest) -> dict:
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _request_data(request: HttpRequest) -> tuple[dict, dict]:
    content_type = request.content_type or ""
    if content_type.startswith("multipart/form-data"):
        return request.POST.dict(), request.FILES
    return _json_body(request), {}


def _get_role(user: User) -> str:
    if user.is_superuser:
        return UserProfile.Role.ADMIN
    profile = getattr(user, "profile", None)
    role = profile.role if profile else UserProfile.Role.COO
    return role if role in LOGIN_ALLOWED_ROLES else UserProfile.Role.COO


def _user_payload(user: User) -> dict:
    profile = getattr(user, "profile", None)
    if user.is_superuser:
        resolved_role = UserProfile.Role.ADMIN
    else:
        raw_role = profile.role if profile else UserProfile.Role.COO
        resolved_role = raw_role if raw_role in LOGIN_ALLOWED_ROLES else UserProfile.Role.COO
    avatar = ""
    if profile:
        if getattr(profile, "avatar_file", None):
            avatar = profile.avatar_file.url
            if avatar.startswith("/"):
                avatar = f"https://geoclimatz.pythonanywhere.com{avatar}"
        elif profile.avatar_url:
            avatar = profile.avatar_url
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": resolved_role,
        "status": profile.status if profile else UserProfile.Status.ACTIVE,
        "avatar_url": avatar,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
    }


def _task_payload(task: Task) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "column": task.column,
        "priority": task.priority,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "position": float(task.position),
        "parent_id": task.parent_id,
        "assignee": _user_payload(task.assignee) if task.assignee else None,
        "created_by": _user_payload(task.created_by) if task.created_by else None,
        "labels": task.labels,
        "properties": task.properties,
        "content": task.content,
        "subtasks_count": task.subtasks.count(),
        "comments_count": task.comments.count(),
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
    }


def api_login_required(view_func):
    def wrapped(request: HttpRequest, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)
        return view_func(request, *args, **kwargs)

    return wrapped


def roles_required(*allowed_roles):
    def decorator(view_func):
        def wrapped(request: HttpRequest, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse({"error": "Authentication required"}, status=401)
            role = _get_role(request.user)
            if role not in set(allowed_roles):
                return JsonResponse({"error": "Forbidden for this role"}, status=403)
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator


@require_GET
def health(_: HttpRequest):
    return JsonResponse({"ok": True, "service": "geoclimatz-api", "time": timezone.now().isoformat()})


@csrf_exempt
@require_http_methods(["POST"])
def auth_login(request: HttpRequest):
    body = _json_body(request)
    user = authenticate(request, username=body.get("username"), password=body.get("password"))
    if not user:
        return JsonResponse({"error": "Invalid credentials"}, status=401)
    role = _get_role(user)
    if role not in LOGIN_ALLOWED_ROLES:
        return JsonResponse({"error": "This account role is not allowed to access this dashboard"}, status=403)

    login(request, user)
    ActivityLog.objects.create(actor=user, kind=ActivityLog.Kind.AUTH, message=f"{user.username} logged in")
    return JsonResponse({"user": _user_payload(user)})


@csrf_exempt
@require_http_methods(["POST"])
def auth_logout(request: HttpRequest):
    if request.user.is_authenticated:
        ActivityLog.objects.create(actor=request.user, kind=ActivityLog.Kind.AUTH, message=f"{request.user.username} logged out")
    logout(request)
    return JsonResponse({"ok": True})


@require_GET
def auth_me(request: HttpRequest):
    if not request.user.is_authenticated:
        return JsonResponse({"authenticated": False, "user": None})
    return JsonResponse({"authenticated": True, "user": _user_payload(request.user)})


@csrf_exempt
@require_http_methods(["GET", "PATCH"])
@api_login_required
def auth_profile(request: HttpRequest):
    if request.method == "GET":
        return JsonResponse({"user": _user_payload(request.user)})

    body, files = _request_data(request)
    user = request.user
    user.first_name = body.get("first_name", user.first_name)
    user.last_name = body.get("last_name", user.last_name)
    user.email = body.get("email", user.email)
    user.save()

    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.avatar_url = body.get("avatar_url", profile.avatar_url)
    if files.get("avatar_image"):
        profile.avatar_file = files.get("avatar_image")
    profile.save()

    new_password = body.get("new_password", "").strip()
    if new_password:
        current_password = body.get("current_password", "")
        if not user.check_password(current_password):
            return JsonResponse({"error": "Current password is incorrect"}, status=400)
        user.set_password(new_password)
        user.save()
        login(request, user)

    return JsonResponse({"user": _user_payload(user)})


@require_GET
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.CEO, UserProfile.Role.COO)
def dashboard_overview(_: HttpRequest):
    visitors = TrafficPoint.objects.filter(period=TrafficPoint.Period.MONTHLY).aggregate(total=models.Sum("visitors"))["total"] or 0
    subscribers = NewsletterSubscriber.objects.count() or max(1, UserProfile.objects.count() * 4)
    active_users = UserProfile.objects.filter(status=UserProfile.Status.ACTIVE).count()
    revenue = int(visitors * 2)

    recent = [
        {
            "id": log.id,
            "message": log.message,
            "kind": log.kind,
            "created_at": log.created_at.isoformat(),
            "actor": log.actor.username if log.actor else "System",
        }
        for log in ActivityLog.objects.select_related("actor")[:10]
    ]

    return JsonResponse(
        {
            "stats": {
                "visitors": visitors,
                "subscribers": subscribers,
                "active_users": active_users,
                "revenue": revenue,
            },
            "traffic": {
                period: list(TrafficPoint.objects.filter(period=period).values("label", "visitors"))
                for period in [TrafficPoint.Period.DAILY, TrafficPoint.Period.WEEKLY, TrafficPoint.Period.MONTHLY]
            },
            "user_growth": list(UserGrowthPoint.objects.values("label", "users")),
            "recent_activity": recent,
        }
    )


@require_GET
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.CEO, UserProfile.Role.COO)
def analytics(_: HttpRequest):
    labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    bounce = [{"label": l, "rate": 32 + (i * 2) + random.randint(-2, 2)} for i, l in enumerate(labels)]
    duration = [{"label": l, "minutes": round(3.2 + i * 0.25 + random.random(), 2)} for i, l in enumerate(labels)]
    trends = [{"label": f"Week {i}", "sessions": random.randint(35000, 60000), "unique": random.randint(25000, 42000)} for i in range(1, 7)]
    return JsonResponse(
        {
            "traffic_trends": trends,
            "bounce_rate": bounce,
            "session_duration": duration,
            "top_pages": list(TopPage.objects.values("path", "views", "trend_pct")),
            "live_visitors": random.randint(250, 800),
        }
    )


@csrf_exempt
@require_http_methods(["GET", "POST"])
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.CEO)
def users_collection(request: HttpRequest):
    if request.method == "GET":
        users = User.objects.select_related("profile").all().order_by("id")
        return JsonResponse({"results": [_user_payload(u) for u in users]})

    body, files = _request_data(request)
    if not body.get("username") or not body.get("email") or not body.get("password"):
        return JsonResponse({"error": "username, email and password are required"}, status=400)

    user = User.objects.create_user(
        username=body["username"],
        email=body["email"],
        password=body["password"],
        first_name=body.get("first_name", ""),
        last_name=body.get("last_name", ""),
    )
    role = body.get("role", UserProfile.Role.COO)
    if role not in LOGIN_ALLOWED_ROLES:
        role = UserProfile.Role.COO
    if _get_role(request.user) == UserProfile.Role.CEO and role not in {UserProfile.Role.COO}:
        role = UserProfile.Role.COO
    UserProfile.objects.create(
        user=user,
        role=role,
        status=body.get("status", UserProfile.Status.INVITED),
        avatar_url=body.get("avatar_url", ""),
        avatar_file=files.get("avatar_image"),
    )
    ActivityLog.objects.create(actor=request.user, kind=ActivityLog.Kind.CREATE, message=f"Created user {user.username}")
    return JsonResponse({"user": _user_payload(user)}, status=201)


@csrf_exempt
@require_http_methods(["GET", "PATCH", "DELETE"])
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.CEO)
def user_detail(request: HttpRequest, user_id: int):
    try:
        user = User.objects.select_related("profile").get(pk=user_id)
    except User.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)

    if request.method == "GET":
        return JsonResponse({"user": _user_payload(user)})

    if request.method == "DELETE":
        username = user.username
        user.delete()
        ActivityLog.objects.create(actor=request.user, kind=ActivityLog.Kind.DELETE, message=f"Deleted user {username}")
        return JsonResponse({"ok": True})

    body, files = _request_data(request)
    user.first_name = body.get("first_name", user.first_name)
    user.last_name = body.get("last_name", user.last_name)
    user.email = body.get("email", user.email)
    if body.get("password"):
        user.set_password(body["password"])
    user.save()

    profile, _ = UserProfile.objects.get_or_create(user=user)
    if _get_role(request.user) == UserProfile.Role.CEO:
        profile.role = body.get("role", profile.role)
        if profile.role not in {UserProfile.Role.COO}:
            profile.role = UserProfile.Role.COO
    else:
        profile.role = body.get("role", profile.role)
        if profile.role not in LOGIN_ALLOWED_ROLES:
            profile.role = UserProfile.Role.COO
    profile.status = body.get("status", profile.status)
    profile.avatar_url = body.get("avatar_url", profile.avatar_url)
    if files.get("avatar_image"):
        profile.avatar_file = files.get("avatar_image")
    profile.save()

    ActivityLog.objects.create(actor=request.user, kind=ActivityLog.Kind.UPDATE, message=f"Updated user {user.username}")
    return JsonResponse({"user": _user_payload(user)})


def _content_scope_for_user(request: HttpRequest):
    role = _get_role(request.user)
    if role in {UserProfile.Role.ADMIN, UserProfile.Role.CEO}:
        return BlogPost.objects.select_related("author").all(), GalleryImage.objects.select_related("uploaded_by").all()
    return BlogPost.objects.select_related("author").filter(author=request.user), GalleryImage.objects.select_related("uploaded_by").filter(uploaded_by=request.user)


@csrf_exempt
@require_http_methods(["GET", "POST"])
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.CEO, UserProfile.Role.COO)
def posts_collection(request: HttpRequest):
    posts_qs, _ = _content_scope_for_user(request)
    if request.method == "GET":
        posts = []
        for p in posts_qs:
            analytics = getattr(p, "analytics", None)
            posts.append(
                {
                    "id": p.id,
                    "title": p.title,
                    "description": p.description,
                    "status": p.status,
                    "body": p.body,
                    "body_format": p.body_format,
                    "hero_image_url": p.hero_image_url,
                    "author": p.author.username if p.author else None,
                    "created_at": p.created_at.isoformat(),
                    "analytics": {
                        "views": analytics.views if analytics else 0,
                        "likes": analytics.likes if analytics else 0,
                        "comments": analytics.comments if analytics else 0,
                    },
                }
            )
        return JsonResponse({"results": posts})

    body = _json_body(request)
    if not body.get("title"):
        return JsonResponse({"error": "title is required"}, status=400)
    post = BlogPost.objects.create(
        title=body["title"],
        description=body.get("description", ""),
        body=body.get("body", ""),
        body_format=body.get("body_format", BlogPost.BodyFormat.MARKDOWN),
        hero_image_url=body.get("hero_image_url", ""),
        status=body.get("status", BlogPost.Status.DRAFT),
        author=request.user,
        published_at=timezone.now() if body.get("status") == BlogPost.Status.PUBLISHED else None,
    )
    ContentAnalytics.objects.get_or_create(post=post)
    ActivityLog.objects.create(actor=request.user, kind=ActivityLog.Kind.CREATE, message=f'Created post "{post.title}"')
    return JsonResponse({"id": post.id}, status=201)


@csrf_exempt
@require_http_methods(["PATCH", "DELETE"])
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.CEO, UserProfile.Role.COO)
def post_detail(request: HttpRequest, post_id: int):
    try:
        post = BlogPost.objects.get(pk=post_id)
    except BlogPost.DoesNotExist:
        return JsonResponse({"error": "Post not found"}, status=404)

    role = _get_role(request.user)
    if role == UserProfile.Role.COO and post.author_id != request.user.id:
        return JsonResponse({"error": "COO can modify only own posts"}, status=403)

    if request.method == "DELETE":
        title = post.title
        post.delete()
        ActivityLog.objects.create(actor=request.user, kind=ActivityLog.Kind.DELETE, message=f'Deleted post "{title}"')
        return JsonResponse({"ok": True})

    body = _json_body(request)
    post.title = body.get("title", post.title)
    post.description = body.get("description", post.description)
    post.body = body.get("body", post.body)
    post.body_format = body.get("body_format", post.body_format)
    post.hero_image_url = body.get("hero_image_url", post.hero_image_url)
    post.status = body.get("status", post.status)
    if post.status == BlogPost.Status.PUBLISHED and not post.published_at:
        post.published_at = timezone.now()
    post.save()
    ActivityLog.objects.create(actor=request.user, kind=ActivityLog.Kind.UPDATE, message=f'Updated post "{post.title}"')
    return JsonResponse({"ok": True})


@csrf_exempt
@require_http_methods(["GET", "POST"])
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.CEO, UserProfile.Role.COO)
def gallery_collection(request: HttpRequest):
    _, gallery_qs = _content_scope_for_user(request)
    if request.method == "GET":
        return JsonResponse({"results": list(gallery_qs.values("id", "caption", "image_url", "created_at"))})

    body = _json_body(request)
    if not body.get("image_url"):
        return JsonResponse({"error": "image_url is required"}, status=400)
    image = GalleryImage.objects.create(caption=body.get("caption", ""), image_url=body["image_url"], uploaded_by=request.user)
    ActivityLog.objects.create(actor=request.user, kind=ActivityLog.Kind.CREATE, message="Uploaded gallery image")
    return JsonResponse({"id": image.id}, status=201)


@csrf_exempt
@require_http_methods(["DELETE"])
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.CEO, UserProfile.Role.COO)
def gallery_detail(request: HttpRequest, image_id: int):
    try:
        image = GalleryImage.objects.get(pk=image_id)
    except GalleryImage.DoesNotExist:
        return JsonResponse({"error": "Image not found"}, status=404)

    role = _get_role(request.user)
    if role == UserProfile.Role.COO and image.uploaded_by_id != request.user.id:
        return JsonResponse({"error": "COO can delete only own media"}, status=403)

    image.delete()
    ActivityLog.objects.create(actor=request.user, kind=ActivityLog.Kind.DELETE, message="Deleted gallery image")
    return JsonResponse({"ok": True})


@require_GET
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.CEO, UserProfile.Role.COO)
def content_analytics(request: HttpRequest):
    posts_qs, _ = _content_scope_for_user(request)
    rows = []
    for post in posts_qs:
        analytics = getattr(post, "analytics", None)
        rows.append(
            {
                "post_id": post.id,
                "title": post.title,
                "views": analytics.views if analytics else 0,
                "likes": analytics.likes if analytics else 0,
                "comments": analytics.comments if analytics else 0,
            }
        )
    return JsonResponse({"results": rows})


def _task_scope_for_user(request: HttpRequest):
    role = _get_role(request.user)
    qs = Task.objects.select_related("assignee", "created_by").prefetch_related("subtasks", "comments", "followups")
    if role in {UserProfile.Role.ADMIN, UserProfile.Role.CEO}:
        return qs
    return qs.filter(Q(assignee=request.user) | Q(created_by=request.user))


@require_GET
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.CEO, UserProfile.Role.COO)
def tasks_board(request: HttpRequest):
    qs = _task_scope_for_user(request)
    if request.GET.get("assignee_id"):
        qs = qs.filter(assignee_id=request.GET["assignee_id"])
    if request.GET.get("due_from"):
        qs = qs.filter(due_date__gte=request.GET["due_from"])
    if request.GET.get("due_to"):
        qs = qs.filter(due_date__lte=request.GET["due_to"])

    grouped = {"pending": [], "in_progress": [], "completed": []}
    for task in qs:
        grouped[task.column].append(_task_payload(task))
    return JsonResponse({"columns": grouped})


@csrf_exempt
@require_http_methods(["POST"])
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.CEO, UserProfile.Role.COO)
def task_create(request: HttpRequest):
    body = _json_body(request)
    if not body.get("title"):
        return JsonResponse({"error": "title is required"}, status=400)

    assignee = User.objects.filter(pk=body.get("assignee_id")).first() if body.get("assignee_id") else None
    role = _get_role(request.user)
    if role == UserProfile.Role.CEO and assignee:
        assignee_role = _get_role(assignee)
        if assignee_role not in {UserProfile.Role.CEO, UserProfile.Role.COO}:
            return JsonResponse({"error": "CEO can assign only to CEO/COO"}, status=403)

    task = Task.objects.create(
        title=body["title"],
        description=body.get("description", ""),
        column=body.get("column", Task.Column.PENDING),
        priority=body.get("priority", Task.Priority.MEDIUM),
        due_date=body.get("due_date") or None,
        position=Decimal(str(body.get("position", 1000))),
        parent_id=body.get("parent_id"),
        assignee=assignee,
        created_by=request.user,
        labels=body.get("labels", []),
        properties=body.get("properties", {}),
        content=body.get("content", []),
    )
    ActivityLog.objects.create(actor=request.user, kind=ActivityLog.Kind.CREATE, message=f'Created task "{task.title}"')
    return JsonResponse({"task": _task_payload(task)}, status=201)


@csrf_exempt
@require_http_methods(["GET", "PATCH", "DELETE"])
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.CEO, UserProfile.Role.COO)
def task_detail(request: HttpRequest, task_id: int):
    try:
        task = Task.objects.select_related("assignee", "created_by").get(pk=task_id)
    except Task.DoesNotExist:
        return JsonResponse({"error": "Task not found"}, status=404)

    role = _get_role(request.user)
    if role == UserProfile.Role.COO and not (task.assignee_id == request.user.id or task.created_by_id == request.user.id):
        return JsonResponse({"error": "COO can access only related tasks"}, status=403)

    if request.method == "GET":
        payload = _task_payload(task)
        payload["comments"] = [
            {"id": c.id, "message": c.message, "author": c.author.username if c.author else None, "created_at": c.created_at.isoformat()}
            for c in task.comments.select_related("author").all()
        ]
        payload["followups"] = [
            {"id": f.id, "message": f.message, "status": f.status, "requester": f.requester.username if f.requester else None}
            for f in task.followups.select_related("requester").all()
        ]
        return JsonResponse({"task": payload})

    if request.method == "DELETE":
        if role == UserProfile.Role.COO and task.created_by_id != request.user.id:
            return JsonResponse({"error": "COO can delete only own-created tasks"}, status=403)
        title = task.title
        task.delete()
        ActivityLog.objects.create(actor=request.user, kind=ActivityLog.Kind.DELETE, message=f'Deleted task "{title}"')
        return JsonResponse({"ok": True})

    body = _json_body(request)
    task.title = body.get("title", task.title)
    task.description = body.get("description", task.description)
    task.column = body.get("column", task.column)
    task.priority = body.get("priority", task.priority)
    task.parent_id = body.get("parent_id", task.parent_id)
    task.properties = body.get("properties", task.properties)
    task.labels = body.get("labels", task.labels)
    task.content = body.get("content", task.content)
    if "position" in body:
        task.position = Decimal(str(body["position"]))
    if body.get("due_date") is not None:
        task.due_date = body.get("due_date") or None
    if body.get("assignee_id") is not None:
        task.assignee = User.objects.filter(pk=body["assignee_id"]).first()
    task.save()
    ActivityLog.objects.create(actor=request.user, kind=ActivityLog.Kind.UPDATE, message=f'Updated task "{task.title}"')
    return JsonResponse({"task": _task_payload(task)})


@csrf_exempt
@require_http_methods(["POST"])
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.CEO, UserProfile.Role.COO)
def task_move(request: HttpRequest, task_id: int):
    try:
        task = Task.objects.get(pk=task_id)
    except Task.DoesNotExist:
        return JsonResponse({"error": "Task not found"}, status=404)

    role = _get_role(request.user)
    if role == UserProfile.Role.COO and not (task.assignee_id == request.user.id or task.created_by_id == request.user.id):
        return JsonResponse({"error": "COO can move only related tasks"}, status=403)

    body = _json_body(request)
    task.column = body.get("column", task.column)
    if "position" in body:
        task.position = Decimal(str(body["position"]))
    task.save(update_fields=["column", "position", "updated_at"])
    ActivityLog.objects.create(actor=request.user, kind=ActivityLog.Kind.UPDATE, message=f'Moved task "{task.title}" to {task.column}')
    return JsonResponse({"task": _task_payload(task)})


@csrf_exempt
@require_http_methods(["POST"])
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.CEO, UserProfile.Role.COO)
def task_comment_create(request: HttpRequest, task_id: int):
    try:
        task = Task.objects.get(pk=task_id)
    except Task.DoesNotExist:
        return JsonResponse({"error": "Task not found"}, status=404)

    message = _json_body(request).get("message", "").strip()
    if not message:
        return JsonResponse({"error": "message is required"}, status=400)

    comment = TaskComment.objects.create(task=task, author=request.user, message=message)
    return JsonResponse({"comment": {"id": comment.id, "message": comment.message, "created_at": comment.created_at.isoformat()}}, status=201)


@csrf_exempt
@require_http_methods(["POST"])
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.CEO, UserProfile.Role.COO)
def task_followup_create(request: HttpRequest, task_id: int):
    try:
        task = Task.objects.get(pk=task_id)
    except Task.DoesNotExist:
        return JsonResponse({"error": "Task not found"}, status=404)

    message = _json_body(request).get("message", "").strip()
    if not message:
        return JsonResponse({"error": "message is required"}, status=400)

    followup = TaskFollowUp.objects.create(task=task, requester=request.user, message=message)
    return JsonResponse({"followup": {"id": followup.id, "message": followup.message, "status": followup.status}}, status=201)


@require_GET
@roles_required(UserProfile.Role.ADMIN)
def performance(_: HttpRequest):
    latest = PerformanceMetric.objects.order_by("-id").first()
    cards = {
        "page_load_ms": latest.page_load_ms if latest else 0,
        "api_response_ms": latest.api_response_ms if latest else 0,
        "error_rate_pct": float(latest.error_rate_pct) if latest else 0,
    }
    trend = list(PerformanceMetric.objects.values("label", "page_load_ms", "api_response_ms", "error_rate_pct"))
    servers = list(ServerStatus.objects.values("id", "name", "region", "status"))
    return JsonResponse({"cards": cards, "trend": trend, "servers": servers})


@require_GET
@roles_required(UserProfile.Role.ADMIN)
def activity_logs(request: HttpRequest):
    limit = int(request.GET.get("limit", 50))
    logs = [
        {
            "id": log.id,
            "message": log.message,
            "kind": log.kind,
            "actor": log.actor.username if log.actor else "System",
            "metadata": log.metadata,
            "created_at": log.created_at.isoformat(),
        }
        for log in ActivityLog.objects.select_related("actor").all()[:limit]
    ]
    return JsonResponse({"results": logs})


@require_GET
@roles_required(UserProfile.Role.ADMIN)
def admin_summary(_: HttpRequest):
    return JsonResponse(
        {
            "users": User.objects.count(),
            "posts": BlogPost.objects.count(),
            "tasks": Task.objects.count(),
            "logs": ActivityLog.objects.count(),
            "tasks_by_column": list(Task.objects.values("column").annotate(count=Count("id")).order_by("column")),
        }
    )


@require_GET
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.CEO)
def members_list(_: HttpRequest):
    users = User.objects.select_related("profile").all().order_by("first_name", "last_name", "username")
    return JsonResponse({"results": [_user_payload(u) for u in users]})


@csrf_exempt
@require_http_methods(["GET", "POST", "PATCH"])
def member_requests(request: HttpRequest):
    if request.method == "POST":
        body = _json_body(request)
        if not body.get("name") or not body.get("email"):
            return JsonResponse({"error": "name and email are required"}, status=400)
        obj = MemberRequest.objects.create(
            name=body["name"],
            email=body["email"],
            message=body.get("message", ""),
            requested_role=body.get("requested_role", MemberRequest.RequestedRole.STAFF),
            requested_by=request.user if request.user.is_authenticated else None,
        )
        return JsonResponse({"id": obj.id}, status=201)

    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=401)

    if _get_role(request.user) not in {UserProfile.Role.ADMIN, UserProfile.Role.CEO}:
        return JsonResponse({"error": "Forbidden for this role"}, status=403)

    if request.method == "PATCH":
        body = _json_body(request)
        req_id = body.get("id")
        status = body.get("status")
        req = MemberRequest.objects.filter(pk=req_id).first()
        if not req:
            return JsonResponse({"error": "Request not found"}, status=404)
        if status not in {MemberRequest.Status.PENDING, MemberRequest.Status.APPROVED, MemberRequest.Status.REJECTED}:
            return JsonResponse({"error": "Invalid status"}, status=400)
        req.status = status
        req.save(update_fields=["status", "updated_at"])
        return JsonResponse({"ok": True})

    return JsonResponse({"results": list(MemberRequest.objects.values())})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def newsletter_collection(request: HttpRequest):
    if request.method == "POST":
        body = _json_body(request)
        email = body.get("email", "").strip().lower()
        if not email:
            return JsonResponse({"error": "email is required"}, status=400)
        obj, _ = NewsletterSubscriber.objects.get_or_create(email=email, defaults={"name": body.get("name", "")})
        return JsonResponse({"id": obj.id}, status=201)

    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=401)
    if _get_role(request.user) not in {UserProfile.Role.ADMIN, UserProfile.Role.CEO}:
        return JsonResponse({"error": "Forbidden for this role"}, status=403)
    return JsonResponse({"results": list(NewsletterSubscriber.objects.values("id", "email", "name", "created_at"))})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def donations_collection(request: HttpRequest):
    if request.method == "POST":
        body = _json_body(request)
        if not body.get("donor_name") or not body.get("donor_email") or body.get("amount") is None:
            return JsonResponse({"error": "donor_name, donor_email and amount are required"}, status=400)
        donation = Donation.objects.create(
            donor_name=body["donor_name"],
            donor_email=body["donor_email"],
            amount=Decimal(str(body["amount"])),
            currency=body.get("currency", "USD"),
            message=body.get("message", ""),
            anonymous=bool(body.get("anonymous", False)),
        )
        return JsonResponse({"id": donation.id}, status=201)

    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=401)
    if _get_role(request.user) not in {UserProfile.Role.ADMIN, UserProfile.Role.CEO}:
        return JsonResponse({"error": "Forbidden for this role"}, status=403)
    return JsonResponse({"results": list(Donation.objects.values())})


@csrf_exempt
@require_http_methods(["GET", "POST"])
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.CEO, UserProfile.Role.COO)
def testimonials_collection(request: HttpRequest):
    if request.method == "GET":
        return JsonResponse(
            {
                "results": [
                    {
                        "id": row.id,
                        "name": row.name,
                        "role_title": row.role_title,
                        "company": row.company,
                        "quote": row.quote,
                        "avatar_url": row.avatar_url,
                        "rating": row.rating,
                        "featured": row.featured,
                        "created_by": row.created_by.username if row.created_by else None,
                        "created_at": row.created_at.isoformat(),
                    }
                    for row in Testimonial.objects.select_related("created_by").all()
                ]
            }
        )

    body = _json_body(request)
    if not body.get("name") or not body.get("quote"):
        return JsonResponse({"error": "name and quote are required"}, status=400)
    testimonial = Testimonial.objects.create(
        name=body["name"],
        role_title=body.get("role_title", ""),
        company=body.get("company", ""),
        quote=body["quote"],
        avatar_url=body.get("avatar_url", ""),
        rating=max(1, min(5, int(body.get("rating", 5)))),
        featured=bool(body.get("featured", False)),
        created_by=request.user,
    )
    ActivityLog.objects.create(actor=request.user, kind=ActivityLog.Kind.CREATE, message=f'Created testimonial "{testimonial.name}"')
    return JsonResponse({"id": testimonial.id}, status=201)


@csrf_exempt
@require_http_methods(["PATCH", "DELETE"])
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.CEO, UserProfile.Role.COO)
def testimonial_detail(request: HttpRequest, testimonial_id: int):
    testimonial = Testimonial.objects.filter(pk=testimonial_id).first()
    if not testimonial:
        return JsonResponse({"error": "Testimonial not found"}, status=404)

    if request.method == "DELETE":
        name = testimonial.name
        testimonial.delete()
        ActivityLog.objects.create(actor=request.user, kind=ActivityLog.Kind.DELETE, message=f'Deleted testimonial "{name}"')
        return JsonResponse({"ok": True})

    body = _json_body(request)
    testimonial.name = body.get("name", testimonial.name)
    testimonial.role_title = body.get("role_title", testimonial.role_title)
    testimonial.company = body.get("company", testimonial.company)
    testimonial.quote = body.get("quote", testimonial.quote)
    testimonial.avatar_url = body.get("avatar_url", testimonial.avatar_url)
    if "rating" in body:
        testimonial.rating = max(1, min(5, int(body["rating"])))
    if "featured" in body:
        testimonial.featured = bool(body["featured"])
    testimonial.save()
    ActivityLog.objects.create(actor=request.user, kind=ActivityLog.Kind.UPDATE, message=f'Updated testimonial "{testimonial.name}"')
    return JsonResponse({"ok": True})


@csrf_exempt
@require_http_methods(["GET", "POST"])
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.CEO, UserProfile.Role.COO)
def team_collection(request: HttpRequest):
    if request.method == "GET":
        return JsonResponse(
            {
                "results": [
                    {
                        "id": row.id,
                        "name": row.name,
                        "role_title": row.role_title,
                        "bio": row.bio,
                        "image_url": row.image_url,
                        "email": row.email,
                        "linkedin_url": row.linkedin_url,
                        "is_active": row.is_active,
                        "display_order": row.display_order,
                    }
                    for row in TeamMember.objects.all()
                ]
            }
        )

    body = _json_body(request)
    if not body.get("name") or not body.get("role_title"):
        return JsonResponse({"error": "name and role_title are required"}, status=400)
    member = TeamMember.objects.create(
        name=body["name"],
        role_title=body["role_title"],
        bio=body.get("bio", ""),
        image_url=body.get("image_url", ""),
        email=body.get("email", ""),
        linkedin_url=body.get("linkedin_url", ""),
        is_active=bool(body.get("is_active", True)),
        display_order=int(body.get("display_order", 0)),
    )
    ActivityLog.objects.create(actor=request.user, kind=ActivityLog.Kind.CREATE, message=f'Created team member "{member.name}"')
    return JsonResponse({"id": member.id}, status=201)


@csrf_exempt
@require_http_methods(["PATCH", "DELETE"])
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.CEO, UserProfile.Role.COO)
def team_detail(request: HttpRequest, member_id: int):
    member = TeamMember.objects.filter(pk=member_id).first()
    if not member:
        return JsonResponse({"error": "Team member not found"}, status=404)

    if request.method == "DELETE":
        name = member.name
        member.delete()
        ActivityLog.objects.create(actor=request.user, kind=ActivityLog.Kind.DELETE, message=f'Deleted team member "{name}"')
        return JsonResponse({"ok": True})

    body = _json_body(request)
    member.name = body.get("name", member.name)
    member.role_title = body.get("role_title", member.role_title)
    member.bio = body.get("bio", member.bio)
    member.image_url = body.get("image_url", member.image_url)
    member.email = body.get("email", member.email)
    member.linkedin_url = body.get("linkedin_url", member.linkedin_url)
    if "is_active" in body:
        member.is_active = bool(body["is_active"])
    if "display_order" in body:
        member.display_order = int(body["display_order"])
    member.save()
    ActivityLog.objects.create(actor=request.user, kind=ActivityLog.Kind.UPDATE, message=f'Updated team member "{member.name}"')
    return JsonResponse({"ok": True})


@csrf_exempt
@require_http_methods(["GET", "POST", "PATCH", "DELETE"])
@api_login_required
def brainstorm_collection(request: HttpRequest):
    role = _get_role(request.user)
    own_or_shared = Q(author=request.user) | Q(share_with_all=True) | Q(shared_with=request.user)

    if request.method == "GET":
        ideas = BrainstormIdea.objects.filter(own_or_shared).distinct().order_by("-updated_at")
        return JsonResponse(
            {
                "results": [
                    {
                        "id": idea.id,
                        "title": idea.title,
                        "content": idea.content,
                        "status": idea.status,
                        "author": idea.author.username,
                        "share_with_all": idea.share_with_all,
                        "shared_with": [u.username for u in idea.shared_with.all()],
                        "updated_at": idea.updated_at.isoformat(),
                    }
                    for idea in ideas
                ]
            }
        )

    body = _json_body(request)

    if request.method == "POST":
        if not body.get("title"):
            return JsonResponse({"error": "title is required"}, status=400)
        idea = BrainstormIdea.objects.create(
            title=body["title"],
            content=body.get("content", ""),
            status=body.get("status", BrainstormIdea.Status.DRAFT),
            author=request.user,
            share_with_all=bool(body.get("share_with_all", False)),
        )
        shared_ids = body.get("shared_user_ids", [])
        if shared_ids:
            idea.shared_with.set(User.objects.filter(id__in=shared_ids))
        return JsonResponse({"id": idea.id}, status=201)

    idea = BrainstormIdea.objects.filter(pk=body.get("id")).first()
    if not idea:
        return JsonResponse({"error": "Idea not found"}, status=404)
    if idea.author_id != request.user.id and role != UserProfile.Role.ADMIN:
        return JsonResponse({"error": "Only author or admin can modify"}, status=403)

    if request.method == "DELETE":
        idea.delete()
        return JsonResponse({"ok": True})

    idea.title = body.get("title", idea.title)
    idea.content = body.get("content", idea.content)
    idea.status = body.get("status", idea.status)
    if "share_with_all" in body:
        idea.share_with_all = bool(body["share_with_all"])
    idea.save()
    if "shared_user_ids" in body:
        idea.shared_with.set(User.objects.filter(id__in=body.get("shared_user_ids", [])))
    return JsonResponse({"ok": True})
