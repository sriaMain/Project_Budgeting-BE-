from rest_framework import serializers
from .models import POC, Company, CompanyTag


class CompanyTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyTag
        fields = ["id", "name"]


# class CompanySerializer(serializers.ModelSerializer):
#     tags = serializers.PrimaryKeyRelatedField(
#         many=True,
#         queryset=CompanyTag.objects.all(),
#     )

#     class Meta:
#         model = Company
#         fields = [
#             "id",
#             "company_name",
#             "mobile_number",
#             "email",
#             "gstin",
#             "street_address",
#             "city",
#             "postal_code",
#             "municipality",
#             "state",
#             "country",
#             "tags",
#             "created_at",
#             "updated_at",
#         ]
        
#     required_fields = ["country","state"]


#     def to_representation(self, instance):
#         """
#         Customize the representation to show nested tags on read.
#         """
#         representation = super().to_representation(instance)
#         representation['tags'] = CompanyTagSerializer(instance.tags.all(), many=True).data
#         # return representation
class CompanySerializer(serializers.ModelSerializer):
    tags = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=CompanyTag.objects.all(),
        required=False,   # Important
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
            "tags",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "country": {"required": True},
            "state": {"required": True},
            # All other fields optional during update
            "email": {"required": False},
            "company_name": {"required": False},
            "mobile_number": {"required": False},
            "gstin": {"required": False},
            "street_address": {"required": False},
            "city": {"required": False},
            "postal_code": {"required": False},
            "municipality": {"required": False},
        }

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['tags'] = CompanyTagSerializer(instance.tags.all(), many=True).data
        return rep

class PointOfContactSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.company_name', read_only=True)

    class Meta:
        model = POC
        fields = ["id", "company", "company_name", "poc_name", "designation", "poc_mobile", "poc_email"]
        extra_kwargs = {
            'company': {'write_only': True}
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If an instance is passed (i.e., for an update), make 'company' not required.
        if self.instance:
            self.fields['company'].required = False

    def validate_company(self, value):
        if not Company.objects.filter(id=value.id).exists():
            raise serializers.ValidationError("Company does not exist.")
        return value

    def validate(self, data):
        """
        Check for duplicate email or mobile number within the same company.
        """
        # For updates where company_id is not provided, use the instance's company
        company = data.get('company') or (self.instance and self.instance.company)
        
        poc_email = data.get('poc_email')
        poc_mobile = data.get('poc_mobile')
        
        # On update, self.instance is the existing POC object.
        # On create, self.instance is None.
        instance = self.instance

        # Base queryset for checking duplicates
        queryset = POC.objects.filter(company=company)

        # If updating, exclude the current instance from the queryset
        if instance:
            queryset = queryset.exclude(pk=instance.pk)

        # Check if a POC with the same email exists for this company
        if poc_email and queryset.filter(poc_email__iexact=poc_email).exists():
            raise serializers.ValidationError(
                "A point of contact with this email address already exists for this company."
            )

        # Check if a POC with the same mobile number exists for this company
        if poc_mobile and queryset.filter(poc_mobile=poc_mobile).exists():
            raise serializers.ValidationError(
                "A point of contact with this mobile number already exists for this company."
            )

        return data