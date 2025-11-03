import boto3
import time
import json
import os
from django.conf import settings

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_TRANSCRIBE_ROLE_ARN = os.getenv("AWS_TRANSCRIBE_ROLE_ARN")

transcribe_client = boto3.client("transcribe", region_name=AWS_REGION)


def start_medical_transcription_job(job_name: str, media_url: str) -> str:
    """
    Start AWS Medical Transcribe Job
    """
    response = transcribe_client.start_medical_transcription_job(
        MedicalTranscriptionJobName=job_name,
        LanguageCode="en-US",
        MediaFormat=media_url.split(".")[-1],  # e.g. 'mp3' or 'wav'
        Media={"MediaFileUri": media_url},
        OutputBucketName=settings.AWS_STORAGE_BUCKET_NAME,
        Specialty="PRIMARYCARE",
        Type="CONVERSATION",
        Settings={"ShowSpeakerLabels": True, "MaxSpeakerLabels": 2},
    )
    return response["MedicalTranscriptionJob"]["MedicalTranscriptionJobName"]


def get_transcription_result(job_name: str) -> str:
    """
    Poll AWS Transcribe until job finishes.
    Returns the transcript text.
    """
    while True:
        job = transcribe_client.get_medical_transcription_job(
            MedicalTranscriptionJobName=job_name
        )["MedicalTranscriptionJob"]

        status = job["TranscriptionJobStatus"]

        if status in ["FAILED"]:
            raise Exception(f"Transcription failed: {job.get('FailureReason')}")

        if status == "COMPLETED":
            transcript_uri = job["Transcript"]["TranscriptFileUri"]
            # Download transcript JSON from S3
            import requests
            response = requests.get(transcript_uri)
            data = response.json()
            return data["results"]["transcripts"][0]["transcript"]

        time.sleep(10)  # Wait before polling again
