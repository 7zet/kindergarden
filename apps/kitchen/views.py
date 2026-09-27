from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from io import BytesIO

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Max, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from openpyxl import Workbook

from apps.attendance.models import Attendance, Status
from apps.web.access import APPROVE_MENU, EDIT_MENU, EDIT_STOCK, VIEW_KITCHEN, require

from .forms import (DishForm, DishIngredientForm, IngredientForm, MenuDishForm,
                    StockReceiveForm, SupplierForm)
from .models import DailyMenu, Dish, DishIngredient, Ingredient, MenuDish, StockMove, Supplier
from .services import approve_menu, enter_fact, monthly_report, receive_stock, reverse_move
from .units import display_quantity, to_grams


def kg_of(request): return request.user.kindergarten


def tabs():
    return [("kitchen_menu", "Bugungi menyu"), ("kitchen_dishes", "Taomlar"),
            ("kitchen_ingredients", "Masalliqlar"), ("kitchen_stock", "Ombor"),
            ("kitchen_report", "Hisobot")]


@require(VIEW_KITCHEN)
def menu_today(request):
    kg = kg_of(request)
    try: day = datetime.strptime(request.GET.get("date", ""), "%Y-%m-%d").date()
    except ValueError: day = timezone.localdate()
    menu, _ = DailyMenu.objects.get_or_create(kindergarten=kg, date=day)
    if request.method == "POST" and menu.status == DailyMenu.Status.DRAFT:
        action = request.POST.get("action")
        if action == "add_dish" and request.user.has_perm(EDIT_MENU):
            dish = get_object_or_404(Dish, pk=request.POST.get("dish"), kindergarten=kg, is_active=True)
            MenuDish.objects.get_or_create(menu=menu, dish=dish, defaults={"meal_type": dish.meal_type})
        elif action == "remove_dish" and request.user.has_perm(EDIT_MENU):
            menu.dishes.filter(pk=request.POST.get("entry")).delete()
        return redirect(f"{reverse('kitchen_menu')}?date={day:%Y-%m-%d}")
    present = Attendance.objects.filter(enrollment__child__kindergarten=kg, day=day,
                                        status=Status.PRESENT).values("enrollment_id").distinct().count()
    return render(request, "kitchen/menu.html", {"kg":kg, "tabs":tabs(), "menu":menu,
        "day":day, "prev":day-timedelta(days=1), "next":day+timedelta(days=1),
        "present":present, "available_dishes":Dish.objects.filter(kindergarten=kg,is_active=True),
        "entries":menu.dishes.select_related("dish"),
        "lines":menu.lines.select_related("ingredient")})


@require(APPROVE_MENU)
def menu_approve(request, pk):
    menu = get_object_or_404(DailyMenu, pk=pk, kindergarten=kg_of(request))
    if request.method == "POST":
        try: approve_menu(menu, request.user)
        except ValidationError as exc: messages.error(request, "; ".join(exc.messages))
        else: messages.success(request, "Taomnoma tasdiqlandi va reja ombordan chiqarildi.")
    return redirect(f"{reverse('kitchen_menu')}?date={menu.date:%Y-%m-%d}")


@require(EDIT_STOCK)
def menu_fact(request, pk):
    menu = get_object_or_404(DailyMenu, pk=pk, kindergarten=kg_of(request))
    if request.method == "POST":
        facts = {}
        try:
            for line in menu.lines.select_related("ingredient"):
                facts[str(line.ingredient_id)] = to_grams(
                    request.POST.get(f"fact_{line.ingredient_id}"),
                    line.ingredient.display_unit, line.ingredient.gram_per_piece)
            enter_fact(menu, facts, request.user)
        except (ValidationError, ValueError) as exc:
            messages.error(request, "; ".join(exc.messages) if hasattr(exc,"messages") else str(exc))
        else: messages.success(request, "Haqiqiy sarf saqlandi.")
    return redirect(f"{reverse('kitchen_menu')}?date={menu.date:%Y-%m-%d}")


@require(VIEW_KITCHEN)
def dish_list(request):
    qs = Dish.objects.filter(kindergarten=kg_of(request)).annotate(norm_count=Count("ingredients"))
    q=request.GET.get("q","").strip(); meal=request.GET.get("meal","")
    if q: qs=qs.filter(name__icontains=q)
    if meal: qs=qs.filter(meal_type=meal)
    return render(request,"kitchen/dishes.html",{"kg":kg_of(request),"tabs":tabs(),"dishes":qs,"q":q,"meal":meal,"meal_types":Dish.MealType.choices})


@require(EDIT_MENU)
def dish_form(request, pk=None):
    kg=kg_of(request); dish=get_object_or_404(Dish,pk=pk,kindergarten=kg) if pk else None
    form=DishForm(request.POST or None,instance=dish)
    if request.method=="POST" and request.POST.get("action")=="delete_norm" and dish:
        dish.ingredients.filter(pk=request.POST.get("norm")).delete(); return redirect("kitchen_dish_edit",pk=dish.pk)
    if request.method=="POST" and request.POST.get("action")=="add_norm" and dish:
        nf=DishIngredientForm(request.POST); nf.fields["ingredient"].queryset=Ingredient.objects.filter(kindergarten=kg,is_active=True)
        if nf.is_valid():
            norm=nf.save(commit=False); norm.dish=dish; norm.full_clean(); norm.save(); return redirect("kitchen_dish_edit",pk=dish.pk)
    if request.method=="POST" and not request.POST.get("action") and form.is_valid():
        dish=form.save(commit=False); dish.kindergarten=kg; dish.save(); return redirect("kitchen_dish_edit",pk=dish.pk)
    nf=DishIngredientForm(); nf.fields["ingredient"].queryset=Ingredient.objects.filter(kindergarten=kg,is_active=True)
    return render(request,"kitchen/form.html",{"kg":kg,"tabs":tabs(),"form":form,"norm_form":nf,"object":dish,"title":"Taom"})


@require(VIEW_KITCHEN)
def ingredient_list(request):
    qs=Ingredient.objects.filter(kindergarten=kg_of(request)).with_stock(); q=request.GET.get("q","").strip(); category=request.GET.get("category","")
    if q: qs=qs.filter(name__icontains=q)
    if category: qs=qs.filter(category=category)
    return render(request,"kitchen/ingredients.html",{"kg":kg_of(request),"tabs":tabs(),"ingredients":qs,"q":q,"category":category,"categories":Ingredient.Category.choices})


@require(EDIT_STOCK)
def ingredient_form(request,pk=None):
    kg=kg_of(request); obj=get_object_or_404(Ingredient,pk=pk,kindergarten=kg) if pk else None
    initial={"min_stock":(obj.min_stock_g/1000 if obj else 0)}; form=IngredientForm(request.POST or None,instance=obj,initial=initial)
    if request.method=="POST" and form.is_valid():
        obj=form.save(commit=False); obj.kindergarten=kg; obj.min_stock_g=to_grams(form.cleaned_data["min_stock"] or 0,"kg") if form.cleaned_data["min_stock"] else Decimal("0"); obj.full_clean(); obj.save(); return redirect("kitchen_ingredients")
    return render(request,"kitchen/form.html",{"kg":kg,"tabs":tabs(),"form":form,"title":"Masalliq"})


@require(VIEW_KITCHEN)
def stock_list(request):
    kg=kg_of(request); ingredients=Ingredient.objects.filter(kindergarten=kg).with_stock().annotate(last_received=Max("moves__happened_at",filter=Q(moves__direction="in",moves__is_reversed=False)))
    moves=StockMove.objects.filter(kindergarten=kg).select_related("ingredient","supplier","created_by")
    start=request.GET.get("start"); end=request.GET.get("end")
    if start: moves=moves.filter(happened_at__gte=start)
    if end: moves=moves.filter(happened_at__lte=end)
    return render(request,"kitchen/stock.html",{"kg":kg,"tabs":tabs(),"ingredients":ingredients,"moves":moves[:200],"start":start,"end":end})


@require(EDIT_STOCK)
def stock_receive(request):
    kg=kg_of(request); form=StockReceiveForm(request.POST or None); form.fields["ingredient"].queryset=Ingredient.objects.filter(kindergarten=kg,is_active=True); form.fields["supplier"].queryset=Supplier.objects.filter(kindergarten=kg,is_active=True)
    if request.method=="POST" and form.is_valid():
        receive_stock(kindergarten=kg,ingredient=form.cleaned_data["ingredient"],quantity_g=form.cleaned_data["quantity_g"],unit_price=form.cleaned_data.get("unit_price"),happened_at=form.cleaned_data["happened_at"],supplier=form.cleaned_data.get("supplier"),document_number=form.cleaned_data.get("document_number", ""),note=form.cleaned_data.get("note", ""),user=request.user); messages.success(request,"Ombor kirimi saqlandi."); return redirect("kitchen_stock")
    return render(request,"kitchen/form.html",{"kg":kg,"tabs":tabs(),"form":form,"title":"Ombor kirimi"})


@require(EDIT_STOCK)
def stock_reverse(request,pk):
    move=get_object_or_404(StockMove,pk=pk,kindergarten=kg_of(request))
    if request.method=="POST":
        reason=request.POST.get("reason","").strip()
        if not reason: messages.error(request,"Storno sababi majburiy.")
        else:
            try: reverse_move(move,reason,request.user)
            except ValidationError as exc: messages.error(request,"; ".join(exc.messages))
            else: messages.success(request,"Harakat storno qilindi.")
    return redirect("kitchen_stock")


@require(EDIT_STOCK)
def supplier_form(request):
    form=SupplierForm(request.POST or None)
    if request.method=="POST" and form.is_valid(): obj=form.save(commit=False); obj.kindergarten=kg_of(request); obj.save(); return redirect("kitchen_receive")
    return render(request,"kitchen/form.html",{"kg":kg_of(request),"tabs":tabs(),"form":form,"title":"Yetkazib beruvchi"})


def _period(request):
    try:return datetime.strptime(request.GET.get("period",""),"%Y-%m").date().replace(day=1)
    except ValueError:return timezone.localdate().replace(day=1)


@require(VIEW_KITCHEN)
def report(request):
    period=_period(request); rows,cost=monthly_report(kg_of(request),period)
    return render(request,"kitchen/report.html",{"kg":kg_of(request),"tabs":tabs(),"period":period,"rows":rows,"cost":cost})


@require(VIEW_KITCHEN)
def report_excel(request):
    period=_period(request); rows,cost=monthly_report(kg_of(request),period); wb=Workbook(); ws=wb.active; ws.title="Oshxona hisoboti"; ws.append(["Masalliq","Oy boshi (g)","Kirim (g)","Reja (g)","Fakt (g)","Farq (g)","Oy oxiri (g)"])
    for r in rows: ws.append([r["ingredient"].name,float(r["opening"]),float(r["incoming"]),float(r["planned"]),float(r["actual"]),float(r["diff"]),float(r["closing"])])
    ws.append([]); ws.append(["Jami xarajat",float(cost)]); stream=BytesIO(); wb.save(stream); response=HttpResponse(stream.getvalue(),content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"); response["Content-Disposition"]=f'attachment; filename="kitchen-{period:%Y-%m}.xlsx"'; return response

