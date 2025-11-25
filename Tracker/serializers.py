from rest_framework import serializers
from .models import Company, CompanyTag


class CompanyTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyTag
        fields = ["id", "name"]


class CompanySerializer(serializers.ModelSerializer):
    # read tags as objects
    tags = CompanyTagSerializer(many=True, read_only=True)
    # write tags by id list
    tag_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        write_only=True,
        queryset=CompanyTag.objects.all(),
        source="tags"
    )

    class Meta:
        model = Company
        fields = [
            "id",
            "company_name",
            "mobile_number",
            "email",
            "gstin",
            "street_address",
            "city",
            "postal_code",
            "municipality",
            "state",
            "country",
            "tags",       # read-only list of tag objects
            "tag_ids",    # write-only list of tag ids
            "created_at",
            "updated_at",
        ]
