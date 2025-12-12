from rest_framework import serializers
from .models import ProductGroup, Product_Services, QuoteItem, Quote
from client.models import Company, POC  # Import Company and POC models

class ProductGroupSerializer(serializers.ModelSerializer):
 
    created_by = serializers.StringRelatedField(read_only=True)
    modified_by = serializers.StringRelatedField(read_only=True)
    class Meta:
        model = ProductGroup
        fields = [
            'id',
            'product_group_name',
            'description',
            'created_by',
            'modified_by',
            'created_at',
            'updated_at'
        ]
 
    def to_representation(self, instance):
        data = super().to_representation(instance)
 
        # Rename key from product_group_name -> product_group
        data['product_group'] = data.pop('product_group_name')
 
        return data
 
    def get_modified_by(self, obj):
        return obj.modified_by.username if obj.modified_by else None
   
 
    def validate_product_group_name(self, value):
        if ProductGroup.objects.filter(product_group_name__iexact=value).exists():
            raise serializers.ValidationError("Product group already exists.")
        return value
    
class ProductServicesSerializer(serializers.ModelSerializer):
    """
    Serializer for Product_Services.
    - On GET → show product_group object or product_group_name (if nested).
    - On POST/PUT → accept product_group as integer primary key.
    """

    product_group = serializers.PrimaryKeyRelatedField(
        queryset=ProductGroup.objects.all(),
        allow_null=True
    )

    created_by = serializers.StringRelatedField(read_only=True)
    modified_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Product_Services
        fields = [
            'id',
            'product_group',
            'product_service_name',
            'description',
            'is_active',
            'created_by',
            'modified_by',
            'created_at',
            'updated_at',
        ]

    def create(self, validated_data):
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['created_by'] = request.user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['modified_by'] = request.user
        return super().update(instance, validated_data)
    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.product_group:
            data['product_group'] = instance.product_group.product_group_name
        return data


   

class QuoteItemSerializer(serializers.ModelSerializer):
    """
    Serializer for each line item in a quote.
    """
    class Meta:
        model = QuoteItem
        fields = [
            'id',
            'product_service',
            'description',
            'quantity',
            'unit',
            'price_per_unit',
            'cost',
            'po_number',
            'bill_number',
            'amount',
        ]
        read_only_fields = ['amount'] # Amount is calculated by the model


class QuoteSerializer(serializers.ModelSerializer):
    """
    Serializer for the main Quote model. It includes nested QuoteItems.
    """
    items = QuoteItemSerializer(many=True)
    
    # Use the new 'client' foreign key relationship
    client = serializers.PrimaryKeyRelatedField(queryset=Company.objects.all())
    client_name = serializers.StringRelatedField(source='client', read_only=True)
    poc = serializers.PrimaryKeyRelatedField(queryset=POC.objects.all(), allow_null=True)
    poc_name = serializers.StringRelatedField(source='poc', read_only=True)

    created_by = serializers.StringRelatedField(read_only=True)
    modified_by = serializers.StringRelatedField(read_only=True)
    author = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Quote
        fields = [
            'quote_no',
            'quote_name',
            'date_of_issue',
            'due_date',
            'status',
            'client',  # Use this for writing
            'client_name', # This will be used for reading
            'poc',
            'poc_name',
            'author',
            'sub_total',
            'tax_percentage',
            'total_amount',
            'total_cost',
            'in_house_cost',
            'outsourced_cost',
            'invoiced_sum',
            'to_be_invoiced_sum',
            'created_at',
            'updated_at',
            'created_by',
            'modified_by',
            'items',  # The nested line items
            
        ]

    def _calculate_totals(self, quote_instance):
        """A helper method to calculate and save totals for a quote."""
        from decimal import Decimal
        items = quote_instance.items.all()
        sub_total = sum(item.amount for item in items)
        total_cost = sum(item.cost for item in items if item.cost is not None)

        # Ensure tax_percentage is not None and is Decimal
        tax_percentage = quote_instance.tax_percentage or Decimal('0')
        if not isinstance(tax_percentage, Decimal):
            tax_percentage = Decimal(str(tax_percentage))
        total_amount = sub_total * (Decimal('1') + (tax_percentage / Decimal('100')))

        quote_instance.sub_total = sub_total
        quote_instance.total_amount = total_amount
        quote_instance.total_cost = total_cost
        quote_instance.save(update_fields=['sub_total', 'total_amount', 'total_cost'])

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        
        # Create the main Quote instance
        quote = Quote.objects.create(**validated_data)
        
        # Create each QuoteItem instance
        for item_data in items_data:
            QuoteItem.objects.create(quote=quote, **item_data)
        
        # Calculate and save the totals
        self._calculate_totals(quote)
            
        return quote

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)

        # Update the main Quote instance
        instance = super().update(instance, validated_data)

        # Handle updating the line items
        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                QuoteItem.objects.create(quote=instance, **item_data)

        # Recalculate and save the totals
        self._calculate_totals(instance)

        return instance


class ProductServiceModuleSerializer(serializers.ModelSerializer):
    module_id = serializers.IntegerField(source='id')
    module_name = serializers.CharField(source='product_service_name')

    class Meta:
        model = Product_Services
        fields = ['module_id', 'module_name', 'description', 'is_active']

class ProductGroupWithModulesSerializer(serializers.ModelSerializer):
    group_id = serializers.IntegerField(source='id')
    group_name = serializers.CharField(source='product_group_name')
    modules = ProductServiceModuleSerializer(source='products_services', many=True)

    class Meta:
        model = ProductGroup
        fields = ['group_id', 'group_name', 'description', 'modules']


class QuoteSummarySerializer(serializers.ModelSerializer):
    client_id = serializers.IntegerField(source='client.id')
    client_name = serializers.StringRelatedField(source='client')

    class Meta:
        model = Quote
        fields = [
            'quote_no',
            'client_id',
            'client_name',
            'quote_name',
            'date_of_issue',
            'quote_value',
            'status',
        ]

    quote_value = serializers.DecimalField(source='total_amount', max_digits=15, decimal_places=2)


class QuoteItemDetailSerializer(serializers.ModelSerializer):
    product_group = serializers.CharField(source='product_service.product_group.product_group_name', read_only=True)
    product_name = serializers.CharField(source='product_service.product_service_name', read_only=True)

    class Meta:
        model = QuoteItem
        fields = [
            'product_group',
            'product_name',
            'quantity',
            'unit',
            'price_per_unit',
            'amount',
            'cost',
            'po_number',
            'bill_number',
        ]

class ClientDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ['company_name', 'street_address', 'city', 'state', 'country']

class QuoteDetailSerializer(serializers.ModelSerializer):
    author = serializers.StringRelatedField()
    client = ClientDetailSerializer(read_only=True)
    items = QuoteItemDetailSerializer(many=True, read_only=True)

    class Meta:
        model = Quote
        fields = [
            'quote_no',
            'quote_name',
            'date_of_issue',
            'due_date',
            'status',
            'author',
            'client',
            'sub_total',
            'tax_percentage',
            'total_amount',
            'total_cost',
            'in_house_cost',
            'outsourced_cost',
            'invoiced_sum',
            'to_be_invoiced_sum',
            'items',
        ]