from django.conf import settings
from django.db import models
import uuid


class AudioFile(models.Model):
    """
    Stores metadata and uploaded audio file (backed by S3 using FileField).
    """
    STATUS_CHOICES = (
        ("uploaded", "Uploaded"),
        ("transcription_started", "Transcription Started"),
        ("transcription_completed", "Transcription Completed"),
        ("failed", "Failed"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    original_filename = models.CharField(max_length=512)
    file = models.FileField(
        upload_to="input/",  # optional custom path in S3
        max_length=1024,
        help_text="Audio file stored on S3 via Django storage backend"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=32, choices=STATUS_CHOICES, default="uploaded", db_index=True
    )
    metadata = models.JSONField(null=True, blank=True)  # e.g., sample rate, duration

    class Meta:
        ordering = ["-uploaded_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["uploaded_at"]),
        ]

    def __str__(self):
        return f"{self.original_filename} ({self.status})"

    @property
    def s3_uri(self):
        """
        Returns S3 URI if using S3 storage; otherwise returns None.
        """
        storage = self.file.storage
        if hasattr(storage, "bucket_name"):
            return f"s3://{storage.bucket_name}/{self.file.name}"
        return None

    @property
    def file_url(self):
        """
        Returns an HTTPS URL or presigned URL if using S3.
        """
        try:
            return self.file.url if self.file else None
        except Exception:
            return None


class TranscriptionJob(models.Model):
    """
    Represents a single AWS Transcribe job for a given audio file.
    """
    STATUS_CHOICES = (
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    audio = models.ForeignKey(
        AudioFile,
        on_delete=models.CASCADE,
        related_name="transcription_jobs"
    )
    aws_job_name = models.CharField(max_length=255, unique=True)
    status = models.CharField(
        max_length=32, choices=STATUS_CHOICES, default="in_progress", db_index=True
    )
    transcript_s3_uri = models.CharField(max_length=1024, null=True, blank=True)
    transcript_text = models.TextField(null=True, blank=True)
    transcript_full_json = models.JSONField(null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["started_at"]),
        ]

    def __str__(self):
        return f"{self.aws_job_name} ({self.status})"


class SOAPNote(models.Model):
    """
    Stores the structured SOAP (Subjective, Objective, Assessment, Plan) note generated
    from a completed transcription job, possibly by an AI model.
    """
    FORMAT_CHOICES = (("text", "Text"), ("json", "JSON"))

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transcription_job = models.OneToOneField(
        TranscriptionJob,
        on_delete=models.CASCADE,
        related_name="soap_note"
    )
    generated_at = models.DateTimeField(auto_now_add=True)
    format = models.CharField(max_length=8, choices=FORMAT_CHOICES, default="json")
    content = models.JSONField(null=True, blank=True)  # if format=json
    content_text = models.TextField(null=True, blank=True)  # if format=text
    vertex_response_meta = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["-generated_at"]

    def __str__(self):
        return f"SOAPNote ({self.transcription_job.aws_job_name})"
