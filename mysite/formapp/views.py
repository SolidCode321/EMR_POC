from django.shortcuts import render
from django.shortcuts import redirect
from django.http import JsonResponse
from django.conf import settings
from .models import AudioFile, MedicalForm
import time
import os, json

from google import genai

from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_POST

API_KEY = 'AIzaSyCBQzOAwHwxdttt_JXm5WWPJecnArCX2wM'

def index(request):
    forms = MedicalForm.objects.all()
    return render(request, 'index.html', {'forms': forms})


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
    

@csrf_protect
def upload_form_page(request):
    forms = MedicalForm.objects.all()
    return render(request, 'upload_form.html', {'forms': forms})

@require_POST
@csrf_protect
def submit_form(request):
    title = request.POST.get('title')
    pdf = request.FILES.get('pdf')

    if title and pdf:
        MedicalForm.objects.create(title=title, pdf=pdf)
        return redirect('index')  # Redirect to home or success page
    else:
        return render(request, 'upload_form.html', {
            'error': 'Both title and PDF are required.'
        })

@csrf_exempt
def delete_form(request):
    if request.method == 'POST':
        form_id = request.POST.get('form_id')
        try:
            form = MedicalForm.objects.get(id=form_id)
            form.delete()
            return redirect('upload_form_page')  # Adjust based on your URL name
        except MedicalForm.DoesNotExist:
            return render(request, 'upload.html', {
                'error': 'Form not found.',
                'forms': MedicalForm.objects.all()
            })

    return redirect('upload_form_page')