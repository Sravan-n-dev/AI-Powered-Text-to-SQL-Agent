"""
Seeds a small, self-contained e-commerce sample schema into the target
database: customers, categories, products, orders, order_items.

We deliberately do NOT depend on downloading an external dataset (like
Chinook) at setup time — that adds a network dependency that can break
silently. This schema is small but has everything needed to exercise
joins, aggregations, filters, and "repeat customer" style cohort
questions, which is what actually matters for demoing the agent.

Run with:
    python scripts/seed_sample_db.py
(from your host machine, with DATABASE_URL in .env pointing at
localhost:5432 — see README for details)
"""
import random
from datetime import datetime, timedelta

import psycopg2

from app.config import settings

random.seed(42)  # reproducible sample data

SCHEMA_SQL = """
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS categories CASCADE;
DROP TABLE IF EXISTS customers CASCADE;

CREATE TABLE customers (
    customer_id SERIAL PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    signup_date DATE NOT NULL,
    country TEXT NOT NULL
);

CREATE TABLE categories (
    category_id SERIAL PRIMARY KEY,
    category_name TEXT NOT NULL UNIQUE
);

CREATE TABLE products (
    product_id SERIAL PRIMARY KEY,
    product_name TEXT NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories(category_id),
    unit_price NUMERIC(10, 2) NOT NULL
);

CREATE TABLE orders (
    order_id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    order_date DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'completed'
);

CREATE TABLE order_items (
    order_item_id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(order_id),
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    quantity INTEGER NOT NULL,
    unit_price NUMERIC(10, 2) NOT NULL
);
"""

CATEGORY_NAMES = ["Electronics", "Home & Kitchen", "Books", "Sports & Outdoors", "Apparel"]

PRODUCTS_BY_CATEGORY = {
    "Electronics": [("Wireless Earbuds", 59.99), ("4K Monitor", 249.99), ("USB-C Hub", 34.99)],
    "Home & Kitchen": [("Air Fryer", 89.99), ("Coffee Grinder", 29.99), ("Cast Iron Pan", 44.99)],
    "Books": [("Python Crash Course", 24.99), ("Atomic Habits", 16.99), ("Dune", 12.99)],
    "Sports & Outdoors": [("Yoga Mat", 19.99), ("Camping Tent", 129.99), ("Water Bottle", 14.99)],
    "Apparel": [("Running Shoes", 79.99), ("Denim Jacket", 59.99), ("Wool Sweater", 49.99)],
}

COUNTRIES = ["USA", "Canada", "UK", "Germany", "India", "Australia"]


def seed():
    conn = psycopg2.connect(settings.database_url)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            print("Creating schema...")
            cur.execute(SCHEMA_SQL)

            print("Inserting categories...")
            category_ids = {}
            for name in CATEGORY_NAMES:
                cur.execute(
                    "INSERT INTO categories (category_name) VALUES (%s) RETURNING category_id",
                    (name,),
                )
                category_ids[name] = cur.fetchone()[0]

            print("Inserting products...")
            product_ids = []
            for category_name, products in PRODUCTS_BY_CATEGORY.items():
                for product_name, price in products:
                    cur.execute(
                        """INSERT INTO products (product_name, category_id, unit_price)
                           VALUES (%s, %s, %s) RETURNING product_id""",
                        (product_name, category_ids[category_name], price),
                    )
                    product_ids.append((cur.fetchone()[0], price))

            print("Inserting customers...")
            customer_ids = []
            first_names = ["Alex", "Sam", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Jamie"]
            last_names = ["Smith", "Johnson", "Lee", "Brown", "Garcia", "Patel", "Kim", "Nguyen"]
            for i in range(60):
                fn, ln = random.choice(first_names), random.choice(last_names)
                email = f"{fn.lower()}.{ln.lower()}{i}@example.com"
                signup = datetime(2024, 1, 1) + timedelta(days=random.randint(0, 500))
                cur.execute(
                    """INSERT INTO customers (first_name, last_name, email, signup_date, country)
                       VALUES (%s, %s, %s, %s, %s) RETURNING customer_id""",
                    (fn, ln, email, signup.date(), random.choice(COUNTRIES)),
                )
                customer_ids.append(cur.fetchone()[0])

            print("Inserting orders + order items...")
            today = datetime(2026, 8, 1)
            for customer_id in customer_ids:
                # Each customer places 0-5 orders, spread over the last year,
                # so some customers are "repeat" (2+) and some are one-time.
                num_orders = random.choices([0, 1, 2, 3, 4, 5], weights=[5, 25, 25, 20, 15, 10])[0]
                for _ in range(num_orders):
                    order_date = today - timedelta(days=random.randint(1, 365))
                    cur.execute(
                        """INSERT INTO orders (customer_id, order_date, status)
                           VALUES (%s, %s, 'completed') RETURNING order_id""",
                        (customer_id, order_date.date()),
                    )
                    order_id = cur.fetchone()[0]

                    num_items = random.randint(1, 4)
                    for _ in range(num_items):
                        product_id, price = random.choice(product_ids)
                        qty = random.randint(1, 3)
                        cur.execute(
                            """INSERT INTO order_items (order_id, product_id, quantity, unit_price)
                               VALUES (%s, %s, %s, %s)""",
                            (order_id, product_id, qty, price),
                        )

        conn.commit()
        print("✅ Sample database seeded successfully.")
        print("   Tables: customers, categories, products, orders, order_items")
        print("   Next step: python scripts/index_schema.py")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
