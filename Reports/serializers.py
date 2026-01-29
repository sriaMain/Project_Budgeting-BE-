from rest_framework import serializers


class MetricSerializer(serializers.Serializer):
    value = serializers.DecimalField(max_digits=15, decimal_places=2)
    change = serializers.IntegerField()


class DashboardMetricsSerializer(serializers.Serializer):
    budget = MetricSerializer()
    invoiced = MetricSerializer()
    received = MetricSerializer()
    expenses = MetricSerializer()
    profit = MetricSerializer()