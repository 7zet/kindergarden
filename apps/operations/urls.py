from django.urls import path

from . import views

urlpatterns = [
    path("outbox/", views.outbox_monitor, name="outbox_monitor"),
    path("", views.finance_dashboard, name="finance_dashboard"),
    path("expenses/", views.expense_list, name="expense_list"),
    path("expenses/new/", views.expense_new, name="expense_new"),
    path("expenses/<uuid:pk>/void/", views.expense_void, name="expense_void"),
    path("categories/new/", views.category_new, name="expense_category_new"),
    path("suppliers/new/", views.supplier_new, name="supplier_new"),
    path("cash-shifts/", views.cash_shifts, name="cash_shifts"),
    path("cash-shifts/open/", views.cash_shift_open, name="cash_shift_open"),
    path("cash-shifts/<uuid:pk>/close/", views.cash_shift_close, name="cash_shift_close"),
    path("payroll/", views.payroll, name="payroll"),
    path("payroll/compensation/new/", views.compensation_new, name="compensation_new"),
    path("payroll/generate/", views.payroll_generate, name="payroll_generate"),
    path("payroll/<uuid:pk>/edit/", views.payroll_edit, name="payroll_edit"),
    path("announcements/", views.announcements, name="announcements"),
    path("reports/excel/", views.report_excel, name="management_report_excel"),
    path("reports/pdf/", views.report_pdf, name="management_report_pdf"),
]
