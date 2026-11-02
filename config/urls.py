from django.urls import path
from pos import views
urlpatterns = [
 path("login/",views.login), path("signup/",views.signup), path("logout/",views.logout),
 path("",views.dashboard), path("products/",views.products), path("products/save/",views.save_product), path("products/<str:pid>/delete/",views.delete_product),
 path("sales/",views.sales), path("sales/checkout/",views.checkout), path("sales/<str:sale_id>/complete/",views.complete_sale),
 path("deadstock/",views.deadstock), path("api/deadstock/",views.deadstock_data), path("deadstock/<str:pid>/action/",views.deadstock_action),
 path("reports/",views.reports), path("api/reports/",views.report_data), path("reports/pdf/",views.report_pdf), path("api/margin-alerts/",views.margin_alerts),
 path("categories/",views.categories), path("categories/save/",views.save_category), path("categories/<str:cat_id>/threshold/",views.set_threshold), path("categories/<str:cat_id>/decision/",views.category_decision), path("categories/<str:cat_id>/delete/",views.delete_category), path("tax/refresh/",views.refresh_tax),
]
