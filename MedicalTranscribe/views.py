import boto3
import json
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .models import AudioFile
from urllib.parse import urlparse
from .tasks import start_transcription_task
from rest_framework import generics, filters
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from .serializers import AudioFileSerializer


class AudioUploadView(APIView):
    """
    1. Upload audio file (handled by Django Storage → S3)
    2. Create AudioFile entry in DB
    3. Trigger background Celery task for AWS Transcribe
    """

    def post(self, request):
        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response(
                {"error": "No file uploaded."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Optional: validate allowed audio types
        allowed_types = {"audio/mpeg", "audio/wav", "audio/mp3", "audio/x-m4a"}
        if file_obj.content_type not in allowed_types:
            return Response(
                {"error": f"Unsupported file type: {file_obj.content_type}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Save file directly using Django FileField (S3 backed)
            audio = AudioFile.objects.create(
                original_filename=file_obj.name,
                file=file_obj,
                status="uploaded",
                metadata={
                    "size": file_obj.size,
                    "content_type": file_obj.content_type,
                },
            )

            # Trigger background AWS Transcribe job
            start_transcription_task(str(audio.id))
            return Response(
                {
                    "id": str(audio.id),
                    "file_name": audio.original_filename,
                    "file_url": audio.file_url,
                    "s3_uri": audio.file.url,
                    "status": audio.status,
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            return Response(
                {"error": f"Failed to upload audio file: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class AudioFilePagination(PageNumberPagination):
    """
    Custom pagination for AudioFile list.
    Defaults: 10 per page, supports ?page=2&size=20
    """
    page_size = 10
    page_size_query_param = "size"
    max_page_size = 100


class AudioListView(generics.ListAPIView):
    """
    Paginated + filterable list of uploaded audio files.
    Supports filtering by 'id' (UUID).
    """
    serializer_class = AudioFileSerializer
    pagination_class = AudioFilePagination
    queryset = AudioFile.objects.all().order_by("-uploaded_at")
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["id"]  # allow ?id=<uuid>
    ordering_fields = ["uploaded_at", "status", "original_filename"]

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        # Paginate
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class TranscriptionStatusView(APIView):
    """
    Fetch AWS Transcribe Medical job status and update DB if completed.
    """

    def get(self, request, audio_id):
        audio = get_object_or_404(AudioFile, id=audio_id)
        job = audio.transcription_jobs.order_by("-started_at").first()
        if not job:
            return Response({"detail": "No transcription job found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            # Initialize AWS Transcribe client
            transcribe_client = boto3.client(
                "transcribe",
                region_name=settings.AWS_S3_REGION_NAME,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            )

            # Fetch job details from AWS
            job_details = transcribe_client.get_medical_transcription_job(
                MedicalTranscriptionJobName=job.aws_job_name
            )
            job_info = job_details["MedicalTranscriptionJob"]
            job_status = job_info["TranscriptionJobStatus"]

            # If COMPLETED → Fetch transcript JSON from S3
            if job_status == "COMPLETED":
                transcript_uri = job_info["Transcript"]["TranscriptFileUri"]
                job.transcript_s3_uri = transcript_uri

                # Initialize S3 client
                s3_client = boto3.client(
                    "s3",
                    region_name=settings.AWS_S3_REGION_NAME,
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                )

                # Handle HTTPS or S3 URI formats
                if transcript_uri.startswith("https://"):
                    # Example:
                    parsed = urlparse(transcript_uri)
                    bucket_name = parsed.path.strip("/").split("/")[0]
                    # If path is `/doctus-transcribe-education/...`, fix it
                    if bucket_name != settings.AWS_STORAGE_BUCKET_NAME:
                        bucket_name = settings.AWS_STORAGE_BUCKET_NAME
                        key = parsed.path.lstrip("/").split("/", 1)[1]
                    else:
                        key = "/".join(parsed.path.lstrip("/").split("/")[1:])
                else:
                    # s3:// URI format
                    s3_uri = transcript_uri.replace("s3://", "")
                    bucket_name, key = s3_uri.split("/", 1)

                # Fetch transcript JSON from S3
                obj = s3_client.get_object(Bucket=bucket_name, Key=key)
                transcript_json = json.loads(obj["Body"].read())

                # Extract plain text transcript
                transcript_text = (
                    transcript_json.get("results", {})
                    .get("transcripts", [{}])[0]
                    .get("transcript", "")
                )

                # Update DB record
                job.status = "completed"
                job.completed_at = job_info.get("CompletionTime")
                job.transcript_text = transcript_text
                job.transcript_full_json = transcript_json
                job.save(
                    update_fields=[
                        "status",
                        "completed_at",
                        "transcript_s3_uri",
                        "transcript_text",
                        "transcript_full_json",
                    ]
                )

            elif job_status == "FAILED":
                job.status = "failed"
                job.error_message = job_info.get("FailureReason", "Unknown failure")
                job.save(update_fields=["status", "error_message"])

            # Prepare response
            return Response(
                {
                    "audio_id": str(audio.id),
                    "audio_filename": audio.original_filename,
                    "transcription_job": {
                        "job_id": str(job.id),
                        "aws_job_name": job.aws_job_name,
                        "status": job.status,
                        "started_at": job.started_at,
                        "completed_at": job.completed_at,
                        "error_message": job.error_message,
                    },
                    "transcript_text": job.transcript_text,
                    "transcript_s3_uri": job.transcript_s3_uri,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": f"Failed to fetch transcription status: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )