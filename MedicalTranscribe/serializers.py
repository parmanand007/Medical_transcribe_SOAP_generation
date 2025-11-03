from rest_framework import serializers
from .models import AudioFile

class AudioUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    # optional metadata fields
    sample_rate = serializers.IntegerField(required=False)
    channels = serializers.IntegerField(required=False)


class AudioFileSerializer(serializers.ModelSerializer):
    s3_uri = serializers.SerializerMethodField()

    class Meta:
        model = AudioFile
        fields = ["id", "original_filename", "status", "uploaded_at", "s3_uri"]

    def get_s3_uri(self, obj):
        # Return direct S3 URI or fallback to file.url
        try:
            return obj.file.url
        except Exception:
            return None