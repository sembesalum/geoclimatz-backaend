from django.contrib import admin

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


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "status", "updated_at")
    list_filter = ("role", "status")
    search_fields = ("user__username", "user__email")


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "column", "priority", "assignee", "due_date", "position")
    list_filter = ("column", "priority")
    search_fields = ("title", "description")


admin.site.register(TrafficPoint)
admin.site.register(UserGrowthPoint)
admin.site.register(TopPage)
admin.site.register(BlogPost)
admin.site.register(GalleryImage)
admin.site.register(TaskComment)
admin.site.register(PerformanceMetric)
admin.site.register(ServerStatus)
admin.site.register(ActivityLog)
admin.site.register(ContentAnalytics)
admin.site.register(TaskFollowUp)
admin.site.register(MemberRequest)
admin.site.register(NewsletterSubscriber)
admin.site.register(Donation)
admin.site.register(BrainstormIdea)
admin.site.register(Testimonial)
admin.site.register(TeamMember)
