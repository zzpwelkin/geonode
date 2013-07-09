import os
from contextlib import closing
from owslib import wps

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import User
from django.http import HttpRequest
from django.db.models.signals import post_save, pre_delete
from django.core.urlresolvers import reverse

import pywps
from geonode.wpsprocess.repertory import RepertoryManager, Repertory

# Create your models here.

class WPSService(User):
    """
    @param serviceurl:
    @param repertorydir: 
    @param configfile:
    """    
    serviceurl = models.URLField()
    repertorydir = models.CharField(max_length=200)
    configfile = models.CharField(max_length=50)
    #user = models.OneToOneField(User, related_name = 'wpsservice')
    
    def __unicode__(self):
        return u"user:{0} \n email:".format(self.username, self.email)
    
class Process(pywps.models.Process):
    wpsservice = models.ForeignKey(WPSService)
    
#    class Meta:
#        unique_together = ("wpsservice", "identifier", "processVersion", )
    
    def setInputorOuputValue(self, attrname, value):
        """
        add list or single value to inputs or outputs field of this process
        """
        many_to_many_fields_name = [m2m.name for m2m in self._meta.many_to_many]
        if attrname in many_to_many_fields_name:
            att = self.__getattribute__(attrname)
            if isinstance(value, (type([]), type(()))):
                att.add(*value)
            else:
                att.add(value)
    
def wpsservice_create_of_user(instance, sender, **kwargs):
    wpsservice = WPSService(user_ptr=instance)
    wpsservice.__dict__.update(instance.__dict__)
    #wpsservice.update(repertorydir = os.path.join(settings.WPS['repertory'], instance.username),
    #                  configfile = 'wps.cfg')
    wpsservice.serviceurl = reverse('wps_global_dispatch', args=( instance.username,))
    wpsservice.repertorydir = os.path.join(settings.WPS['repertory'], instance.username)
    wpsservice.configfile = 'wps.cfg'
    wpsservice.save()
    
    # set the wps repertory for that user
    RepertoryManager().create(wpsservice)
    
    #post_save.connect(receiver=wpsservice_create_of_user, sender=User)
        
def wpsservice_delete_of_user(instance, sender, **kwargs):
        wpsservice = WPSService.objects.get(user_ptr=instance)
        
        # delete all the process from table
        for p in wpsservice.process_set.all():
            p.delete()
        
        # delete the repertory of this service
        RepertoryManager().delete(wpsservice)
        
        # delete the service
        wpsservice.delete()
        
        #post_delete.connect(receiver=wpsservice_create_of_user, sender=User)
        
def process_created(instance, sender, **kwargs):
    pass
    
if 'geonode.wpsprocess' in settings.INSTALLED_APPS:
    post_save.connect(receiver=wpsservice_create_of_user, sender=User)
    pre_delete.connect(receiver=wpsservice_delete_of_user, sender=User)
    