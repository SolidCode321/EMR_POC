from django.urls import path

from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("", views.index, name="index"),
    path('upload/', views.upload_audio, name='upload_audio'),
    path('transcribe/', views.transcribe_audio, name='transcribe_audio'),
    path('upload-form/', views.upload_form_page, name='upload_form_page'),
    path('submit-form/', views.submit_form, name='submit_form'),
    path('delete-form/', views.delete_form, name='delete_form'),
]  + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

