import pandas as pd
import re
import csv
from io import TextIOWrapper

from django.views import View
from django.shortcuts import render, get_object_or_404, redirect

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Customer, Item, WeekOrder, Order, OrderItem
from .serializers import CustomerSerializer, ItemSerializer, WeekOrderSerializer, OrderSerializer, OrderItemSerializer


class OrderCSVUploadView(View):
    def get(self, request):
        return render(request, 'upload_orders.html')
    

class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer

    @action(detail=False, methods=['post'])
    def upload_xlsx(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)

        df = pd.read_excel(file, engine='openpyxl', header=None)

        orders_dict = {}
        current_customer = None
        columns = [(0, 1, 2), (4, 5, 6)]  # sets of columns in the XLSX

        def str_to_float(s):
            try:
                clean_s = re.sub(r'[^\d.-]', '', str(s))
                return round(float(clean_s), 3)
            except (ValueError, TypeError):
                return None

        # Build the dictionary
        for col_set in columns:
            for _, row in df.iterrows():
                # Detect new customer
                if 'איסוף: לוד' in str(row[col_set[0]]):
                    current_customer = row[col_set[0]].split('איסוף: לוד')[0].strip()
                    orders_dict[current_customer] = {"phone": row[col_set[0]].split('איסוף: לוד')[1].strip()}
                # Add product for current customer
                elif current_customer and pd.notna(row[col_set[0]]) and pd.notna(row[col_set[2]]) and row[col_set[0]] == 'תוספות':
                    orders_dict[current_customer]["fee_price"] = str_to_float(str(row[col_set[2]]).split(' ')[0].strip())
                elif current_customer and pd.notna(row[col_set[0]]) and pd.notna(row[col_set[2]]) and row[col_set[0]] == 'סך הכל':
                    orders_dict[current_customer]["total"] = str_to_float(str(row[col_set[2]]).split(' ')[0].strip())
                elif current_customer and pd.notna(row[col_set[0]]) and pd.notna(row[col_set[1]]) and pd.notna(row[col_set[2]]) and row[col_set[0]] != 'מוצר':
                    product = str(row[col_set[0]]).replace('"', '')
                    quantity = str_to_float(str(row[col_set[1]]).split(' ')[0].strip())
                    full_price = str_to_float(str(row[col_set[2]]).split(' ')[0].strip())
                    if quantity and full_price:
                        orders_dict[current_customer][product] = {}
                        orders_dict[current_customer][product]["quantity"] = quantity
                        orders_dict[current_customer][product]["price"] = full_price/quantity
                        orders_dict[current_customer][product]["measurement_type"] = 'weight' if 'ק"ג' in str(row[col_set[1]]) else 'countable'


        orders_created = 0
        order_items_created = 0
        # Create database entries
        for customer_name, items_dict in orders_dict.items():
            customer, _ = Customer.objects.get_or_create(
                full_name=customer_name,
                phone=items_dict.get('phone', ''),
                defaults={'default_delivery': 'none', 'in_neighborhood': True}
            )

            order = Order.objects.create(customer=customer, delivery_type=customer.default_delivery, fee_price=items_dict.get('fee_price', 0), total_amount=items_dict.get('total', 0))
            orders_created += 1

            for item_name, item_data in items_dict.items():
                if item_name in ['phone', 'fee_price', 'total']:
                    continue

                item, created = Item.objects.get_or_create(
                    name=item_name,
                    defaults={
                        'cost_price': item_data.get("price", 0),
                        'sale_price': item_data.get("price", 0),
                        'stock_quantity': 0,
                        'measurement_type': item_data.get("measurement_type", 'weight')
                    }
                )

                if not created:
                    updated = False
                    new_price = item_data.get("price", 0)
                    
                    if item.cost_price != new_price:
                        item.cost_price = new_price
                        updated = True
                    
                    if item.sale_price != new_price:
                        item.sale_price = new_price
                        updated = True
                    
                    if updated:
                        item.save()

                OrderItem.objects.create(order=order, item=item, quantity=quantity, unit_price=item.sale_price)
                order_items_created += 1

        return Response({
            "orders_created": orders_created,
            "order_items_created": order_items_created
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        serializer = self.get_serializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        self.queryset.model.objects.bulk_create([self.queryset.model(**item) for item in serializer.validated_data])
        return Response({"status": "orders created"}, status=status.HTTP_201_CREATED)


class CustomerCSVUploadView(View):
    def get(self, request):
        # render the template
        return render(request, 'upload_customers.html')


class CustomerListView(View):
    def get(self, request):
        # get all customers
        customers = Customer.objects.all().order_by('full_name')
        return render(request, 'customer_list.html', {'customers': customers})


class CustomerUpdateView(View):
    def get(self, request, customer_id):
        customer = get_object_or_404(Customer, id=customer_id)
        return render(request, 'customer_update.html', {'customer': customer})

    def post(self, request, customer_id):
        customer = get_object_or_404(Customer, id=customer_id)
        # Update fields from POST data
        customer.full_name = request.POST.get('full_name', customer.full_name)
        customer.email = request.POST.get('email', customer.email)
        customer.phone = request.POST.get('phone', customer.phone)
        customer.address = request.POST.get('address', customer.address)
        customer.default_delivery = request.POST.get('default_delivery', customer.default_delivery)
        customer.in_neighborhood = request.POST.get('in_neighborhood') == 'on'
        customer.metadata = request.POST.get('metadata', customer.metadata)
        customer.save()
        return redirect('customer_list')
    
class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        serializer = self.get_serializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        self.queryset.model.objects.bulk_create([self.queryset.model(**item) for item in serializer.validated_data])
        return Response({"status": "customers created"}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def bulk_upload_csv(self, request):
        """
        Accepts a CSV file with customer data.
        Adjusts first two columns into full_name,
        prepends 0 to the phone column, and creates customers in bulk.
        """
        file = request.FILES.get('file')
        if not file:
            return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)

        decoded_file = TextIOWrapper(file, encoding='utf-8')
        reader = csv.reader(decoded_file)

        customers_to_create = []

        for row in reader:
            # Example row: ["חרות", "אביטן", "525649463", "שלב ב כצנלסון 5 קומה 5 דירה 21"]
            if len(row) < 4:
                continue  # skip invalid rows

            full_name = f"{row[0]} {row[1]}"
            phone = f"0{row[2]}"  # prepend 0 to the phone
            address_raw = row[3].strip()
            if address_raw == "מחוץ לשכונה":
                address = ""
                in_neighborhood = False
            else:
                address = address_raw
                in_neighborhood = True

            customers_to_create.append(
                Customer(
                    full_name=full_name,
                    phone=phone,
                    address=address,
                    in_neighborhood=in_neighborhood
                )
            )

        Customer.objects.bulk_create(customers_to_create)

        return Response(
            {"status": f"{len(customers_to_create)} customers created"},
            status=status.HTTP_201_CREATED
        )


class ItemViewSet(viewsets.ModelViewSet):
    queryset = Item.objects.all()
    serializer_class = ItemSerializer

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        serializer = self.get_serializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        self.queryset.model.objects.bulk_create([self.queryset.model(**item) for item in serializer.validated_data])
        return Response({"status": "items created"}, status=status.HTTP_201_CREATED)


class WeekOrderViewSet(viewsets.ModelViewSet):
    queryset = WeekOrder.objects.all()
    serializer_class = WeekOrderSerializer

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        serializer = self.get_serializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        self.queryset.model.objects.bulk_create([self.queryset.model(**item) for item in serializer.validated_data])
        return Response({"status": "week orders created"}, status=status.HTTP_201_CREATED)


class OrderItemViewSet(viewsets.ModelViewSet):
    queryset = OrderItem.objects.all()
    serializer_class = OrderItemSerializer

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        serializer = self.get_serializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        self.queryset.model.objects.bulk_create([self.queryset.model(**item) for item in serializer.validated_data])
        return Response({"status": "order items created"}, status=status.HTTP_201_CREATED)
