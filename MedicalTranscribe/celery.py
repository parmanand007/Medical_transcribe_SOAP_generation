import os
from celery import Celery

# Ensure Django settings are loaded
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "MedicalTranscribe.settings")

app = Celery("MedicalTranscribe")

# Load config from Django settings
app.config_from_object("django.conf:settings", namespace="CELERY")

# Discover tasks automatically from all installed apps
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
