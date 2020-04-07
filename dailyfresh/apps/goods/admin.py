from django.contrib import admin
from apps.goods.models import GoodsType,IndexPromotionBanner,GoodsSKU
from apps.goods.models import IndexGoodsBanner,IndexTypeGoodsBanner,Goods
from django.core.cache import cache
# Register your models here.
class BaseModelAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        '''新增或更新表中数据是调用'''
        super().save_model(request,obj,form,change)
        #发出任务，让celery worker重新生成首页静态页面
        from celery_tasks.tasks import generate_static_index_html
        generate_static_index_html.delay()

        #清除首页的缓存数据
        cache.delete('index_page_data')

    def delete_model(self, request, obj):
        '''删除表中的数据时调用'''
        super().delete_model(request,obj)
        # 发出任务，让celery worker重新生成首页静态页面
        from celery_tasks.tasks import generate_static_index_html
        generate_static_index_html.delay()

        # 清除首页的缓存数据
        cache.delete('index_page_data')

class GoodsTypeAdmin(BaseModelAdmin):
    pass

class IndexGoodsBannerAdmin(BaseModelAdmin):
    pass

class IndexTypeGoodsBannerAdmin(BaseModelAdmin):
    list_display = ['sku','display_type']

class IndexPromotionBannerAdmin(BaseModelAdmin):
    list_display = ['name']

class GoodsAdmin(BaseModelAdmin):
    list_display = ['name']

class GoodsSKUAdmin(BaseModelAdmin):
    list_display = ['name']



admin.site.register(GoodsType,GoodsTypeAdmin)
admin.site.register(IndexGoodsBanner,IndexGoodsBannerAdmin)
admin.site.register(IndexTypeGoodsBanner,IndexTypeGoodsBannerAdmin)
admin.site.register(IndexPromotionBanner,IndexPromotionBannerAdmin)
admin.site.register(Goods,GoodsAdmin)
admin.site.register(GoodsSKU,GoodsSKUAdmin)

