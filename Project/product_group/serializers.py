from rest_framework import serializers
from .models import ProductGroup, Product_Services, QuoteItem, Quote
from client.models import Company  # Import Company model

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
    - On GET, it shows the product_group_name string.
    - On POST/PUT, it accepts a simple integer ID for product_group.
    """
    product_group = serializers.SlugRelatedField(
        slug_field='product_group_name', 
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

    def update(self, instance, validated_data):
        # Set the modified_by user from the request context
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            instance.modified_by = request.user
        
        # The 'product_group' in validated_data is a ProductGroup instance
        # because PrimaryKeyRelatedField resolves the ID to an object.
        return super().update(instance, validated_data)

# --- QUOTATION SERIALIZERS ---

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
            'author',
            'sub_total',
            'tax_percentage',
            'total_amount',
            'created_at',
            'updated_at',
            'created_by',
            'modified_by',
            'items',  # The nested line items
        ]

    def _calculate_totals(self, quote_instance):
        """A helper method to calculate and save totals for a quote."""
        sub_total = sum(item.amount for item in quote_instance.items.all())
        
        # Ensure tax_percentage is not None
        tax_percentage = quote_instance.tax_percentage or 0
        total_amount = sub_total * (1 + (tax_percentage / 100))
        
        quote_instance.sub_total = sub_total
        quote_instance.total_amount = total_amount
        quote_instance.save(update_fields=['sub_total', 'total_amount'])

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


