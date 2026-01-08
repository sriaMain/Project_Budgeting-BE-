from product_group.models import Product_Services, ProductGroup

# Check products 2 and 3
prod2 = Product_Services.objects.get(id=2)
prod3 = Product_Services.objects.get(id=3)

print("Product 2 (Full Stack):")
print(f"  ID: {prod2.id}")
print(f"  Name: {prod2.product_service_name}")
print(f"  Product Group ID: {prod2.product_group_id}")
print(f"  Product Group Name: {prod2.product_group.product_group_name if prod2.product_group else 'None'}")

print("\nProduct 3 (Backend):")
print(f"  ID: {prod3.id}")
print(f"  Name: {prod3.product_service_name}")
print(f"  Product Group ID: {prod3.product_group_id}")
print(f"  Product Group Name: {prod3.product_group.product_group_name if prod3.product_group else 'None'}")

print("\n" + "="*50)
print("All Product Groups:")
for pg in ProductGroup.objects.all():
    services = Product_Services.objects.filter(product_group=pg)
    print(f"\nGroup {pg.id}: {pg.product_group_name}")
    for svc in services:
        print(f"  - {svc.id}: {svc.product_service_name}")
