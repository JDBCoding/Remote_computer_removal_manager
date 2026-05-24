from django.urls import path
from . import views


urlpatterns = [
    path('', views.home, name='home'),
    path("how-to-use/", views.how_to_use, name="how_to_use"),
    path('add/', views.add_part, name='add_part'),
    path('edit/<str:pk>/', views.edit_part, name='edit_part'),
    path("edit/<str:pk>/add-location/", views.add_install_location, name="add_install_location"),
    path('requirement/<int:pk>/edit/', views.requirement_edit, name='requirement_edit'),
    path('requirement/<str:part_number>/edit/', views.edit_requirements, name='edit_requirements'),
    path('requirement/<str:pk>/add/', views.add_requirement, name='add_requirement'),
    path('planning/create/', views.planning_request_create, name='planning_request_create'),
   
    
]

