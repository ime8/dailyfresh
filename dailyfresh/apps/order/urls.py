
from django.conf.urls import url
from apps.order.views import OrderPlaceView,OrderCommitView,OrderPayView,CheckPayView,CommentView
#namespace为了反向找路径
urlpatterns = [
    url(r'^place$',OrderPlaceView.as_view(),name='place'),#提交结算订单页面
    url(r'^commit$',OrderCommitView.as_view(),name='commit'),#创建订单
    url(r'^pay$',OrderPayView.as_view(),name='pay'),#订单支付
    url(r'^check$',CheckPayView.as_view(),name='check'),#查询订单交易结果
    url(r'^comment/(?P<order_id>.+)$',CommentView.as_view(),name='comment'),#订单评论

]
