"""
Product models for the ordering system.
"""
from django.db import models


class Category(models.Model):
    """Product category (e.g. Food, Beverages, Snacks)."""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    """
    Individual product available for ordering.
    Indexed on category and is_available for fast filtering.
    """
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='products'
    )
    name = models.CharField(max_length=255, db_index=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    is_available = models.BooleanField(default=True, db_index=True)
    stock = models.PositiveIntegerField(default=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'name']
        indexes = [
            models.Index(fields=['is_available', 'category']),
        ]

    def __str__(self):
        return f"{self.name} - ₹{self.price}"
