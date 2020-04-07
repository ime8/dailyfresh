from django.shortcuts import render,redirect,reverse
from django.views.generic.base import View
from django.core.cache import cache
from django.core.paginator import Paginator
from django_redis import get_redis_connection
from apps.goods.models import GoodsType,IndexGoodsBanner,IndexPromotionBanner,IndexTypeGoodsBanner
from apps.goods.models import GoodsSKU
from apps.order.models import OrderGoods
from django.conf import settings
import os
# Create your views here.
# goods/index
class IndexView(View):
    '''首頁'''
    def get(self,request):
        #获取用戶信息
        user = request.user
        #判断缓存
        try:
            context = cache.get('index_page_data')
        except Exception as e:
            context = None

        if context is None:
            print("设置缓存")
            #沒有缓存数据
            #获取商品种类信息
            types = GoodsType.objects.all()

            #获取首页轮播商品信息
            goods_banners = IndexGoodsBanner.objects.all().order_by('index')

            #获取首页促销商品信息
            promotion_banners = IndexPromotionBanner.objects.all().order_by('index')

            #获取首页分类商品展示信息
            for type in types:#GoodsType
                #获取type种类首页分类商品的图片展示信息
                image_goods_banners = IndexTypeGoodsBanner.objects.filter(type=type,display_type=1).order_by('index')

                #获取Type种类首页分类商品的文字展示信息
                font_goods_banners = IndexTypeGoodsBanner.objects.filter(type=type,display_type=0).order_by('index')
                #动态给type增加属性，分别保存首页分类商品的图片展示信息和文字信息
                type.image_goods_banners = image_goods_banners
                type.font_goods_banners = font_goods_banners

                #组织上下文
                context = {
                        'types':types,
                        'goods_banners':goods_banners,
                        'promotion_banners':promotion_banners,
                }

                #設置緩存
                cache.set('index_page_data',context,3600)

        #获取用户购物车中商品的数目
        user = request.user
        cart_count = 0
        if user.is_authenticated:#用户已经登陆
            #获取购物车数量使用hash

            #连接setting配置的redis
            conn = get_redis_connection('default')
            cart_key = 'cart_%d'%user.id
            #获取物品种类的数量
            cart_count = conn.hlen(cart_key)
        context.update(cart_count=cart_count)
        return render(request, 'index.html', context)

#/goods/商品id
class DetailView(View):
    '''详情页'''
    def get(self,request,goods_id):
        '''显示详情页'''
        try:
            sku = GoodsSKU.objects.get(id=goods_id)
        except GoodsSKU.DoesNotExist:
            #商品不存在
            return redirect(reverse('goods:index'))
        #获取商品的分类信息
        types = GoodsType.objects.all()

        #获取商品的评论信息
        sku_orders =OrderGoods.objects.filter(sku=sku).exclude(comment='')

        #获取新品信息
        new_skus = GoodsSKU.objects.filter(type=sku.type).order_by('-create_time')[:2]

        # 获取用户购物车中商品的数目
        user = request.user
        cart_count = 0
        if user.is_authenticated:  # 用户已经登陆
            # 获取购物车数量使用hash
            # 连接setting配置的redis
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            # 获取物品种类的数量
            cart_count = conn.hlen(cart_key)

            # 获取用户历史浏览记录，使用list
            conn = get_redis_connection('default')
            # 浏览历史记录每个用户浏览商品的key
            history_key = 'history_%d' % user.id
            # 删除列表中的已存在浏览的goods_id
            conn.lrem(history_key, 0, goods_id)

            # 把新浏览的goods_id插入到列表的左侧
            conn.lpush(history_key, goods_id)
            # 只保存用户最新浏览的5条记录
            conn.ltrim(history_key, 0, 4)

        #组织模板上下文
        context = {'sku':sku,
                   'sku_orders':sku_orders,
                   'new_skus':new_skus,
                   'cart_count':cart_count,
                   'types':types,

                   }
        #使用模板
        return render(request,'detail.html',context)

#种类id 页码 排序方式
#restful_api -->请求一种资源
#/list?type_id=种类id&page=页码&sort=排序方式
#/list/种类id/页码/排序方式
#/list/种类id/页码?sort=排序方式(选择这一种方式)
class ListView(View):
    '''列表页'''
    def get(self,request,type_id,page):
        '''显示列表页'''
        try:
            type = GoodsType.objects.get(id=type_id)
        except GoodsType.DoesNotExist:
            #商品种类不存在
            return redirect(reverse('goods:index'))
        #获取商品种类信息
        types = GoodsType.objects.all()

        #获取排序的方式 #获取分类商品的信息
        # sort=default 按照商品默认id排序
        # sort=price 按照商品价格排序
        # sort=hot 按照商品销售排序
        sort = request.GET.get('sort')
        skus_all = GoodsSKU.objects.filter(type=type)
        if sort == 'price':
            skus = skus_all.order_by('price')
        elif sort == 'hot':
            skus = skus_all.order_by('-sales')
        else:
            sort = 'default'
            skus = skus_all.order_by('-id')

        #对商品进行分页
        paginator = Paginator(skus,1)
        #获取第page页的内容
        try:
            page = int(page)
        except Exception as e:
            page = 1
        if page>paginator.num_pages:#大于页面总数
            page = 1

        # 获取第page页的paginator.page实例对象
        skus_page = paginator.page(page)

        #todo:进行页码的控制，页面上最多显示5个页码
        #1.总页数小于5页，页面上显示所有页码
        #2.如果当前页是前3页，显示1-5页
        #3.如果当前页是最后3页，显示后5页
        #4.其他情况，显示当前页的前2页，当前页，当前页的后两页
        num_pages = paginator.num_pages
        if num_pages < 5:
            pages = range(1,num_pages+1)
        elif num_pages <= 3:
            pages = range(1,6)
        elif num_pages - page <= 2:
            pages = range(num_pages-4,num_pages+1)
        else:
            pages = range(page-2,page+3)


        # 获取新品信息
        new_skus = GoodsSKU.objects.filter(type=type).order_by('-create_time')[:2]

        # 获取用户购物车中商品的数目
        user = request.user
        cart_count = 0
        if user.is_authenticated:  # 用户已经登陆
            # 获取购物车数量使用hash
            # 连接setting配置的redis
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            # 获取物品种类的数量
            cart_count = conn.hlen(cart_key)

        context = {'types':types,
                   'skus_page':skus_page,
                   'new_skus':new_skus,
                   'cart_count':cart_count,
                   'pages':pages,
                   'type':type,
                   'sort':sort}
        return render(request,'list.html',context)