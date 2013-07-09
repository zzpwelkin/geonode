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

import autocomplete_light
from django import forms
from django.forms import formsets
from django.forms.util import ErrorList
from django.forms.models import modelformset_factory

from geonode.wpsprocess.models import Process
from pywps.models import *

logger = logging.getLogger('geonode.wpsprocess.forms')

#class ProfileUploadForm(forms.Form):
#    update_form = forms.FileField()
#    
#    def write_file(self):
#        tempdir = tempfile.mkstemp()
#        
#        f = self.cleaned_data["update_form"]
#        if f is not None:
#            path = os.path.join(tempdir, f.name)
#            with open(path, 'w') as writable:
#                for c in f.chunks():
#                    writable.write(c)
#        return path
    
##################### Process form sets##########################
class UniqueConstraintFormSet(formsets.BaseFormSet):
    """
    the formset that add a constraint by ${unique_name} 
    
    @param unique_name: an str that will be unique 
    """
    def __init__(self, unique_name='identifier', prefix='', data = None, files = None):
        super(UniqueConstraintFormSet, self).__init__(prefix=prefix, data = data, files = files)
        self._unique_name = unique_name
    
    def clean(self):
        """
        Checks that the identifier of two inputs or outputs not the same
        """
        if any(self.errors):
            return 
        
        identifiers = []
        
        for i in range(0, self.total_form_count()):
            ident = self.forms[i].cleaned_data.get(self._unique_name,None)
            if not ident:
                continue
            
            if ident in identifiers:
                raise forms.ValidationError('disticting identifier should be have in a set inputs or outputs ')
            
            identifiers.append(ident)
        
        self.cleaned_data
        
# Metadata Formset 
MetaFormSet = modelformset_factory(Meta, formset=UniqueConstraintFormSet, extra=0, can_delete=True, max_num=1)

class BaseProcessBaseForm(forms.ModelForm):
    Metadata = MetaFormSet(prefix='', unique_name='title')
    class Meta:
        model = Meta
    
    def clean(self):
        return forms.ModelForm.clean(self)
#        data = forms.ModelForm.clean(self)
#        
#        self.Metadata = MetaFormSet(self.data, self.files)
#        if self.Metadata.is_valid():
#            data['Metadata'] = self.Metadata.cleaned_data
#            return data
#        else:
#            raise forms.ValidationError(self.Metadata.errors)
        
class LiteralDataInputForm(BaseProcessBaseForm):
    class Meta:
        model = LiteralDataInput
        
    def clean(self):
        a = 1
        return BaseProcessBaseForm.clean(self)
#        """
#        number1 and number2 check
#        """
#        if all((self.cleaned_data['number1'], self.cleaned_data['number2'],)):
#            raise forms.ValidationError(" the number1 and number2 cann't be exit at the same time ")
#        
#        if not any((self.cleaned_data['number1'], self.cleaned_data['number2'],)):
#            raise forms.ValidationError(" the number1 and number2 cann't be null at the same time")

class LiteralDataOutputForm(BaseProcessBaseForm):
    class Meta:
        model = LiteralDataOutput
        
class ComplexDataInputForm(BaseProcessBaseForm):
    class Meta:
        model = ComplexData
        
class ComplexDataOutputForm(BaseProcessBaseForm):
    class Meta:
        model = ComplexData
        exclude = ('maximumMegabytes','minOccurs','maxOccurs',)
    
LiteralDataInputFormSet = formsets.formset_factory(form=LiteralDataInputForm, formset=UniqueConstraintFormSet, extra=0, can_delete=True, max_num=1)
ComplexDataInputFormSet = formsets.formset_factory(form=ComplexDataInputForm, formset=UniqueConstraintFormSet, extra=0, can_delete=True, max_num=1)
LiteralDataOutputFormSet = formsets.formset_factory(form=LiteralDataOutputForm, formset=UniqueConstraintFormSet, extra=0, can_delete=True, max_num=1)
ComplexDataOutputFormSet = formsets.formset_factory(form=ComplexDataOutputForm, formset=UniqueConstraintFormSet, extra=0, can_delete=True, max_num=1)
        
class UpLoadProcessForm(forms.ModelForm):
    manytomany_field = [LiteralDataInputFormSet(prefix='LiteralDataInput', unique_name='identifier'),
                        ComplexDataInputFormSet(prefix='ComplexDataInput', unique_name='identifier'),
                        LiteralDataOutputFormSet(prefix='LiteralDataOutput', unique_name='identifier'),
                        ComplexDataOutputFormSet(prefix='ComplexDataOutput', unique_name='identifier'),]
       
    class Meta:
        model = Process
        widgets = autocomplete_light.get_widgets_dict(Process)
        exclude = ('WSDL', 'Profile', 'wpsservice','LiteralDataInput', 'LiteralDataOutput', 'ComplexDataInput',
                   'ComplexDataOutput','BoundingBoxDataInput', 'BoundingBoxDataOutput', )
        
    def clean(self):
        data = forms.ModelForm.clean(self)
        
        for i in range(0,len(self.manytomany_field)):
            formset_class = type(self.manytomany_field[i])
            self.manytomany_field[i] = formset_class(data = self.data, files = self.files, prefix=self.manytomany_field[i].prefix, unique_name='identifier')
            
            if self.manytomany_field[i].is_valid():
                data[self.manytomany_field[i].prefix] = self.manytomany_field[i].cleaned_data
            else:
                raise forms.ValidationError(self.manytomany_field[i].errors)
            
        return data
        
##################### Process form sets END##########################

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
                if input.defaultValue.mimeType.lower() == 'image/tiff':
                    kwargs['choices'] = coverages
                elif input.defaultValue.mimeType.lower() == 'esri/shapefile':
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
                        