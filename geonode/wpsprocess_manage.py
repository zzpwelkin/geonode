#!/usr/bin/env python
#-*- coding:utf-8 -*-

"""
the cmd file for administrator to manage process, as update profile
"""


import os, sys

sys.path.append(os.path.dirname(__file__))

def usage():
    using = r"""
    admin_manage admin profile
    
    admin: the administrator's name
    profile: the profile file
    """
    return using

def update_profile(admin, profile):
    """
    Note:
    
    @param  admin: the administrator's name
    @param  profile: the profile file
    
    @return: if success then processes list being added will
    """
    from geonode.wpsprocess.models import WPSService

    try:
        WPSService.objects.get(username=admin).update_profile(profile)
    except WPSService.DoesNotExist:
        print ("The user {0} is not exit".format(admin))
        return

if __name__ == "__main__":
    # set the django env
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "geonode.settings")
    
    if (len(sys.argv) != 3):
        print(usage())
    else:
         ps = update_profile(sys.argv[1], sys.argv[2])
         
         print("The processes added by this file is : {0}".format(str(ps)))
    
