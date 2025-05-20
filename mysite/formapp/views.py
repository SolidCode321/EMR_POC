from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings
from .models import AudioFile
import time
import os, json

from google import genai

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

API_KEY = 'AIzaSyCBQzOAwHwxdttt_JXm5WWPJecnArCX2wM'

def index(request):
    return render(request, 'index.html')


@csrf_exempt
def upload_audio(request):
    if request.method == 'POST':
        audio_file = request.FILES['audio']
        timestamp = int(time.time())
        original_filename = audio_file.name
        extension = os.path.splitext(original_filename)[1] or '.wav'
        new_filename = f"{timestamp}{extension}"
        audio_file.name = new_filename

        # Save the file
        instance = AudioFile.objects.create(file=audio_file)

        return JsonResponse({
            'status': 'success',
            'filename': instance.file.name  # includes relative path like 'audio/123456.wav'
        })

    return JsonResponse({'status': 'failed'}, status=400)


@require_POST
@csrf_exempt  # Optional: if CSRF issues persist
def transcribe_audio(request):
    data = json.loads(request.body)
    filename = data.get('filename')
    file_path = os.path.join(settings.MEDIA_ROOT, filename)

    # Initialize Gemini client
    client = genai.Client(api_key=API_KEY)

    try:
        # Upload file to Gemini
        myfile = client.files.upload(file=file_path)

        # Gemini prompt
        prompt = 'Transcribe the audio file'

        # Generate transcription
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=[prompt, myfile],
        )

        return JsonResponse({'transcription': response.text})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)