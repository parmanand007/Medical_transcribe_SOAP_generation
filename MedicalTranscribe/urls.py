from django.contrib import admin
from django.urls import path
from .views import AudioUploadView, AudioListView, TranscriptionStatusView

urlpatterns = [
    path('admin/', admin.site.urls),

    # API Endpoints
    path("api/audio/upload/", AudioUploadView.as_view(), name="audio-upload"),
    path("api/audio/list/", AudioListView.as_view(), name="audio-list"),
    path("api/audio/<uuid:audio_id>/status/", TranscriptionStatusView.as_view(), name="transcription-status"),
]
