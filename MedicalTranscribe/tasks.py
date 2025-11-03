import boto3
from celery import shared_task
from django.conf import settings

from .models import AudioFile, TranscriptionJob, SOAPNote


@shared_task
def start_transcription_task(audio_id):
    """
    Celery task to trigger an AWS Transcribe Medical job for an uploaded AudioFile.
    """
    audio = AudioFile.objects.get(id=audio_id)

    # Create AWS Transcribe client
    transcribe_client = boto3.client("transcribe", region_name=settings.AWS_S3_REGION_NAME)

    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    file_key = audio.file.name
    s3_uri = f"s3://{bucket_name}/{file_key}"
    job_name = f"medical_transcription_{audio.id.hex}"
    # Save job info in DB
    TranscriptionJob.objects.create(
        audio=audio,
        aws_job_name=job_name,
        status="in_progress",
    )

    try:
        # Start the Transcribe Medical job
        response = transcribe_client.start_medical_transcription_job(
            MedicalTranscriptionJobName=job_name,
            LanguageCode="en-US",  # Required
            MediaSampleRateHertz=16000,  # Use correct sample rate if known
            MediaFormat=_infer_media_format(audio.original_filename),
            Media={"MediaFileUri": s3_uri},
            OutputBucketName=bucket_name,
            Specialty="PRIMARYCARE",      # Required for medical jobs
            Type="CONVERSATION",          # Conversation between doctor and patient
            ContentIdentificationType="PHI", # Redacts personal health info
            Settings={
                "ShowSpeakerLabels": True,
                "MaxSpeakerLabels": 2,
            },
        )

        # Update audio status
        audio.status = "transcription_started"
        audio.save(update_fields=["status"])

        return response

    except Exception as e:
        audio.status = "failed"
        audio.save(update_fields=["status"])
        raise e


def _infer_media_format(filename: str) -> str:
    ext = filename.split(".")[-1].lower()
    return ext if ext in ["mp3", "wav", "flac", "mp4", "ogg", "m4a", "amr", "webm"] else "mp3"


def generate_soap_note(job_id):
    """
    Simulated SOAP note generation from transcript text.
    Replace with AI model like OpenAI, Claude, or Vertex later.
    """
    job = TranscriptionJob.objects.get(id=job_id)
    transcript_text = job.transcript_text or ""

    note = {
        "Subjective": transcript_text[:100],
        "Objective": "Data extracted from audio",
        "Assessment": "Patient condition described",
        "Plan": "Follow-up in 2 weeks",
    }

    SOAPNote.objects.create(
        transcription_job=job,
        format="json",
        content=note,
    )
