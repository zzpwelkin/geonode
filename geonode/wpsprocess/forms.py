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

import logging,tempfile

from django import forms

logger = logging.getLogger('geonode.wpsprocess.forms')

class ProfileUploadForm(forms.Form):
    update_form = forms.FileField()
    
    def write_file(self):
        tempdir = tempfile.mkstemp()
        
        f = self.cleaned_data["update_form"]
        if f is not None:
            path = os.path.join(tempdir, f.name)
            with open(path, 'w') as writable:
                for c in f.chunks():
                    writable.write(c)
        return path

class ExecuteForm(forms.Form):
    """
    the form that a stylesheet will be automate created for setting inputs for a
    process to execute
    """
    def __init__(self, inputs = None, features = None, coverages = None, **kwargs):
        """
        @param inputs: inputs of process
        @param features: An iterable (e.g., a list or tuple) of 2-tuples that contain recorded feature data
        @param coverages: An iterable (e.g., a list or tuple) of 2-tuples that contain recorded coverage data
        """
        assert inputs 
        super(ExecuteForm, self).__init__(**kwargs)
        
        # create a field for every input 
        for __, input in inputs.items():            
            kwargs = {'label':input.identifier, 'help_text':'.'.join((input.__dict__.get('title',''),
                                                                    input.__dict__.get('abstract','')))}
            if input.minOccurs == 0:
                kwargs['require'] = False
            if input.defaultValue and input.dataType != 'ComplexData':
                kwargs['initial'] = input.defaultValue
             
            if input.dataType == 'ComplexData':
                if input.defaultValue.mimeType == 'image/tiff':
                    kwargs['choices'] = coverages
                elif input.defaultValue.mimeType == 'esri/shapefile':
                    kwargs['choices'] = features
                    
                if len(kwargs.get('choices',[])) > 0:
                    kwargs['initial'] = kwargs['choices'][0]
                self.fields[input.identifier] = forms.ChoiceField(**kwargs)
                continue
            
            if input.dataType.rsplit('#')[1] == 'boolean':
                kwargs['require'] = False
                self.fields[input.identifier] = forms.BooleanField(kwargs)
                continue
            
            if input.allowedValues[0] != 'AnyValue':
                kwargs['choices'] = input.allowedValues
                self.fields[input.identifier] = forms.ChoiceField(**kwargs)
                continue
            
            literal_type = input.dataType.rsplit('#')[1]
            if literal_type == 'string':
                self.fields[input.identifier] = forms.CharField(**kwargs)
            elif literal_type == 'integer':
                self.fields[input.identifier] = forms.IntegerField(**kwargs)
            elif literal_type == 'float':
                self.fields[input.identifier] = forms.FloatField(**kwargs)
            else:
                # TODO: add the bbox input
                pass
                        