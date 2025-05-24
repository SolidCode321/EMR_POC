from django.shortcuts import render
from django.shortcuts import redirect
from django.http import JsonResponse
from django.conf import settings
from .models import AudioFile, MedicalForm
import time
import os, json, re

from google import genai
from fillpdf import fillpdfs
from pdfrw import PdfReader

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

            # Delete the actual PDF file from the filesystem
            if form.pdf and os.path.exists(form.pdf.path):
                os.remove(form.pdf.path)

            # Delete the form entry from the database
            form.delete()
            return redirect('upload_form_page')

        except MedicalForm.DoesNotExist:
            return render(request, 'upload.html', {
                'error': 'Form not found.',
                'forms': MedicalForm.objects.all()
            })

    return redirect('upload_form_page')

def get_radio_button_options(pdf_path):
    pdf = PdfReader(pdf_path)
    radio_options = {}

    for page in pdf.pages:
        annotations = page.Annots
        if annotations:
            for annot in annotations:
                field = annot.get('/T')
                field_type = annot.get('/FT')
                if field_type == '/Btn':  # Button field (radio/checkbox)
                    ap = annot.get('/AP')
                    if ap and '/N' in ap:
                        options = list(ap['/N'].keys())
                        radio_options[str(field)] = [str(opt)[1:] if str(opt).startswith("/") else str(opt) for opt in options]

    return radio_options

@csrf_exempt
def fill_form(request):
    try:
        data = json.loads(request.body)
        transcript = data.get('transcript', '')
        pdf_url = data.get('pdf_url', '')

        if not pdf_url or not transcript:
            return JsonResponse({'success': False, 'error': 'Missing transcript or PDF URL'})

        file_path = os.path.join(settings.MEDIA_ROOT+'forms/', pdf_url)

        form_fields = fillpdfs.get_form_fields(file_path)
        radio_options = get_radio_button_options(file_path)

        field_descriptions = []
        for field, value in form_fields.items():
            if field in radio_options:
                opts = ', '.join(radio_options[field])
                field_descriptions.append(f"'{field}' is a radio button with options: {opts}.")
            else:
                field_descriptions.append(f"'{field}' is a text field.")

        fields_prompt = "\n".join(field_descriptions)

        prompt = f"""
        Given the following transcript:
        """
        {transcript}
        """

        And the PDF form fields:
        {fields_prompt}

        Fill the fields based on the transcript. Return a JSON object with field names as keys and the selected or filled values as values.
        """

        # Initialize Gemini client
        client = genai.Client(api_key=API_KEY)

        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=[prompt],
        )

        try:
            filled_data = json.loads(response.text)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Gemini returned an invalid JSON response'})

        # Create output path for the filled PDF
        filled_pdf_filename = f"filled_{os.path.basename(pdf_url)}"
        filled_pdf_path = os.path.join(settings.MEDIA_ROOT, filled_pdf_filename)

        fillpdfs.write_fillable_pdf(file_path, filled_pdf_path, filled_data)

        return JsonResponse({'success': True, 'filled_pdf_url': settings.MEDIA_URL + filled_pdf_filename})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
