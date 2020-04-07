# -*- coding: utf-8 -*-
'''
@Time    : 2019/12/10 23:54
@Author  : jiangzhiqin 
'''
# # 在任务一段加这几句代码初始化配置
import os
import django
# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dailyfresh.settings')
# django.setup()
#使用celery
from celery import Celery
from django.core.mail import send_mail
from django.conf import settings
from django.core.cache import cache
from apps.goods.models import GoodsType,IndexGoodsBanner,IndexPromotionBanner,IndexTypeGoodsBanner
from django.template import loader,RequestContext
import os
import time
import redis

#创建一个Celery的实例对象
broker='redis://122.51.181.167:6379/8'
backend = 'redis://122.51.181.167:6379/8'
app = Celery("celery_tasks.tasks",broker=broker)
#定义发送邮件任务函数
@app.task
def send_register_active_email(to_email,username,token):
    """发送激活邮件"""
    # 发送邮件
    subject = '天天生鲜欢迎信息'
    message = ''
    sender = settings.EMAIL_FROM
    receiver = [to_email]
    html_message = '<h1>{0}, 欢迎您成为天天生鲜注册会员</h1>请点击下面链接激活您的账户<br/><a href="http://127.0.0.1:8000/user/active/{1}">http://127.0.0.1/user/active/{2}</a>'.format(
        username, token, token)
    send_mail(subject, message, sender, receiver, html_message=html_message)
    #time.sleep(5)

@app.task
def generate_static_index_html():
    '''产生首页静态页面'''
    # 获取商品种类信息
    types = GoodsType.objects.all()

    # 获取首页轮播商品信息
    goods_banners = IndexGoodsBanner.objects.all().order_by('index')

    # 获取首页促销商品信息
    promotion_banners = IndexPromotionBanner.objects.all().order_by('index')

    # 获取分类商品展示信息
    for type in types:
        image_goods_banners = IndexTypeGoodsBanner.objects.filter(type=type, display_type=1)
        font_goods_banners = IndexTypeGoodsBanner.objects.filter(type=type, display_type=0)
        type.image_goods_banners = image_goods_banners
        type.font_goods_banners = font_goods_banners

    # 组织上下文
    context = {
        'types': types,
        'goods_banners': goods_banners,
        'promotion_banners': promotion_banners,
    }

    #使用模板
    #1.加载模板文件
    temp = loader.get_template('static_index.html')
    #2.定义模板上下文
    #RequestContext(request,context)
    #3.模板渲染
    static_index_html = temp.render(context)
    #生成首页对应静态文件
    save_path = os.path.join(settings.BASE_DIR,'static/index.html')
    with open(save_path,'w',encoding='utf-8') as f:
        f.write(static_index_html)



