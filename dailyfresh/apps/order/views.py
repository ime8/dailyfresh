from django.shortcuts import render,reverse,redirect
from django.views.generic.base import View
from django.http import JsonResponse
from apps.goods.models import GoodsSKU
from apps.user.models import Address
from django_redis import get_redis_connection
from utils.mixin import LoginRequiredMixin
from apps.order.models import OrderInfo,OrderGoods
from datetime import datetime
from django.db import transaction
from django.conf import settings
import os
from alipay import AliPay
# Create your views here.

#结算订单页面 /order/place
class OrderPlaceView(LoginRequiredMixin,View):
    '''提交结算订单页面'''
    def post(self,request):
        '''提交结算订单页面'''
        #获取用户
        user = request.user
        #获取数据上平id [1,2,3]
        sku_ids = request.POST.getlist('sku_ids')

        #校验数据
        if not sku_ids:
            return redirect(redirect('cart:show'))
        #获取商品的数量和商品
        conn = get_redis_connection('default')
        cart_key = 'cart_%s'%user.id
        skus = []
        #商品的总价格和总数量
        total_amount = 0
        total_count = 0
        address = Address.objects.filter(user=user)


        for sku_id in sku_ids:
            sku = GoodsSKU.objects.get(id=sku_id) #商品
            count = conn.hget(cart_key,sku_id) #商品数量
            price = sku.price
            amount = price*int(count)
            sku.count = int(count)
            sku.amount = amount
            skus.append(sku)
            total_count+=int(count)
            total_amount+=amount

        trans_fee = 10 #这个写死了，可以重新建一个表分类运费
        total_pay = trans_fee + total_amount #总的支付费用
        sku_ids = ','.join(sku_ids) #1,3
        #组织上下文
        context = {'skus':skus,
                   'total_amount':total_amount,
                   'total_count':total_count,
                   'trans_fee':trans_fee,
                   'total_pay':total_pay,
                   'address':address,
                   'sku_ids':sku_ids,}

        #使用模板
        return render(request,'place_order.html',context)

#订单创建,前端传递的参数:地址id(addr_id) 支付方式(pay_method) 用户要购买的商品id字符串(sku_ids)
#mysql事务：一组mysql语句，要么全执行成功，要么全执行失败
class OrderCommitView1(View):
    '''订单创建'''
    #事务
    @transaction.atomic
    def post(self,request):
        '''订单创建'''
        #判断用户是否登陆
        user = request.user
        if not user.is_authenticated:
            #用户未登陆
            return JsonResponse({'res':0,'errmsg':'用户未登录'})

        #接收参数
        addr_id = request.POST.get('addr_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids')

        #校验参数
        if not all((addr_id,pay_method,sku_ids)):
            return JsonResponse({'res': 1, 'errmsg': '参数不完整'})

        #校验支付方式
        if pay_method not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({'res': 2, 'errmsg': '无效的支付方式'})

        #校验地址
        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist:
            #地址不存在
            return JsonResponse({'res': 3, 'errmsg': '地址非法'})


        #todo:创建订单核心业务
        #订单信息表:df_order_info,订单商品表:df_order_goods
        #todo:用户每下一个订单，就需要向df_order_info表中加入一条记录,用户订单中有几个商品就需要向df_order_goods表中加入几条记录
        #组织参数
        #订单id:20200103+用户id
        order_id = datetime.now().strftime('%Y%m%d%H%M%S')+str(user.id)
        #运费
        transit_price =10

        #总数目和总金额
        total_count = 0
        total_price = 0
        #设置事物保存点
        save_id = transaction.savepoint()
        #todo:向df_order_info表中添加一条记录
        try:
            order = OrderInfo.objects.create(order_id=order_id,
                                             user=user,
                                             addr=addr,
                                             pay_method=pay_method,
                                             total_count=total_count,
                                             total_price=total_price,
                                             transit_price=transit_price,
                                             )
            #todo:用户的订单中有几个商品，需要向df_order_goods表中加入几条记录
            conn = get_redis_connection('default')
            cart_key = 'cart_%s'%user.id
            sku_ids = sku_ids.split(',')

            for sku_id in sku_ids:
                #获取商品信息
                try:
                    #悲观锁加锁
                    #select * from df_goods_sku where id=sku_id for update;
                    sku = GoodsSKU.objects.select_for_update().get(id=sku_id)
                except:
                    #商品不存在
                    transaction.savepoint_rollback(save_id)
                    return JsonResponse({'res':4, 'errmsg': '商品不存在'})

                #从redis中获取用户所要购买的商品数量
                count = conn.hget(cart_key,sku_id)

                #todo:判断商品的库存
                if int(count)>sku.stock:
                    transaction.savepoint_rollback(save_id)
                    return JsonResponse({'res': 6, 'errmsg': '商品库存不足'})

                #todo:向df_order_goods表中添加一条记录
                OrderGoods.objects.create(order=order,
                                          sku=sku,
                                          count=count,
                                          price=sku.price)
                #todo:更新商品的库存和销量
                sku.stock-=int(count)
                sku.sales+=int(count)
                sku.save()

                #todo:累加计算订单商品的总数量和总价格
                amount = sku.price*int(count)
                total_count+=int(count)
                total_price+=amount

            #todo:更新订单信息表中的商品的总数量和总价格
            order.total_price=total_price
            order.total_count = total_count
            order.save()
        except Exception as e:
            transaction.savepoint_rollback(save_id)
            return JsonResponse({'res':7,'errmsg':'下单失败'})

        #提交事务
        transaction.savepoint_commit(save_id)

        #todo:清除用户购物车中对应的记录[1,3]
        conn.hdel(cart_key,*sku_ids)
        #返回应答
        return JsonResponse({'res': 5, 'message': '创建成功'})

#乐观锁
class OrderCommitView(View):
    '''订单创建'''
    #事务
    @transaction.atomic
    def post(self,request):
        '''订单创建'''
        #判断用户是否登陆
        user = request.user
        if not user.is_authenticated:
            #用户未登陆
            return JsonResponse({'res':0,'errmsg':'用户未登录'})

        #接收参数
        addr_id = request.POST.get('addr_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids')

        #校验参数
        if not all((addr_id,pay_method,sku_ids)):
            return JsonResponse({'res': 1, 'errmsg': '参数不完整'})

        #校验支付方式
        if pay_method not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({'res': 2, 'errmsg': '无效的支付方式'})

        #校验地址
        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist:
            #地址不存在
            return JsonResponse({'res': 3, 'errmsg': '地址非法'})


        #todo:创建订单核心业务
        #订单信息表:df_order_info,订单商品表:df_order_goods
        #todo:用户每下一个订单，就需要向df_order_info表中加入一条记录,用户订单中有几个商品就需要向df_order_goods表中加入几条记录
        #组织参数
        #订单id:20200103+用户id
        order_id = datetime.now().strftime('%Y%m%d%H%M%S')+str(user.id)
        #运费
        transit_price =10

        #总数目和总金额
        total_count = 0
        total_price = 0
        #设置事物保存点
        save_id = transaction.savepoint()
        #todo:向df_order_info表中添加一条记录
        try:
            # todo： 向df_order_info表中添加一条记录
            order = OrderInfo.objects.create(order_id=order_id,
                                             user=user,
                                             address=addr,
                                             pay_method=pay_method,
                                             total_count=total_count,
                                             total_price=total_price,
                                             transit_price=transit_price)

            # todo: 向df_order_goods表中添加记录
            conn = get_redis_connection('default')
            cart_key = 'cart_{0}'.format(user.id)

            sku_ids = sku_ids.split(',')
            for sku_id in sku_ids:
                # 使用乐观锁，需多重复几次，需要数据库的隔离级别为：提交读Read committed。
                for i in range(3):
                    # 获取商品信息
                    try:
                        sku = GoodsSKU.objects.get(id=sku_id)
                    except Exception as e:
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res': 4, 'errmsg': '商品不存在'})

                    # 从redis中获取商品的数量
                    count = conn.hget(cart_key, sku_id)

                    # todo: 判断某一个商品的库存
                    if int(count) > sku.stock:
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res': 6, 'errmsg': '商品库存不足'})

                    # todo: 更新商品的库存和销量
                    orgin_stock = sku.stock
                    orgin_sales = sku.sales
                    new_stock = orgin_stock - int(count)
                    new_sales = orgin_sales + int(count)

                    # 加乐观锁
                    # update df_goods_sku set stock=new_stock, sales=new_sales
                    # where id=sku_id and stock=orgin_stock;
                    res = GoodsSKU.objects.filter(id=sku_id, stock=orgin_stock).update(stock=new_stock, sales=new_sales)
                    if res == 0:
                        if i == 2:
                            transaction.savepoint_rollback(save_id)
                            return JsonResponse({'res': 7, 'errmsg': '下单失败2'})
                        continue

                    # todo: 向df_order_goods表中添加一条记录
                    OrderGoods.objects.create(order=order,
                                              sku=sku,
                                              count=count,
                                              price=sku.price)

                    # todo: 累加计算订单商品的总数量和总价格
                    amount = sku.price * int(count)
                    total_count += int(count)
                    total_price += amount

                    # 如果成功了，跳出循环
                    break

            # todo: 更新订单信息表中的商品的总数量和总价格
            order.total_price = total_price
            order.total_count = total_count
            order.save()
        except Exception as e:
            transaction.savepoint_rollback(save_id)
            return JsonResponse({'res': 7, 'errmsg': '下单失败'})
        #提交事务
        transaction.savepoint_commit(save_id)

        #todo:清除用户购物车中对应的记录[1,3]
        conn.hdel(cart_key,*sku_ids)
        #返回应答
        return JsonResponse({'res': 5, 'message': '创建成功'})

#支付订单,order/pay
class OrderPayView(View):
    '''支付订单'''
    def post(self,request):
        '''订单支付'''
        user = request.user
        if not user.is_authenticated:
            #用户未登陆
            return JsonResponse({'res':0,'errmsg':'用户未登录'})
        #获取数据
        #订单id
        order_id = request.POST.get('order_id')

        #数据校验
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': '订单id为空'})

        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user,
                                          pay_method=3,
                                          order_status = 1,

                                          )
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '订单不存在'})

        #业务处理:使用python sdk调用支付宝的支付接口
        #初始化
        alipay = AliPay(
            appid="2016101800714203",#应用id
            app_notify_url=None,#默认回调Url
            app_private_key_string=os.path.join(settings.BASE_DIR,'apps/order/app_private_key.pem'),
            alipay_public_key_string=os.path.join(settings.BASE_DIR,'apps/order/alipay_public_key.pem'),
            sign_type="RSA2",#RSA 或者RSA2
            debug=True,#默认False是正式环境
        )
        #调用支付接口
        #电脑网站支付，需要跳转到https://openapi.alipaydev.com/gateway.do+order_string
        #总金额
        total_pay = order.total_price+order.transit_price
        #返回应答
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id,#订单id
            total_amount=total_pay,#支付总金额
            subject='天天生鲜%s'%order_id,
            return_url=None,#可选
            notify_url=None,#可选，不填则使用默认notify url
        )
        #返回应答
        pay_url = 'https://openapi.alipaydev.com/gateway.do'+order_string
        return JsonResponse({'res': 3, 'pay_url': pay_url})

#ajax post
#前端传递的参数:订单id order_id
class CheckPayView(View):
    '''查看订单支付状态'''
    def post(self,request):
        user = request.user
        if not user.is_authenticated:
            # 用户未登陆
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})
        # 获取数据
        # 订单id
        order_id = request.POST.get('order_id')

        # 数据校验
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': '订单id为空'})

        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user,
                                          pay_method=3,
                                          order_status=1,

                                          )
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '订单不存在'})

        # 业务处理:使用python sdk调用支付宝的支付接口
        # 初始化
        alipay = AliPay(
            appid="2016101800714203",  # 应用id
            app_notify_url=None,  # 默认回调Url
            app_private_key_string=os.path.join(settings.BASE_DIR, 'apps/order/app_private_key.pem'),
            alipay_public_key_string=os.path.join(settings.BASE_DIR, 'apps/order/alipay_public_key.pem'),
            sign_type="RSA2",  # RSA 或者RSA2
            debug=True,  # 默认False是正式环境
        )
        while True:
            #调用支付宝的交易查询接口
            response = alipay.api_alipay_trade_query(trade_no=order_id)
            code = response.get('code')
            if code =='10000' and response.get('trade_status')=='TRADE_SUCCESS':
                #支付成功
                #获取支付宝交易号
                trade_no = response.get('trade_no')
                #更新订单状态
                order.trade_no = trade_no
                order.order_status = 4#待评价
                order.save()
                #返回结果
                return JsonResponse({'res':3,'message':'支付成功'})
            elif code== '40004' or (code == '10000' and response.get('trade_status') == 'WAIT_BUYER_PAY'):
                #等待买家付款
                import time
                time.sleep(5)
                continue
            else:
                #支付出错
                return JsonResponse({'res': 4, 'errmsg': '支付失败'})

class CommentView(LoginRequiredMixin,View):
    '''订单评论'''
    def get(self,request,order_id):
        '''提供评论页面'''
        user = request.user

        #校验数据
        if not order_id:
            return redirect(reverse('user:order'))
        try:
            order = OrderInfo.objects.get(order_id=order_id,user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse("user:order"))

        #根据订单状态获取订单的状态标题
        order.status_name = OrderInfo.ORDER_STATUS[order.order_status]

        #获取订单商品信息
        order_skus = OrderGoods.objects.filter(order_id=order_id)
        for order_sku in order_skus:
            #计算商品的小计
            amount = order_sku.count*order_sku.price
            #动态给order_sku增加属性amount,保存商品小计
            order_sku.amount = amount
        #动态给order增加属性order_skus,保存订单商品信息
        order.order_skus = order_skus

        #使用模板
        return render(request,"order_comment.html",{"order":order})

    def post(self, request, order_id):
        """处理评论内容"""
        user = request.user

        # 校验参数
        if not order_id:
            return redirect(reverse('user:order'))

        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user,
                                          )
        except OrderInfo.DoesNotExist:
            return redirect(reverse('user:order'))

        # 获取评论条数
        total_count = request.POST.get('total_count')
        total_count = int(total_count)

        for i in range(1, total_count + 1):
            # 获取评论的商品的id
            sku_id = request.POST.get('sku_{0}'.format(i))

            # 获取评论内容
            content = request.POST.get('content_{0}'.format(i))

            try:
                order_goods = OrderGoods.objects.get(order=order, sku_id=sku_id)
            except OrderGoods.DoesNotExist:
                continue

            order_goods.comment = content
            order_goods.save()

        order.order_status = 5
        order.save()

        return redirect(reverse('user:order', kwargs={'page': 1}))














