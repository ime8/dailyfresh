
from django.conf.urls import url
from django.urls import path,re_path
from apps.goods import views
#namespace为了反向找路径
from apps.goods.views import IndexView,DetailView,ListView
app_name = 'goods'
urlpatterns = [
    path('index', IndexView.as_view(), name='index'),#首页
    re_path('^goods/(?P<goods_id>\d+)$', DetailView.as_view(), name='detail'),#商品详情页
    re_path('^list/(?P<type_id>\d+)/(?P<page>\d+)$',ListView.as_view(),name='list'),#商品列表

]
