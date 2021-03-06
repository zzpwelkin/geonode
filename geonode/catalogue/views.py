# -*- coding: utf-8 -*-
#########################################################################
#
# Copyright (C) 2012 OpenPlans
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
#########################################################################

import os
from ConfigParser import SafeConfigParser
from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from pycsw import server
from django.contrib.auth.decorators import login_required
from geonode.catalogue.backends.pycsw_local import CONFIGURATION


@csrf_exempt
@login_required
def csw_global_dispatch(request):
    """pycsw wrapper"""

    # this view should only operate if pycsw_local is the backend
    # else, redirect to the URL of the non-pycsw_local backend
    if (settings.CATALOGUE['default']['ENGINE'] !=
        'geonode.catalogue.backends.pycsw_local'):
        return HttpResponseRedirect(settings.CATALOGUE['default']['URL'])

    # serialize pycsw settings into SafeConfigParser
    # object for interaction with pycsw
    # TODO: pass just dict when pycsw supports it
    mdict = dict(settings.PYCSW['CONFIGURATION'], **CONFIGURATION)
    config = SafeConfigParser()

    for section, options in mdict.iteritems():
        config.add_section(section)
        for option, value in options.iteritems():
            config.set(section, option, value)

    env = request.META.copy()
    env.update({
            'local.app_root': os.path.dirname(__file__),
            'REQUEST_URI': request.build_absolute_uri(),
            })

    csw = server.Csw(config, env)

    content = csw.dispatch_wsgi()

    return HttpResponse(content, content_type=csw.contenttype)
