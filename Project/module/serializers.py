from rest_framework import serializers
from .models import Module

class ModuleSerializer(serializers.ModelSerializer):

    created_by = serializers.StringRelatedField(read_only=True)
    modified_by = serializers.StringRelatedField(read_only=True)
    class Meta:
        model = Module
        fields = '__all__'

    def get_modified_by(self, obj):
        return obj.modified_by.username if obj.modified_by else None

