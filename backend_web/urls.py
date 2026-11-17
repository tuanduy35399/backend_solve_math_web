from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from learning import views
router=DefaultRouter()
router.register('materials',views.MaterialViewSet,basename='materials')
router.register('sessions',views.SessionViewSet,basename='sessions')
router.register('training',views.TrainingViewSet,basename='training')
urlpatterns=[path('admin/',admin.site.urls),path('api/v1/',include(router.urls))]
urlpatterns += [path('api/v1/'+url,fn) for url,fn in [
    ('health/',views.health),('auth/register/',views.register),('auth/login/',views.login),('auth/logout/',views.logout),
    ('auth/me/',views.me),('users/',views.users),('edges/',views.edges),('quizzes/',views.quizzes),('gaps/',views.gaps),('attempts/',views.attempts),
    ('statistics/',views.statistics),('assignments/',views.assignments),('learning-reports/',views.learning_reports),('stories/',views.stories),('reports/',views.reports),
    ('learning-data/',views.clear_learning),('configuration/',views.configuration),
]]
urlpatterns += [path('api/v1/assignments/<uuid:pk>/',views.assignment_detail),path('api/v1/assignments/<uuid:pk>/publish/',views.publish_assignment),path('api/v1/assignments/<uuid:pk>/results/',views.assignment_results),path('api/v1/quizzes/<uuid:pk>/',views.quiz_detail),path('api/v1/quizzes/<uuid:pk>/submit/',views.submit_quiz)]
