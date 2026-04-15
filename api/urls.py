from django.urls import path

from . import views

urlpatterns = [
    path('health/', views.health),
    path('auth/login/', views.auth_login),
    path('auth/logout/', views.auth_logout),
    path('auth/me/', views.auth_me),
    path('auth/profile/', views.auth_profile),

    path('dashboard/overview/', views.dashboard_overview),
    path('analytics/', views.analytics),

    path('users/', views.users_collection),
    path('users/<int:user_id>/', views.user_detail),

    path('content/posts/', views.posts_collection),
    path('content/posts/<int:post_id>/', views.post_detail),
    path('content/gallery/', views.gallery_collection),
    path('content/gallery/<int:image_id>/', views.gallery_detail),
    path('content/analytics/', views.content_analytics),

    path('tasks/board/', views.tasks_board),
    path('tasks/', views.task_create),
    path('tasks/<int:task_id>/', views.task_detail),
    path('tasks/<int:task_id>/move/', views.task_move),
    path('tasks/<int:task_id>/comments/', views.task_comment_create),
    path('tasks/<int:task_id>/followups/', views.task_followup_create),

    path('performance/', views.performance),
    path('activity-logs/', views.activity_logs),
    path('admin/summary/', views.admin_summary),
    path('members/', views.members_list),
    path('member-requests/', views.member_requests),
    path('newsletter/', views.newsletter_collection),
    path('donations/', views.donations_collection),
    path('testimonials/', views.testimonials_collection),
    path('testimonials/<int:testimonial_id>/', views.testimonial_detail),
    path('team/', views.team_collection),
    path('team/<int:member_id>/', views.team_detail),
    path('brainstorm/', views.brainstorm_collection),
]
