from django.shortcuts import render
from django.shortcuts import redirect
from django.http import JsonResponse
from django.conf import settings
from .models import AudioFile, MedicalForm
import time
import os, json, re
from django.core.files import File

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

        media_relative_path = pdf_url.replace('/media/', '')  # removes the URL prefix
        file_path = os.path.join(settings.MEDIA_ROOT, media_relative_path)

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
        You are given a transcript of a conversation or medical consultation:

        Transcript:
        {transcript}

        And the following list of PDF form fields. Some fields are text input, while others are radio buttons with defined selectable options:

        Form Fields:
        {fields_prompt}

        Please do the following:
        1. Extract relevant information from the transcript to fill in each field.
        2. For radio buttons, select the most appropriate option based on the transcript. If only one option is available, assume it should be selected if relevant.
        3. Return the result as a JSON object where:
            - Each key is the form field name.
            - Each value is the selected or filled value for that field (for radio buttons, the option text or value).

        Output Format (example):
        {{
            "field_name_1": "filled value",
            "field_name_2": "selected radio option"
        }}

        Only return a valid JSON object. Do not include any explanation or extra text. and dont return as ```json```.
        
        """
        
        # print(transcript)
        # print(fields_prompt)
        
        # Initialize Gemini client
        client = genai.Client(api_key=API_KEY)

        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=[prompt],
        )
        raw_response = response.text.strip()

        # Remove code fences if present
        if raw_response.startswith("```json"):
            raw_response = raw_response[len("```json"):].strip()
        if raw_response.endswith("```"):
            raw_response = raw_response[:-3].strip()


        try:
            print("Raw Gemini Response:")
            print(raw_response)
            filled_data = json.loads(raw_response)
            print(filled_data)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Gemini returned an invalid JSON response'})

        # Overwrite the same file with filled data
        fillpdfs.write_fillable_pdf(file_path, file_path, filled_data)
        
        form_entry = MedicalForm.objects.filter(pdf=media_relative_path).first()
        if form_entry:
            form_entry.save()

        return JsonResponse({'success': True, 'filled_pdf_url': settings.MEDIA_URL + file_path})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
