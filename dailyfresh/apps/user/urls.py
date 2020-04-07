
from django.conf.urls import url
from django.urls import path
from apps.user import views
from django.contrib.auth.decorators import login_required
from apps.user.views import RegisterView,ActionView,LoginView,LogoutView,UserInfoView,UserOrderView,AddressView
#namespace为了反向找路径
app_name = 'user'
urlpatterns = [
    # path(r'^register$',views.register,name='register'),#注册
    # path(r'register_handle$',views.register_handle,name='register_handle'),#注册处理
    url(r'^register$',RegisterView.as_view(),name='register'),#注册
    url(r'^active/(?P<token>.*)$',ActionView.as_view(),name='action') ,#用户激活
    url(r'^login$',LoginView.as_view(),name='login'),#登陆页面
    url(r'^$',UserInfoView.as_view(),name='user'),#用户中心-信息页服务
    url(r'^order/(?P<page>\d+)$',UserOrderView.as_view(),name='order'),#用户中心-订单页
    url(r'^address$',AddressView.as_view(),name='address'),#用户中心-地址页
    url(r'^logout$',LogoutView.as_view(),name='logout'),#用户退出


]
