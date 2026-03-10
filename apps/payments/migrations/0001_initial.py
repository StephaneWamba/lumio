# Generated migration for payments app
from django.db import migrations, models
import django.db.models.deletion
import django.core.validators
from decimal import Decimal


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('courses', '0001_initial'),
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Price',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, help_text='Price in currency units', max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal('0.00'))])),
                ('currency', models.CharField(choices=[('USD', 'US Dollar'), ('EUR', 'Euro'), ('GBP', 'British Pound')], default='USD', max_length=3)),
                ('discount_percent', models.DecimalField(decimal_places=2, default=0, max_digits=5, validators=[django.core.validators.MinValueValidator(0)])),
                ('discount_until', models.DateTimeField(blank=True, help_text='Discount valid until this date', null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('course', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='pricing', to='courses.course')),
            ],
            options={
                'verbose_name': 'Price',
                'verbose_name_plural': 'Prices',
            },
        ),
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal('0.00'))])),
                ('currency', models.CharField(default='USD', max_length=3)),
                ('payment_method', models.CharField(choices=[('credit_card', 'Credit Card'), ('paypal', 'PayPal'), ('bank_transfer', 'Bank Transfer')], default='credit_card', max_length=50)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('processing', 'Processing'), ('completed', 'Completed'), ('failed', 'Failed'), ('refunded', 'Refunded')], db_index=True, default='pending', max_length=20)),
                ('transaction_id', models.CharField(help_text='External payment processor transaction ID', max_length=255, unique=True)),
                ('processor_response', models.TextField(blank=True)),
                ('is_refunded', models.BooleanField(default=False)),
                ('refunded_amount', models.DecimalField(decimal_places=2, default=0, max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal('0.00'))])),
                ('refunded_at', models.DateTimeField(blank=True, null=True)),
                ('refund_reason', models.TextField(blank=True)),
                ('initiated_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('course', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='payments', to='courses.course')),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='payments', to='users.user')),
            ],
            options={
                'verbose_name': 'Payment',
                'verbose_name_plural': 'Payments',
                'ordering': ['-initiated_at'],
            },
        ),
        migrations.CreateModel(
            name='PaymentLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('log_type', models.CharField(choices=[('created', 'Created'), ('initiated', 'Initiated'), ('processing', 'Processing'), ('completed', 'Completed'), ('failed', 'Failed'), ('refund_initiated', 'Refund Initiated'), ('refunded', 'Refunded')], max_length=20)),
                ('message', models.TextField()),
                ('details', models.TextField(blank=True, help_text='JSON details of the log entry')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('payment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='logs', to='payments.payment')),
            ],
            options={
                'verbose_name': 'Payment Log',
                'verbose_name_plural': 'Payment Logs',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Invoice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('invoice_number', models.CharField(help_text='Invoice number for reference', max_length=50, unique=True)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('issued', 'Issued'), ('paid', 'Paid'), ('overdue', 'Overdue'), ('cancelled', 'Cancelled')], default='draft', max_length=20)),
                ('subtotal', models.DecimalField(decimal_places=2, max_digits=10)),
                ('tax_amount', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('total_amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('issued_date', models.DateField(blank=True, null=True)),
                ('due_date', models.DateField(blank=True, null=True)),
                ('paid_date', models.DateField(blank=True, null=True)),
                ('notes', models.TextField(blank=True)),
                ('terms', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('payment', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='invoice', to='payments.payment')),
            ],
            options={
                'verbose_name': 'Invoice',
                'verbose_name_plural': 'Invoices',
                'ordering': ['-issued_date'],
            },
        ),
        migrations.AddIndex(
            model_name='payment',
            index=models.Index(fields=['user', '-initiated_at'], name='payment_user_initiated_idx'),
        ),
        migrations.AddIndex(
            model_name='payment',
            index=models.Index(fields=['status', '-initiated_at'], name='payment_status_initiated_idx'),
        ),
        migrations.AddIndex(
            model_name='paymentlog',
            index=models.Index(fields=['payment', '-created_at'], name='paylog_payment_created_idx'),
        ),
        migrations.AddIndex(
            model_name='paymentlog',
            index=models.Index(fields=['log_type', '-created_at'], name='paylog_type_created_idx'),
        ),
    ]
