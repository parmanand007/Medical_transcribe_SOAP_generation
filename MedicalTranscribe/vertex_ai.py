import os
import vertexai
from vertexai.generative_models import GenerativeModel

PROJECT_ID = os.getenv("VERTEX_PROJECT_ID")
LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")

vertexai.init(project=PROJECT_ID, location=LOCATION)


def generate_soap_from_transcript(transcript: str) -> dict:
    """
    Use Vertex AI Gemini model to convert transcript text → SOAP note.
    """
    model = GenerativeModel("gemini-1.5-pro")

    prompt = f"""
    You are a clinical documentation assistant.
    Convert the following medical conversation transcript into a structured SOAP note.
    Format output as JSON with these fields:
    {{
      "Subjective": "...",
      "Objective": "...",
      "Assessment": "...",
      "Plan": "..."
    }}
    Transcript:
    {transcript}
    """

    response = model.generate_content(prompt)
    text_output = response.text.strip()

    try:
        # Attempt to parse structured JSON
        import json
        return json.loads(text_output)
    except Exception:
        # fallback - return as raw string
        return {"raw_output": text_output}
