from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from api.models import (
    ActivityLog,
    BlogPost,
    PerformanceMetric,
    ServerStatus,
    Task,
    TopPage,
    TrafficPoint,
    UserGrowthPoint,
    UserProfile,
)


class Command(BaseCommand):
    help = "Seed demo data for Geoclimatz admin backend"

    def handle(self, *args, **options):
        User = get_user_model()

        admin, created = User.objects.get_or_create(
            username='admin',
            defaults={'email': 'admin@geoclimatz.internal', 'is_staff': True, 'is_superuser': True},
        )
        admin.set_password('Admin123!')
        admin.is_staff = True
        admin.is_superuser = True
        admin.save()
        UserProfile.objects.get_or_create(user=admin, defaults={'role': UserProfile.Role.ADMIN, 'status': UserProfile.Status.ACTIVE})

        ceo, _ = User.objects.get_or_create(username='ceo', defaults={'email': 'ceo@geoclimatz.internal'})
        ceo.set_password('Admin123!')
        ceo.save()
        UserProfile.objects.get_or_create(user=ceo, defaults={'role': UserProfile.Role.CEO})

        if not TrafficPoint.objects.exists():
            for lbl, val in [('Mon',4200), ('Tue',5100), ('Wed',4900), ('Thu',6200), ('Fri',5900), ('Sat',3400), ('Sun',3100)]:
                TrafficPoint.objects.create(period=TrafficPoint.Period.DAILY, label=lbl, visitors=val)
            for lbl, val in [('W1',28400), ('W2',31200), ('W3',29800), ('W4',34100), ('W5',33600), ('W6',35900)]:
                TrafficPoint.objects.create(period=TrafficPoint.Period.WEEKLY, label=lbl, visitors=val)
            for lbl, val in [('Jan',118000), ('Feb',124500), ('Mar',131200), ('Apr',128400), ('May',139800), ('Jun',142300)]:
                TrafficPoint.objects.create(period=TrafficPoint.Period.MONTHLY, label=lbl, visitors=val)

        if not UserGrowthPoint.objects.exists():
            for lbl, users in [('Jan', 820), ('Feb',1040), ('Mar',1280), ('Apr',1520), ('May',1890), ('Jun',2340)]:
                UserGrowthPoint.objects.create(label=lbl, users=users)

        if not TopPage.objects.exists():
            TopPage.objects.bulk_create([
                TopPage(path='/pricing', views=142300, trend_pct=8.2),
                TopPage(path='/docs/api', views=98400, trend_pct=5.1),
                TopPage(path='/dashboard', views=54100, trend_pct=11.0),
            ])

        if not BlogPost.objects.exists():
            BlogPost.objects.create(title='Q2 Sustainability Report', body='Demo content', status=BlogPost.Status.PUBLISHED, author=ceo, published_at=timezone.now())
            BlogPost.objects.create(title='Internal API updates', body='Draft notes', status=BlogPost.Status.DRAFT, author=admin)

        if not Task.objects.exists():
            Task.objects.create(title='Finalize SOC2 evidence pack', column=Task.Column.PENDING, priority=Task.Priority.HIGH, assignee=admin, created_by=ceo)
            Task.objects.create(title='Migrate legacy CSV importers', column=Task.Column.IN_PROGRESS, priority=Task.Priority.HIGH, assignee=ceo, created_by=admin)
            Task.objects.create(title='Ship dark mode for admin', column=Task.Column.COMPLETED, priority=Task.Priority.MEDIUM, assignee=admin, created_by=ceo)

        if not PerformanceMetric.objects.exists():
            for row in [('00:00',480,140,0.13), ('04:00',410,115,0.11), ('08:00',520,165,0.17), ('12:00',390,105,0.09), ('16:00',440,128,0.12), ('20:00',400,112,0.10)]:
                PerformanceMetric.objects.create(label=row[0], page_load_ms=row[1], api_response_ms=row[2], error_rate_pct=row[3])

        if not ServerStatus.objects.exists():
            ServerStatus.objects.bulk_create([
                ServerStatus(name='api-us-east', region='Virginia', status=ServerStatus.Status.ONLINE),
                ServerStatus(name='api-eu-west', region='Frankfurt', status=ServerStatus.Status.ONLINE),
                ServerStatus(name='legacy-importer', region='Tokyo', status=ServerStatus.Status.OFFLINE),
            ])

        if not ActivityLog.objects.exists():
            ActivityLog.objects.create(actor=admin, kind=ActivityLog.Kind.CREATE, message='User John created a post')
            ActivityLog.objects.create(actor=admin, kind=ActivityLog.Kind.DELETE, message='Admin deleted a user')

        self.stdout.write(self.style.SUCCESS('Demo data seeded. Admin login: admin / Admin123!'))
