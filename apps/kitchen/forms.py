from django import forms
from .models import Dish, DishIngredient, Ingredient, MenuDish, StockMove, Supplier
from .units import to_grams


class IngredientForm(forms.ModelForm):
    min_stock = forms.DecimalField(label="Minimal zaxira", min_value=0)
    class Meta:
        model = Ingredient
        fields = ["name", "category", "display_unit", "gram_per_piece", "is_active"]


class DishForm(forms.ModelForm):
    class Meta: model = Dish; fields = ["name", "meal_type", "description", "is_active"]


class DishIngredientForm(forms.ModelForm):
    class Meta: model = DishIngredient; fields = ["ingredient", "grams_per_child"]


class MenuDishForm(forms.ModelForm):
    class Meta: model = MenuDish; fields = ["dish"]


class StockReceiveForm(forms.Form):
    ingredient = forms.ModelChoiceField(queryset=Ingredient.objects.none(), label="Masalliq")
    quantity = forms.DecimalField(label="Miqdor", min_value=0.01)
    unit = forms.ChoiceField(choices=[("kg","kg"),("litr","litr"),("dona","dona"),("g","gramm")])
    unit_price = forms.DecimalField(label="1 kg narxi", min_value=0, required=False)
    happened_at = forms.DateField(label="Sana", widget=forms.DateInput(attrs={"type":"date"}))
    supplier = forms.ModelChoiceField(queryset=Supplier.objects.none(), required=False)
    document_number = forms.CharField(max_length=40, required=False, label="Hujjat raqami")
    note = forms.CharField(max_length=200, required=False, label="Izoh")

    def clean(self):
        data = super().clean()
        ingredient = data.get("ingredient")
        if ingredient and data.get("quantity"):
            try: data["quantity_g"] = to_grams(data["quantity"], data["unit"], ingredient.gram_per_piece)
            except ValueError as exc: raise forms.ValidationError(str(exc))
        return data


class SupplierForm(forms.ModelForm):
    class Meta: model = Supplier; fields = ["name", "phone", "note", "is_active"]

