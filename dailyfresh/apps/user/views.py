from django.shortcuts import render
from django.shortcuts import redirect,reverse,HttpResponse
from apps.user.models import User,Address
from apps.goods.models import GoodsSKU
from apps.order.models import OrderInfo,OrderGoods
from django.core.paginator import Paginator
from django.views.generic import View
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired
from django.conf import settings
from celery_tasks.tasks import send_register_active_email
from django.contrib.auth import authenticate,login,logout
from django.core.mail import send_mail
from django.contrib.auth.decorators import login_required
from utils.mixin import LoginRequiredMixin
import re
from django_redis import get_redis_connection
import time
# Create your views here.
app_name = 'user'
def register(request):
    '''注册'''
    if request.method == 'GET':
        return render(request,'register.html')
    else:#注册处理
        # 获取请求数据
        username = request.POST.get('user_name')
        print("username:", username)
        password = request.POST.get('pwd')
        pw_sure = request.POST.get('cpwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')
        # 验证数据
        # 1、用户，密码，邮箱都不能为空
        if not all((username, password, email)):
            return render(request, 'register.html', context={
                'errormg': '用户名、密码、邮箱不能为空',
            })
        # 2、密码和确认密码需一致
        if password != pw_sure:
            return render(request, 'register.html', context={
                'errormg': '密码和确认密码不一致',
            })
        # 3、校验邮箱
        if not re.match('^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', context={
                'errormg': '邮箱格式不正确',
            })
        # 4、校验同意协议
        if allow != 'on':
            return render(request, 'register.html', context={
                'errormg': '请同意协议',
            })
        # 5、校验用户名重复不能创建
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:#用户不存在
            user = None

        if user:
            return render(request, 'register.html', context={
                'errormg': '用户名已存在',
            })
        user = User.objects.create_user(username, email, password)
        user.is_active = 0  # 没有激活
        user.save()

        #发送激活邮件，包含激活链接:http://127.0.0.1:8000/user/active/user_id
        #激活链接中需要包含用户的身份信息,并且要把身份信息进行加密


        #返回应答,跳转首页
        return redirect(reverse('goods:index'))

def register_handle(request):
    '''注册处理'''
    #获取请求数据
    username = request.POST.get('user_name')
    print("username:",username)
    password = request.POST.get('pwd')
    pw_sure = request.POST.get('cpwd')
    email = request.POST.get('email')
    allow = request.POST.get('allow')
    #验证数据
    #1、用户，密码，邮箱都不能为空
    if not all((username,password,email)):
        return render(request,'register.html',context={
            'errormg':'用户名、密码、邮箱不能为空',
        })
    #2、密码和确认密码需一致
    if password != pw_sure:
        return render(request,'register.html',context={
            'errormg':'密码和确认密码不一致',
        })
    #3、校验邮箱
    if not re.match('^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$',email):
        return render(request,'register.html',context={
            'errormg':'邮箱格式不正确',
        })
    #4、校验同意协议
    if allow != 'on':
        return render(request,'register.html',context={
            'errormg':'请同意协议',
        })
    #5、校验用户名重复不能创建
    try:
        user = User.objects.get(username=username)
    except User.DoseNotExist:
        user = None

    if user:
        return render(request,'register.html',context={
            'errormg':'用户名已存在',
        })
    user = User.objects.create_user(username,email,password)
    user.is_active=0 #没有激活
    user.save()
    return redirect(reverse('goods:index'))

class RegisterView(View):
    '''注册'''
    def get(self,request):
        '''显示注册页面'''
        return render(request, 'register.html')
    def post(self,request):
        '''注册处理'''
        # 获取请求数据
        username = request.POST.get('user_name')
        print("username:", username)
        password = request.POST.get('pwd')
        pw_sure = request.POST.get('cpwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')
        # 验证数据
        # 1、用户，密码，邮箱都不能为空
        if not all((username, password, email)):
            return render(request, 'register.html', context={
                'errormg': '用户名、密码、邮箱不能为空',
            })
        # 2、密码和确认密码需一致
        if password != pw_sure:
            return render(request, 'register.html', context={
                'errormg': '密码和确认密码不一致',
            })
        # 3、校验邮箱
        if not re.match('^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', context={
                'errormg': '邮箱格式不正确',
            })
        # 4、校验同意协议
        if allow != 'on':
            return render(request, 'register.html', context={
                'errormg': '请同意协议',
            })
        # 5、校验用户名重复不能创建
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:  # 用户不存在
            user = None

        if user:
            return render(request, 'register.html', context={
                'errormg': '用户名已存在',
            })
        user = User.objects.create_user(username, email, password)
        user.is_active = 0  # 没有激活
        user.save()

        # 发送激活邮件，包含激活链接:http://127.0.0.1:8000/user/active/user_id
        # 激活链接中需要包含用户的身份信息,并且要把身份信息进行加密

        #加密用户的身份信息，生成激活token
        serializer = Serializer(settings.SECRET_KEY,3600)
        info = {"confirm":user.id}
        token = serializer.dumps(info)
        token = token.decode() #解码bytes->str

        #发送邮件
        # subject = '天天生鲜欢迎您'
        # message = ''
        # from_email = settings.EMAIL_FROM
        # recipient_list = [email]
        # html_message = '<h1>{0},欢迎您成为天天生鲜注册会员</h1>请点击下面的链接激活您的账户<br/><a href="http://127.0.0.1:8000/user/active/{1}">http://127.0.0.1:8000/user/active/{2}</a>'.format(username,token,token)
        # send_mail(subject,message,from_email,recipient_list,html_message=html_message)
        send_register_active_email.delay(email,username,token)
        #返回应答，跳转到首页
        return redirect(reverse('goods:index'))


class ActionView(View):
    '''用户激活'''
    def get(self,request,token):
        '''进行用户激活'''
        try:
            serializer = Serializer(settings.SECRET_KEY, 3600)
            info = serializer.loads(token)
            user_id = info['confirm']
            user = User.objects.get(id=user_id)
            user.is_active=1
            user.save()
        except SignatureExpired as e:
            #链接过期，重新生成激活的链接
            return HttpResponse('激活链接已过期')

        #成功激活返回登陆页
        return redirect(reverse('user:login'))

class LoginView(View):
    '''登陆页面'''
    def get(self,request):
        if 'username' in request.COOKIES:
            username = request.COOKIES.get('username')
            checked = 'checked'
        else:
            username =''
            checked=''

        return render(request,'login.html',context={'username':username,
                                                    'checked':checked})

    def post(self,request):
        '''登陆校验'''

        #获取数据
        username = request.POST.get("username")
        pwd = request.POST.get("pwd")
        remember = request.POST.get("remember")

        #验证数据
        if not all((username,pwd)):
            return render(request,'login.html',context={'errormg':'用户名或者密码不能为空'})
        #业务处理登陆校验
        user = authenticate(username=username,password=pwd)

        if user is not None:
            if user.is_active:#用户已激活
                #登陆
                login(request, user, backend=None)
                #获取登陆后所要跳转的地址
                #默认跳转到首页
                next_url=request.GET.get('next',reverse('goods:index'))
                response = redirect(next_url) #返回HttpResponseRedirect
                if remember == 'on':
                    response.set_cookie('username',username,max_age=7*24*3600)
                else:
                    response.delete_cookie('username')
                return response


                #跳转到首页


            else:
                return render(request,'login.html',context={'errormg':'用户未激活'})
        else:
            return render(request,'login.html',context={'errormg':'用户名或者密码不正确'})
class LogoutView(View):
    '''退出登陆'''
    def get(self,request):
        '''退出登陆'''
        logout(request)
        return redirect(reverse('user:login'))

#/user
class UserInfoView(LoginRequiredMixin,View):
    '''用户中心-信息页'''
    def get(self,request):
        '''显示'''
        #page='user'
        #requst.user
        #如果用户未登陆->AnonymousUser类的一个实例
        #如果用户登陆->User类的一个实例
        #request.user.is_authenticated()

        #获取用户的个人信息
        user = request.user
        address = Address.objects.get_default_address(user)
        #获取用户的历史浏览记录
        # from redis import StrictRedis
        # sr = StrictRedis(host='122.51.181.167',port='6379',db=9)

        # 获取用户的历史浏览记录
        con = get_redis_connection('default')
        history_key = 'history_%s'%user.id
        #获取用户最新浏览的5个商品的id
        sku_id = con.lrange(history_key,0,4) #[2,3,1]
        #从数据库中查询用户浏览的商品的具体信息
        # goods_li = GoodsSKU.objects.get(id__in=sku_id)
        # goods_res =[]
        # for sku in sku_id:
        #     for goods in goods_li:
        #         if sku == goods.id:
        #             goods_res.append(goods)

        # 遍历获取用户浏览的商品信息
        goods_li =[]
        for id in sku_id:
            goods = GoodsSKU.objects.get(id=id)
            goods_li.append(goods)



        #除了你给模板文件传递的模板变量之外，django框架会把request.user也传给模板文件
        return render(request,'user_center_info.html',{'page':'user',
                                                       'address':address,
                                                       'goods_li':goods_li,
                                                       })
#/user/order
class UserOrderView(LoginRequiredMixin,View):
    '''用户中心-订单页'''
    def get(self,request,page):
        '''显示'''
        #获取订单信息
        user = request.user
        orders = OrderInfo.objects.filter(user=user).order_by('-create_time')
        for order in orders:
            order_skus = OrderGoods.objects.filter(order_id=order.order_id)

            for order_sku in order_skus:
                #计算小计
                amount = order_sku.price * order_sku.count
                order_sku.amount = amount
            #订单添加商品属性
            order.order_skus = order_skus
            #订单状态
            order.status_name = OrderInfo.ORDER_STATUS[str(order.order_status)]

        #分页
        paginator = Paginator(orders,1)


        # 获取第page页的对象s
        try:
            page = int(page)
        except Exception as e:
            page = 1
        order_page = paginator.page(page)

        # todo: 进行页码控制， 页面上最多显示5个页面
        num_pages = paginator.num_pages
        if num_pages < 5:
            pages = range(1, num_pages + 1)
        elif page <= 3:
            pages = range(1, 6)
        elif num_pages - page <= 2:
            pages = range(num_pages - 4, num_pages + 1)
        else:
            pages = range(page - 2, page + 3)

        context ={
            'order_page':order_page,
            'pages':pages,
            'page':'order',
        }
        #page='order'
        return render(request,'user_center_order.html',context)
#user/address
class AddressView(LoginRequiredMixin,View):
    '''用户中心-地址页'''
    def get(self,request):
        '''显示'''
        #获取用户的默认收货地址
        user = request.user
        address = Address.objects.get_default_address(user)

        # try:
        #     address = Address.objects.get(user=request.user,is_default=True)
        # except Address.DoesNotExist:
        #     address = None
        #page='address'
        return render(request,'user_center_site.html',{'page':'address','addres':address})

    def post(self,request):
        '''地址的添加'''
        #接收数据
        user = request.user
        receiver = request.POST.get('receiver')
        addr = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        phone = request.POST.get('phone')
        #校验数据
        if not all([receiver,addr,phone]):
            return render(request,'user_center_site.html',{'errormsg':'收件人、收件地址、电话不能为空'})
        if not re.match(r'^1[3|4|5|7|8][0-9]{9}$',phone):
            return render(request,'user_center_site.html',context={
                'errormsg':'电话号码不符合要求',
            })
        #业务处理：地址添加
        address = Address.objects.get_default_address(user)
        # try:
        #     address = Address.objects.get(user=request.user,is_default=True)
        # except Address.DoesNotExist:
        #     address = None
        if address:
            is_default = False
        else:
            is_default = True

        useraddress = Address.objects.create(user=request.user,
                                             receiver=receiver,
                                             addr=addr,
                                             zip_code=zip_code,
                                             phone=phone,
                                             is_default=is_default)
        return redirect(reverse('user:address'))



        #返回应答







