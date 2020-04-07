from django.shortcuts import render
from django.views.generic.base import View
from django.http import JsonResponse
from apps.goods.models import GoodsSKU
from django_redis import get_redis_connection
from utils.mixin import LoginRequiredMixin

# Create your views here.
#/cart/add
class CartAddView(View):
    '''添加购物车'''
    def post(self,request):
        '''购物车的添加'''
        user = request.user
        #判断用户是否登陆，登陆了才能添加购物车
        if not user.is_authenticated:
            return JsonResponse({'res':0,'errmsg':'用户未登陆'})
        #获取数据
        sku_id = request.POST.get('sku_id') #商品id
        count = request.POST.get('count') #商品的数量
        print("count",type(count))

        #校验数据的有效性
        if not all([sku_id,count]):
            return JsonResponse({'res':1,'errmsg':'数据不完整'})

        try:#商品数量不是整数
            count = int(count)
        except Exception as e:
            return JsonResponse({'res': 2, 'errmsg': '数据不正确'})

        # 校验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '商品不存在'})

        #进行业务的处理添加购物车
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        #先尝试获取sku_id的值 —>hget cart_key 属性
        #如果sku_id在hash中不存在，hget返回None
        cart_count = conn.hget(cart_key,sku_id)
        print("")
        if cart_count:
            #累加数量
            count += int(cart_count)

        #校验商品是否还有库存
        if sku.stock<count:
            return JsonResponse({'res': 4, 'errmsg': '商品库存已不足'})

        #设置hash中sku_id对应的值
        #hset —>如果sku_id已经存在，更新数据，如果sku_id不存在，添加数量
        conn.hset(cart_key,sku_id,count)
        #获取商品条目数
        total_count = conn.hlen(cart_key)
        #返回应答
        return JsonResponse({'res': 5,'total_count':total_count, 'message': '购物车添加成功'})
#/cart
class CartInfoView(LoginRequiredMixin,View):
    '''购物车信息'''
    def get(self,request):
        '''购物车信息'''

        #从redis中获取购物车信息
        user = request.user
        conn = get_redis_connection('default')
        cart_key = "cart_%s"%user.id

        #存储的购物车格式"card_id":{"商品id sku_id":"商品数量 count"}
        #hgetall Return a Python dict
        cart = conn.hgetall(cart_key)

        #获取商品信息
        skus =[]
        #总数量
        total_count = 0
        #总价格
        total_amount = 0
        for sku_id,count in cart.items():
            #商品
            sku = GoodsSKU.objects.get(id=sku_id)
            #商品总价
            amount = sku.price*int(count)
            #给商品增加属性
            sku.amount = amount
            #给商品增加数量属性
            sku.count = int(count)
            skus.append(sku)
            #商品总价格
            total_amount += amount
            #商品总数量
            total_count +=int(count)

        #组织上下文
        context = {"skus":skus,
                   "total_amount":total_amount,
                   "total_count":total_count}
        #使用模板
        return render(request,'cart.html',context)

# 请求方式：ajax post
# 传递参数：商品id sku_id ,商品数量 count
# 返回： JsonResponse({'res':5, 'message': '更新成功', 'total_count': total_count})
# /cart/update
class CartUpdateView(View):
    '''购物车记录更新'''
    def post(self,request):
        '''购物车记录更新'''
        user = request.user
        # 判断用户是否登陆，登陆了才能添加购物车
        if not user.is_authenticated:
            return JsonResponse({'res': 0, 'errmsg': '用户未登陆'})
        # 获取数据
        sku_id = request.POST.get('sku_id')  # 商品id
        count = request.POST.get('count')  # 商品的数量
        #print("count", type(count))

        # 校验数据的有效性
        if not all([sku_id, count]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})

        try:  # 商品数量不是整数
            count = int(count)
        except Exception as e:
            return JsonResponse({'res': 2, 'errmsg': '数据不正确'})

        # 校验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '商品不存在'})

        # 进行业务的处理添加购物车
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id

        if count>sku.stock:
            return JsonResponse({'res': 4, 'errmsg': '商品库存不足'})
        #更新
        conn.hset(cart_key,sku_id,count)

        #计算用户购物车中商品的总件数{'1':5,''2:3}
        total_count = 0
        vals = conn.hvals(cart_key)
        for val in vals:
            total_count+=int(val)
        return JsonResponse({'res':5,'total_count':total_count,'message': '购物车添加成功'})

# 请求方式：ajax post
# 传递参数：商品id sku_id
# /cart/delete
class CartDeleteView(View):
    '''购物车删除'''
    def post(self,request):
        '''购物车删除'''

        #获取用户
        user = request.user
        #判断用户是否登陆
        if not user.is_authenticated:
            return JsonResponse(({'res': 0, 'errmsg': '用户未登陆'}))
        sku_id = request.POST.get('sku_id')

        if not sku_id:
            return JsonResponse(({'res': 1, 'errmsg': '数据不完整'}))

        # 校验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '商品不存在'})

        # 进行业务的处理删除购物车
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        conn.hdel(cart_key,sku_id)

        # 计算用户购物车中商品的总件数{'1':5,''2:3}
        total_count = 0
        vals = conn.hvals(cart_key)
        for val in vals:
            total_count += int(val)
        #使用模板
        return JsonResponse({'res': 5,'total_count':total_count, 'errmsg': '删除成功'})














