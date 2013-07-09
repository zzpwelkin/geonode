from django.conf.urls.defaults import patterns, url
from geonode.wpsprocess.views import *

# wps url is the OGC WPS standard request and response
urlpatterns = patterns('geonode.wpsprocess.views',
    url(r'^(?P<provider>[_\w]+?)/wps/$', WpsStandardServiceApi.as_view(), name='wps_global_dispatch' ),
    url(r'^api/(?P<slug>[_\w]+?)/search/?$', 'search_process', name= 'search_process'), 
    
    url(r'^$', ProcessListView.as_view(template_name='process_list.html', context_object_name='process_list', paginate_by=5), name='process_browse'),
    url(r'^category/(?P<slug>[_\w]+?)/$', ProcessListView.as_view(template_name='process_list.html', context_object_name='process_list', paginate_by=5), name='process_list'),
    url(r'^execute/(?P<provider>[_\w]+?)/(?P<identifier>[_\w]+?)/$', ProcessExecuteView.as_view(template_name='process_execute.html'), name='process_execute'), 
    url(r'^upload/$', UploadProccessView.as_view(template_name='upload_process.html'), name='upload_process'),                   
)
