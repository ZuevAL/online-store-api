# OnlineStore

REST API интернет-магазина на Django REST Framework. Поддерживает регистрацию и вход по JWT, пополнение баланса, каталог, корзину и оформление заказов с проверкой баланса и остатков. Товарами управляет администратор.

## Запуск

Запусти Docker Compose из корня проекта.

```bash
docker compose up --build
```

Django применит миграции при запуске. [Swagger UI](http://127.0.0.1:8000/api/docs/) · [Схема OpenAPI](http://127.0.0.1:8000/api/schema/)

## Администратор

Создай администратора в отдельном терминале после запуска контейнеров.

```bash
docker compose exec web python manage.py createsuperuser
```

## Тесты

```bash
docker compose exec web python manage.py test \
  apps.users.tests apps.products.tests apps.cart.tests apps.orders.tests
```
