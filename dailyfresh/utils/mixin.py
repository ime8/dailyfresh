# -*- coding: utf-8 -*-
'''
@Time    : 2019/12/19 21:46
@Author  : jiangzhiqin 
'''
from django.contrib.auth.decorators import login_required
class LoginRequiredMixin(object):
    @classmethod
    def as_view(cls,**initkwargs):
        #调用父类的as_view
        view = super(LoginRequiredMixin,cls).as_view(**initkwargs)
        return login_required(view)
