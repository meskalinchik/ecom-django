# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.signals import pre_save, post_save
from django.utils.text import slugify
from django.core.urlresolvers import reverse
from transliterate import translit
from notifications.signals import notify
from django.contrib.auth.models import User

class Category(models.Model):

	name = models.CharField(max_length=100)
	slug = models.SlugField(blank=True)

	def __unicode__(self):
		return self.name

	def get_absolute_url(self):
		return reverse('category_detail', kwargs={'category_slug': self.slug})

def pre_save_category_slug(sender, instance, *args, **kwargs):
	if not instance.slug:
		slug = slugify(translit(unicode(instance.name), reversed=True))
		instance.slug = slug

pre_save.connect(pre_save_category_slug, sender=Category)


class Brand(models.Model):

	name = models.CharField(max_length=100)

	def __unicode__(self):
		return self.name


def image_folder(instance, filename):
	filename = instance.slug + '.' + filename.split('.')[1]
	return "{0}/{1}".format(instance.slug, filename)


class SearchProductQuerySet(models.QuerySet):

	def by_brand(self, brand_name=None, category_name=None):
		qs = self
		print(dir(qs))
		if brand_name:
			return qs.filter(brand__name__icontains=brand_name)
		if category_name:
			return qs.filter(category__name=category_name)



class ProductManager(models.Manager):

	def get_queryset(self):
		return SearchProductQuerySet(self.model, using=self._db)

	def all(self):
		return super(ProductManager, self).get_queryset().filter(available=True)

class Product(models.Model):

	category = models.ForeignKey(Category)
	brand = models.ForeignKey(Brand)
	title = models.CharField(max_length=120)
	slug = models.SlugField()
	description = models.TextField()
	image = models.ImageField(upload_to=image_folder)
	price = models.DecimalField(max_digits=9, decimal_places=2)
	available = models.BooleanField(default=True)
	objects = ProductManager()

	def __unicode__(self):
		return self.title

	def get_absolute_url(self):
		return reverse('product_detail', kwargs={'product_slug': self.slug})

def product_available_notify(sender, instance, created, **kwargs):
	try:
		product_available = NotificationModel.objects.get(user=User.objects.get(pk=1))
		if product_available.product.available:
		    notify.send(
		    	instance,
		    	recipient=User.objects.get(pk=1), 
		    	description='Появился товар, который вы ждете - {0}'.format(instance.title),
		    	target=instance,
		    	verb='Появился товар, который вы ждете - "{0}"'.format(instance.title))
		    product_available.notified = True
		    product_available.save()
	except NotificationModel.DoesNotExist:
		pass

post_save.connect(product_available_notify, sender=Product)

class CartItem(models.Model):

	product = models.ForeignKey(Product)
	qty = models.PositiveIntegerField(default=1)
	item_total = models.DecimalField(max_digits=9, decimal_places=2, default=0.00)

	def __unicode__(self):
		return "Cart item for product {0}".format(self.product.title)


class Cart(models.Model):

	items = models.ManyToManyField(CartItem, blank=True)
	cart_total = models.DecimalField(max_digits=9, decimal_places=2, default=0.00)

	def __unicode__(self):
		return str(self.id)

	def add_to_cart(self, product_slug):
		cart = self
		product = Product.objects.get(slug=product_slug)
		new_item, _ = CartItem.objects.get_or_create(product=product, item_total=product.price)
		if new_item not in cart.items.all():
			cart.items.add(new_item)
			cart.save()

	def remove_from_cart(self, product_slug):
		cart = self
		product = Product.objects.get(slug=product_slug)
		for cart_item in cart.items.all():
			if cart_item.product == product:
				cart.items.remove(cart_item)
				cart.save()

	def change_qty(self, qty, item_id):
		cart = self
		cart_item = CartItem.objects.get(id=int(item_id))
		cart_item.qty = int(qty)
		cart_item.item_total = int(qty) * Decimal(cart_item.product.price)
		cart_item.save()
		new_cart_total = 0.00
		for item in cart.items.all():
			new_cart_total += float(item.item_total)
		cart.cart_total = new_cart_total
		cart.save()

ORDER_STATUS_CHOICES = (
	('Принят в обработку', 'Принят в обработку'),
	('Выполняется', 'Выполняется'),
	('Оплачен', 'Оплачен')
)

class Order(models.Model):

	user = models.ForeignKey(settings.AUTH_USER_MODEL)
	items = models.ForeignKey(Cart)
	total = models.DecimalField(max_digits=9, decimal_places=2, default=0.00)
	first_name = models.CharField(max_length=200)
	last_name = models.CharField(max_length=200)
	phone = models.CharField(max_length=20)
	address = models.CharField(max_length=255)
	buying_type = models.CharField(max_length=40, choices=(('Самовывоз', 'Самовывоз'), 
		('Доставка', 'Доставка')), default='Самовывоз')
	date = models.DateTimeField(auto_now_add=True)
	comments = models.TextField()
	status = models.CharField(max_length=100, choices=ORDER_STATUS_CHOICES, default=ORDER_STATUS_CHOICES[0][0])

	def __unicode__(self):
		return "Заказ №{0}".format(str(self.id))




class NotificationModel(models.Model):

	user = models.ForeignKey(settings.AUTH_USER_MODEL)
	product = models.ForeignKey(Product)
	notified = models.BooleanField(default=False)
	notify_accepted = models.BooleanField(default=False)

	def __unicode__(self):
		return "Notification for {0} about stock of {1}".format(
			self.user.username, 
			self.product.title
		)