# Django AWS Medical Transcription Backend

This repository provides a production-grade **Django REST Framework** backend integrated with **Amazon Transcribe Medical** for automatic audio transcription and SOAP note generation.  
Audio files are stored on **Amazon S3**, and transcription status can be tracked via REST APIs.

---

## Overview

### Features
- Upload audio files to **Amazon S3**
- Automatically trigger **Amazon Transcribe Medical** jobs
- Retrieve transcription job details and SOAP notes
- Paginated API to list uploaded audio files
- Secure access with **DRF authentication**
- Example IAM policy for full S3 and Transcribe access

---

## Tech Stack

| Component      | Technology |
|----------------|-------------|
| Framework      | Django 5 + Django REST Framework |
| Database       | PostgreSQL |
| File Storage   | Amazon S3 |
| Transcription  | Amazon Transcribe Medical |

---

## Project Structure

