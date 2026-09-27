from django.urls import path
from . import views

urlpatterns = [
    path("", views.menu_today, name="kitchen_menu"),
    path("menu/<uuid:pk>/approve/", views.menu_approve, name="kitchen_menu_approve"),
    path("menu/<uuid:pk>/fact/", views.menu_fact, name="kitchen_menu_fact"),
    path("dishes/", views.dish_list, name="kitchen_dishes"),
    path("dishes/new/", views.dish_form, name="kitchen_dish_new"),
    path("dishes/<uuid:pk>/", views.dish_form, name="kitchen_dish_edit"),
    path("ingredients/", views.ingredient_list, name="kitchen_ingredients"),
    path("ingredients/new/", views.ingredient_form, name="kitchen_ingredient_new"),
    path("ingredients/<uuid:pk>/", views.ingredient_form, name="kitchen_ingredient_edit"),
    path("stock/", views.stock_list, name="kitchen_stock"),
    path("stock/receive/", views.stock_receive, name="kitchen_receive"),
    path("stock/<uuid:pk>/reverse/", views.stock_reverse, name="kitchen_reverse"),
    path("suppliers/new/", views.supplier_form, name="kitchen_supplier_new"),
    path("report/", views.report, name="kitchen_report"),
    path("report.xlsx", views.report_excel, name="kitchen_report_excel"),
]

