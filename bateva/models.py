from django.db import models
from django.contrib.postgres.fields import ArrayField


class Customer(models.Model):
    id = models.AutoField(primary_key=True)
    full_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True, null=True)
    phones = ArrayField(
        models.CharField(max_length=50),
        blank=True,
        default=list,
        help_text="List of phone numbers"
    )
    address = models.TextField(blank=True, null=True)

    DELIVERY_CHOICES = [
        ("none", "None"),
        ("package", "Package"),
        ("morning_package", "Morning Package"),
        ("delivery", "Delivery"),
        ("morning_delivery", "Morning Delivery"),
    ]

    default_delivery = models.CharField(
        max_length=20, choices=DELIVERY_CHOICES, default="none"
    )
    in_neighborhood = models.BooleanField(default=True)
    metadata = models.JSONField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name


class Item(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2)
    sale_price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    MEASUREMENT_CHOICES = [
        ("countable", "Countable (units, pieces)"),
        ("weight", "Weight-based"),
    ]
    measurement_type = models.CharField(
        max_length=20, choices=MEASUREMENT_CHOICES, default="countable"
    )

    metadata = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.name


class WeekOrder(models.Model):
    id = models.AutoField(primary_key=True)
    week_order = models.CharField(
        max_length=10,
        unique=True,
        help_text="Year and week number, e.g. '2025-W36'"
    )
    csv_file = models.FileField(
        upload_to="week_orders_csv/",
        blank=True,
        null=True,
        help_text="CSV file containing weekly orders"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Week {self.week_order}"

class Order(models.Model):
    id = models.AutoField(primary_key=True)

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("ignored", "Completed"),
        ("completed", "Completed"),
        ("canceled", "Canceled"),
    ]

    DELIVERY_CHOICES = Customer.DELIVERY_CHOICES  # reuse same choices

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="orders"
    )
    fee_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    order_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    delivery_type = models.CharField(
        max_length=20, choices=DELIVERY_CHOICES, default="none"
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    week_order = models.ForeignKey(
        WeekOrder, on_delete=models.SET_NULL, blank=True, null=True,
        related_name="orders",
        help_text="The weekly batch this order belongs to"
    )

def save(self, *args, **kwargs):
    # Check if this is a new object
    is_new = self.pk is None

    super().save(*args, **kwargs)  # Save first to populate order_date

    if is_new and not self.week_order:
        year, week, _ = self.order_date.isocalendar()
        self.week_order = f"{year}-W{week}"
        # Save again to store week_order
        super().save(update_fields=['week_order'])

    metadata = models.JSONField(blank=True, null=True)

    def __str__(self):
        return f"Order {self.id} - {self.customer.full_name}"


class OrderItem(models.Model):
    id = models.AutoField(primary_key=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="order_items")
    quantity = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Use integer for countable items, decimal for weight"
    )
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} {self.item.unit or ''} × {self.item.name} (Order {self.order.id})"
