from rest_framework import serializers
from .models import ProductGroup, Product_Services
class ProductGroupSerializer(serializers.ModelSerializer):

    created_by = serializers.StringRelatedField(read_only=True)
    modified_by = serializers.StringRelatedField(read_only=True)
    class Meta:
        model = ProductGroup
        fields = '__all__'

    def get_modified_by(self, obj):
        return obj.modified_by.username if obj.modified_by else None
    

    def validate_product_group_name(self, value):
        if ProductGroup.objects.filter(product_group_name__iexact=value).exists():
            raise serializers.ValidationError("Product group already exists.")
        return value
    
   
class ProductServicesSerializer(serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)
    modified_by = serializers.StringRelatedField(read_only=True)

    product_group = serializers.SerializerMethodField(read_only=True)


    class Meta:
        model = Product_Services
        fields = '__all__'
        extra_kwargs = {
            'product_group': {'required': True},
        }
    def get_product_group(self, obj):
        return obj.product_group.product_group_name if obj.product_group else None